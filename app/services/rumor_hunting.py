import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from websockets import connect
from ..config import settings
from ..db import SupabaseClient
from ..rate_limiter import anti_429_delay
from .vn_stock_source import VNStockSource
from core.validator import DataValidator
from core.schemas.crypto_schema import RumorHuntingRecord


class AdvancedRumorHunting:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.dedup_cache: set[str] = set()
        self.max_cache_size = 500
        self.vn_source = VNStockSource()
        self._coinglass_cache: dict[str, tuple[dict, datetime]] = {}

    async def scan(self) -> list[dict]:
        tickers = await self.fetch_binance_snapshot()
        symbols = [item["symbol"] for item in tickers if item["symbol"].endswith("USDT")][:80]
        websocket_data = await self.collect_binance_websocket(symbols)
        records: list[dict] = []

        for ticker in tickers:
            symbol = ticker["symbol"]
            if not symbol.endswith("USDT"):
                continue

            score, reason = await self.score_ticker(ticker, websocket_data.get(symbol))
            if score < 6.0:
                continue

            record = self.build_record(ticker, score, reason)
            if self.is_duplicate(record):
                continue

            records.append(record)

        records.sort(key=lambda item: item["analysis_score"], reverse=True)
        records = records[:20]

        if records:
            validated_records, validation_errors = DataValidator.validate_many(RumorHuntingRecord, records)
            if validation_errors:
                logging.warning("[RumorHunting] Dropped %d invalid rumor hunting records.", len(validation_errors))
                for err in validation_errors:
                    logging.debug("[RumorHunting] Validation error %s: %s", err["index"], err["errors"])

            if validated_records:
                logging.info("[RumorHunting] Pushing %d records to Supabase.", len(validated_records))
                await self.supabase_client.insert_rows(settings.rumour_table, validated_records)
            else:
                logging.warning("[RumorHunting] No valid rumor hunting records to push.")

        return records

    async def fetch_binance_snapshot(self) -> list[dict]:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get("https://api.binance.com/api/v3/ticker/24hr")
            response.raise_for_status()
            await anti_429_delay()
            return response.json()[:500]

    async def fetch_coinglass_data(self, symbol: str) -> dict | None:
        if not settings.coinglass_api_key:
            return None

        now = datetime.now(timezone.utc)
        if symbol in self._coinglass_cache:
            cached_data, expiry = self._coinglass_cache[symbol]
            if now < expiry:
                return cached_data
            else:
                del self._coinglass_cache[symbol]

        async with AsyncClient(timeout=20.0) as client:
            await anti_429_delay()
            response = await client.get(
                "https://open-api.coinglass.com/api/pro/v1/fundFlow",
                headers={"coinglassSecret": settings.coinglass_api_key},
                params={"symbol": symbol},
            )

            if response.status_code != 200:
                logging.warning("[RumorHunting] Coinglass request failed for %s: %s", symbol, response.status_code)
                return None

            payload = response.json()
            data = payload.get("data") or payload
            self._coinglass_cache[symbol] = (data, now + timedelta(minutes=5))
            return data

    async def fetch_vn_stock_data(self, symbol: str) -> dict | None:
        if not self.vn_source.base_url:
            return None
        return await self.vn_source.fetch_symbol_flow(symbol)

    async def collect_binance_websocket(self, symbols: list[str]) -> dict[str, dict]:
        result: dict[str, dict] = {}
        if not symbols:
            return result

        try:
            uri = "wss://stream.binance.com:9443/ws/!ticker@arr"
            async with connect(uri) as ws:
                raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                payload = json.loads(raw)
                for item in payload:
                    symbol = item.get("s")
                    if symbol in symbols:
                        result[symbol] = {
                            "price_change_percent": float(item.get("P", 0)),
                            "quote_volume": float(item.get("q", 0)),
                        }
        except Exception as exc:
            logging.warning("[RumorHunting] Binance websocket fetch failed: %s", exc)

        return result

    async def score_ticker(self, ticker: dict, websocket_data: dict | None) -> tuple[float, str]:
        price_change = float(ticker.get("priceChangePercent", 0) or 0)
        quote_volume = float(ticker.get("quoteVolume", 0) or 0)
        base_volume = float(ticker.get("volume", 0) or 0)

        score = 0.0
        reasons: list[str] = []

        if abs(price_change) <= 4.0:
            score += 2.0
            reasons.append("Sideway giá 24h")
        if base_volume >= 10000:
            score += 1.0
            reasons.append("Volume giao dịch ổn định")
        if quote_volume >= 5_000_000:
            score += 1.0
            reasons.append("Quote volume mạnh")

        if websocket_data and abs(websocket_data.get("price_change_percent", 0)) <= 2.5:
            score += 1.0
            reasons.append("Live stream sideway")

        coinglass_payload = await self.fetch_coinglass_data(ticker["symbol"])
        if coinglass_payload:
            outflow = self.extract_coinglass_outflow(coinglass_payload)
            if outflow is not None and outflow < -300000:
                score += 2.0
                reasons.append("Outflow mạnh liên tục từ Coinglass")

        vn_payload = await self.fetch_vn_stock_data(ticker["symbol"])
        if vn_payload and isinstance(vn_payload, dict):
            net_flow = vn_payload.get("netFlow") or vn_payload.get("flow")
            try:
                if net_flow is not None and float(net_flow) < -100000000:
                    score += 1.0
                    reasons.append(f"Outflow VN {settings.vn_stock_source or 'DNS'} mạnh")
            except (TypeError, ValueError):
                pass

        if score >= 6.0:
            reasons.append("Đủ điều kiện Rumor Hunting TOP 20")

        return round(min(score, 10.0), 1), "; ".join(reasons)

    def extract_coinglass_outflow(self, payload: dict) -> float | None:
        candidates = [
            payload.get("netFlow"),
            payload.get("outflow"),
            payload.get("data", {}).get("netFlow") if isinstance(payload.get("data"), dict) else None,
        ]
        for value in candidates:
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def build_record(self, ticker: dict, score: float, reason: str) -> dict:
        timestamp = datetime.now(timezone.utc) + timedelta(hours=7)
        symbol = ticker["symbol"]
        summary = (
            f"Quét Binance + Coinglass: Sideway giá, volume nén và outflow liên tục. "
            f"Điểm lõi {score}/10."
        )
        return {
            "ticker": symbol,
            "source": "AdvancedRumorHunting",
            "intel_source": "Binance/Coinglass",
            "rumor_summary": summary,
            "analysis_score": score,
            "live_status": "Active",
            "detected_at": timestamp.isoformat(),
            "details": reason,
            "quote_volume": float(ticker.get("quoteVolume", 0) or 0),
            "price_change_percent": float(ticker.get("priceChangePercent", 0) or 0),
        }

    def is_duplicate(self, record: dict) -> bool:
        signature = hashlib.sha256(
            f"{record['ticker']}|{record['source']}|{record['rumor_summary']}".encode("utf-8")
        ).hexdigest()
        if signature in self.dedup_cache:
            return True
        self.dedup_cache.add(signature)
        if len(self.dedup_cache) > self.max_cache_size:
            self.dedup_cache = set(list(self.dedup_cache)[-400:])
        return False
