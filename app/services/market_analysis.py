import logging
from datetime import datetime, timezone
from httpx import AsyncClient
from .ai_analysis import AIAnalyzer
from ..db import SupabaseClient


class MarketAnalysisEngine:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.ai = AIAnalyzer(supabase_client)

    async def scan(self) -> list[dict]:
        logging.info("[MarketAnalysis] Fetching raw market data from Binance.")
        raw = await self.fetch_binance_tickers()
        if not raw:
            logging.warning("[MarketAnalysis] No Binance data available.")
            return []

        scan_items = []
        for item in raw:
            scan_items.append(self.build_scan_record(item))

        scan_items = sorted(scan_items, key=lambda item: item["score"], reverse=True)[:120]

        for item in scan_items[:10]:
            item["ai_note"] = await self.ai.summarize_scan(
                summary=self.format_scan_summary(item),
                context="Dữ liệu điểm số, tín hiệu và thanh khoản từ Binance 24h",
            )

        signal_items = [self.build_signal_record(item) for item in scan_items if item["signal"] in {"GOLDEN", "ACCUMULATE"}]

        logging.info("[MarketAnalysis] Writing %d market scans", len(scan_items))
        await self.supabase_client.upsert_rows("market_scans", scan_items, conflict="id")

        logging.info("[MarketAnalysis] Writing %d market signals", len(signal_items))
        await self.supabase_client.upsert_rows("market_signals", signal_items, conflict="id")

        return scan_items

    async def fetch_binance_tickers(self) -> list[dict]:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get("https://api.binance.com/api/v3/ticker/24hr", params={"limit": 500})
            response.raise_for_status()
            data = response.json()

        return [
            item for item in data
            if isinstance(item, dict)
            and item.get("symbol", "").endswith("USDT")
            and float(item.get("quoteVolume", 0) or 0) >= 1_000_000
        ]

    def build_scan_record(self, item: dict) -> dict:
        ticker = item["symbol"]
        price = float(item.get("lastPrice") or 0)
        change24h = float(item.get("priceChangePercent") or 0)
        volume = float(item.get("quoteVolume") or 0)
        fvg = change24h >= 3.0 and volume >= 30_000_000
        liquidity_sweep = volume >= 50_000_000 and change24h >= 1.5
        score = self.compute_score(change24h, volume)
        signal = self.compute_signal(score, change24h)
        structure = self.compute_structure(change24h)
        rsi = self.estimate_rsi(change24h)
        vwap_position = "Above" if change24h >= 0 else "Below"
        note = f"Binance 24h {change24h:+.2f}%, volume {volume:,.0f}."
        now = datetime.now(timezone.utc).isoformat()

        return {
            "id": ticker,
            "ticker": ticker,
            "name": ticker,
            "market": "CRYPTO",
            "price": price,
            "change24h": round(change24h, 2),
            "score": round(score, 1),
            "signal": signal,
            "structure": structure,
            "fvg": fvg,
            "liquidity_sweep": liquidity_sweep,
            "rsi": round(rsi, 1),
            "vwap_position": vwap_position,
            "note": note,
            "updated_at": now,
            "ai_note": None,
        }

    def build_signal_record(self, scan: dict) -> dict:
        entry_price = None
        if scan["price"] and scan["signal"] in {"GOLDEN", "ACCUMULATE"}:
            entry_price = round(scan["price"] * 0.995, 8)

        return {
            "id": scan["ticker"],
            "ticker": scan["ticker"],
            "market": scan["market"],
            "entry_price": entry_price,
            "score": scan["score"],
            "signal_type": scan["signal"],
            "note": scan["note"],
            "created_at": scan["updated_at"],
        }

    def format_scan_summary(self, scan: dict) -> str:
        return (
            f"Ticker {scan['ticker']}, giá {scan['price']}, change24h {scan['change24h']}%, "
            f"score {scan['score']}, signal {scan['signal']}, structure {scan['structure']}, "
            f"FVG={scan['fvg']}, sweep={scan['liquidity_sweep']}, RSI~{scan['rsi']}"
        )

    def compute_score(self, change24h: float, volume: float) -> float:
        score = 5.0
        score += min(4.0, max(-4.0, change24h * 0.12))
        score += min(3.0, volume / 25_000_000)
        score += 1.0 if change24h > 0 else -0.5
        return max(1.0, min(10.0, score))

    def compute_signal(self, score: float, change24h: float) -> str:
        if score >= 8.0 and change24h >= 1.5:
            return "GOLDEN"
        if score >= 6.0:
            return "ACCUMULATE"
        if change24h <= -6.0:
            return "AVOID"
        return "HOLD"

    def compute_structure(self, change24h: float) -> str:
        if change24h >= 2.5:
            return "BOS_UP"
        if change24h <= -2.5:
            return "BOS_DOWN"
        return "RANGE"

    def estimate_rsi(self, change24h: float) -> float:
        if change24h >= 5.0:
            return 78.0
        if change24h <= -5.0:
            return 22.0
        return 50.0 + change24h * 2.0
