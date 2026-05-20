import logging
from datetime import datetime, timezone
from httpx import AsyncClient
from .ai_analysis import AIAnalyzer
from ..config import settings
from ..db import SupabaseClient


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

        logging.info("[MarketAnalysis] Writing %d market scans", len(scan_items))
        await self.supabase_client.upsert_rows("market_scans", scan_items, conflict="id")

        logging.info("[MarketAnalysis] Writing %d market signals", len(signal_items))
        await self.supabase_client.upsert_rows("market_signals", signal_items, conflict="id")

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
