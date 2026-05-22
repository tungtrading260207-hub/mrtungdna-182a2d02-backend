import logging
from datetime import datetime, timezone
from httpx import AsyncClient
from .ai_analysis import AIAnalyzer
from ..config import settings
from ..db import SupabaseClient
from core.validator import DataValidator
from core.schemas.stock_schema import MarketScan, MarketSignal


class MarketAnalysisEngine:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.ai = AIAnalyzer(supabase_client)

    def _supabase_headers(self) -> dict[str, str]:
        api_key = settings.supabase_service_key
        if not api_key:
            raise RuntimeError("Supabase service key is not configured")
        return {
            "apikey": api_key,
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def _upsert_supabase(self, table: str, rows: list[dict], conflict: str):
        import os
        from httpx import AsyncClient

        if not rows:
            return []

        # Support multiple environment variable names (Render vs Vite local names)
        supabase_url = (
            os.getenv("SUPABASE_URL")
            or os.getenv("VITE_SUPABASE_URL")
            or (str(getattr(settings, "supabase_url", "")) if getattr(settings, "supabase_url", None) else None)
        )

        supabase_key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_SERVICE_KEY")
            or os.getenv("SUPABASE_KEY")
            or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")
            or os.getenv("VITE_SUPABASE_ANON_KEY")
            or (getattr(settings, "supabase_service_key", None))
        )

        # Schema for PostgREST (default public). If your tables live in another schema, set SUPABASE_SCHEMA.
        schema = os.getenv("SUPABASE_SCHEMA") or os.getenv("POSTGREST_SCHEMA") or "public"

        if not supabase_url or not supabase_key:
            logging.error(
                "Supabase credentials missing. SUPABASE_URL=%s, SERVICE_ROLE=%s, SERVICE_KEY=%s, ANON=%s",
                bool(supabase_url),
                bool(os.getenv("SUPABASE_SERVICE_ROLE_KEY")),
                bool(os.getenv("SUPABASE_SERVICE_KEY")),
                bool(os.getenv("VITE_SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_PUBLISHABLE_KEY")),
            )
            raise RuntimeError("Supabase credentials are not set in environment variables")

        supabase_url = str(supabase_url).strip().strip('"').strip("'")
        supabase_key = str(supabase_key).strip().strip('"').strip("'")
        base_url = supabase_url.rstrip("/")
        url = f"{base_url}/rest/v1/{table}"

        headers = {
            "apikey": supabase_key,
            "Authorization": f"Bearer {supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
            "Accept": "application/json",
            "Accept-Profile": schema,
            "Content-Profile": schema,
        }

        try:
            async with AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=rows,
                    params={"on_conflict": conflict},
                )
                # If 404 occurs, include schema/table guidance in logs
                if response.status_code == 404:
                    logging.error(
                        "[MarketAnalysis] Supabase REST returned 404 for %s. URL=%s. Schema=%s. Check table name spelling or schema placement.",
                        table,
                        url,
                        schema,
                    )
                response.raise_for_status()
        except Exception as exc:
            # Attempt to extract response details when available
            message = str(exc)
            try:
                resp = exc.response if hasattr(exc, "response") else None
                if resp is None and 'response' in locals():
                    resp = locals().get('response')
                if resp is not None:
                    message = f"{exc} - status={getattr(resp, 'status_code', None)} body={getattr(resp, 'text', None)}"
            except Exception:
                pass
            logging.error("[MarketAnalysis] Supabase upsert failed for table %s: %s", table, message)
            raise
        return []

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

        # Loại bỏ trường 'ai_note' và gửi payload khớp đúng cột Supabase
        # --- BẮT ĐẦU ĐOẠN CODE CHỐT CHẶN BẢO MẬT & BÓC TÁCH LỖI ---
        import math

        def sanitize_num(v):
            if v is None: return 0.0
            if isinstance(v, (float, int)):
                if math.isnan(v) or math.isinf(v): return 0.0
                return float(v)
            try:
                val = float(v)
                if math.isnan(val) or math.isinf(val): return 0.0
                return val
            except (ValueError, TypeError):
                return 0.0

        def sanitize_str(v, default=""):
            if v is None: return default
            return str(v).strip()

        # 1. Build Payload Scans an toàn tuyệt đối
        scans_to_db = []
        for item in scan_items:
            # FIX: build_scan_record() return 'ticker' not 'symbol'
            symbol_str = sanitize_str(item.get('ticker') or item.get('symbol', 'UNKNOWN'))
            rec_id = sanitize_str(item.get('id') or symbol_str)
            if rec_id == "0" or rec_id == "": rec_id = symbol_str

            scans_to_db.append({
                "id": rec_id,
                "symbol": symbol_str,
                "score": sanitize_num(item.get('score')),
                "price": sanitize_num(item.get('price')),
                "volume": sanitize_num(item.get('volume')),
                "signal": sanitize_str(item.get('signal', 'NONE')),
                "created_at": sanitize_str(item.get('updated_at'))
            })

        scans_to_db, scan_validation_errors = DataValidator.validate_many(MarketScan, scans_to_db)
        if scan_validation_errors:
            logging.warning("[MarketAnalysis] %d invalid market scan records were dropped.", len(scan_validation_errors))
            for err in scan_validation_errors:
                logging.debug("[MarketAnalysis] Scan validation error %s: %s", err["index"], err["errors"])

        # 2. Build Payload Signals an toàn tuyệt đối
        signals_to_db = []
        for item in signal_items:
            symbol_str = sanitize_str(item.get('ticker') or item.get('symbol', 'UNKNOWN'))
            sig_str = sanitize_str(item.get('signal', 'NONE'))
            timestamp = sanitize_str(item.get('updated_at', ''))
            # FIX: Make ID unique per cycle to avoid duplicate conflict
            rec_id = sanitize_str(item.get('id'))
            if rec_id == "0" or rec_id == "" or rec_id == symbol_str:
                # Add timestamp to ID to make it unique per cycle
                import hashlib
                ts_short = timestamp[-8:] if timestamp else "000000"
                rec_id = f"{symbol_str}_{sig_str}_{ts_short}"

            signals_to_db.append({
                "id": rec_id,
                "symbol": symbol_str,
                "signal": sig_str,
                "score": sanitize_num(item.get('score')),
                "price": sanitize_num(item.get('price')),
                "created_at": timestamp
            })

        signals_to_db, signal_validation_errors = DataValidator.validate_many(MarketSignal, signals_to_db)
        if signal_validation_errors:
            logging.warning("[MarketAnalysis] %d invalid market signal records were dropped.", len(signal_validation_errors))
            for err in signal_validation_errors:
                logging.debug("[MarketAnalysis] Signal validation error %s: %s", err["index"], err["errors"])

        # 3. Ghi DB với Try-Catch soi chiếu mọi góc ngách
        try:
            if scans_to_db:
                logging.info("[MarketAnalysis] Writing %d market scans to Supabase", len(scans_to_db))
                await self.supabase_client.upsert_rows("market_scans", scans_to_db, conflict="id")
            else:
                logging.warning("[MarketAnalysis] No scans data to write (Empty Payload).")
        except Exception as e:
            error_details = str(e)
            # Bóc tách phản hồi ẩn từ Supabase (nếu có)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details += f" | Supabase Details: {e.response.text}"
                except Exception:
                    pass
            logging.error(f"[FATAL DB ERROR] Market Scans Upsert Failed: {error_details}")
            if scans_to_db: logging.error(f"Sample Payload that caused error: {scans_to_db[0]}")

        try:
            if signals_to_db:
                logging.info("[MarketAnalysis] Writing %d market signals to Supabase", len(signals_to_db))
                await self.supabase_client.upsert_rows("market_signals", signals_to_db, conflict="id")
        except Exception as e:
            error_details = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_details += f" | Supabase Details: {e.response.text}"
                except Exception:
                    pass
            logging.error(f"[FATAL DB ERROR] Market Signals Upsert Failed: {error_details}")

            return scan_items

    async def fetch_binance_tickers(self) -> list[dict]:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get("https://api.binance.com/api/v3/ticker/24hr")
            response.raise_for_status()
            data = response.json()[:500]

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
            "price": round(scan["price"], 8),
            "entry_price": entry_price,
            "score": scan["score"],
            "signal": scan["signal"],
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
