import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from httpx import AsyncClient
from ..config import settings
from ..db import SupabaseClient
from .no_api_scrapers import NoApiScraper
from .no_api_scrapers import NoApiScraper


class MacroDataScheduler:
    def __init__(self, supabase_client: SupabaseClient):
        self.supabase_client = supabase_client
        self.last_fred_date: str | None = None
        self.scraper = NoApiScraper()
        try:
            self.local_zone = ZoneInfo(settings.timezone)
        except Exception:
            self.local_zone = timezone.utc
        self._cache: dict[str, tuple[dict, datetime]] = {}

    async def scan(self) -> list[dict]:
        records: list[dict] = []

        coingecko = await self.fetch_coingecko_data()
        if coingecko:
            records.append(coingecko)

        lunarcrush = await self.fetch_lunarcrush_data()
        if lunarcrush:
            records.append(lunarcrush)

        alpha_vantage = await self.fetch_alpha_vantage_data()
        if alpha_vantage:
            records.append(alpha_vantage)

        tv_macro = await self.fetch_tradingview_macro_data()
        if tv_macro:
            records.extend(tv_macro)

        fred = await self.fetch_fred_data_if_due()
        if fred:
            records.append(fred)

        if records:
            logging.info("[MacroDataScheduler] Writing %d records to Supabase.", len(records))
            await self.supabase_client.upsert_rows("macro_sentiment", records, conflict="id")

        return records

    async def fetch_coingecko_data(self) -> dict | None:
        cache_key = "coingecko_global"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        headers = {}
        if settings.coingecko_api_key:
            headers["x-cg-pro-api-key"] = settings.coingecko_api_key

        async with AsyncClient(timeout=30.0) as client:
            response = await client.get("https://api.coingecko.com/api/v3/global", headers=headers)
            response.raise_for_status()
            data = response.json()

        record = {
            "id": cache_key,
            "source": "CoinGecko",
            "metric": "global_crypto",
            "value": data.get("data", {}),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "CoinGecko global crypto market snapshot.",
        }
        self._set_cache(cache_key, record, settings.cache_time_realtime_slow)
        return record

    async def fetch_lunarcrush_data(self) -> dict | None:
        if not settings.lunarcrush_api_key:
            return None

        cache_key = "lunarcrush_assets"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        async with AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.lunarcrush.com/v2",
                params={"data": "assets", "key": settings.lunarcrush_api_key, "limit": 10},
            )
            response.raise_for_status()
            data = response.json()

        record = {
            "id": cache_key,
            "source": "LunarCrush",
            "metric": "asset_sentiment",
            "value": data.get("data", []),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "LunarCrush sentiment data for top assets.",
        }
        self._set_cache(cache_key, record, settings.cache_time_social)
        return record

    async def fetch_alpha_vantage_data(self) -> dict | None:
        if not settings.alpha_vantage_api_key:
            return None

        cache_key = "alpha_vantage_spy"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        async with AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://www.alphavantage.co/query",
                params={
                    "function": "GLOBAL_QUOTE",
                    "symbol": "SPY",
                    "apikey": settings.alpha_vantage_api_key,
                },
            )
            response.raise_for_status()
            data = response.json()

        quote = data.get("Global Quote") or {}
        record = {
            "id": cache_key,
            "source": "AlphaVantage",
            "metric": "spy_global_quote",
            "value": {
                "symbol": quote.get("01. symbol"),
                "price": quote.get("05. price"),
                "change_percent": quote.get("10. change percent"),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": "Alpha Vantage global quote for SPY.",
        }
        self._set_cache(cache_key, record, settings.cache_time_macro)
        return record

    async def fetch_tradingview_macro_data(self) -> list[dict]:
        cache_key = "tv_macro_data"
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        # Fetch Gold, DXY, SPY via TradingView Scanner
        payload = await self.scraper.scan_tradingview(
            markets=["america", "cfd"],
            tickers=["FX_IDC:XAUUSD", "CAPITALCOM:DXY", "AMEX:SPY"]
        )
        
        records = []
        if payload and "data" in payload:
            for item in payload["data"]:
                sym = item.get("s", "")
                d = item.get("d", [])
                if len(d) >= 3:
                    records.append({
                        "id": f"tv_macro_{sym}",
                        "source": "TradingView",
                        "metric": f"macro_{sym}",
                        "value": {
                            "symbol": sym,
                            "price": d[0], # close
                            "volume": d[1], # volume
                            "change_percent": d[2], # change
                        },
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                        "notes": "No-API TradingView macro scan."
                    })
        
        if records:
            # We cache it as a list in the cache dict. The _set_cache expects a record dict but we can store list too.
            self._set_cache(cache_key, records, settings.cache_time_realtime_slow) # Update quickly like every 5m
            return records
        return []

    async def fetch_fred_data_if_due(self) -> dict | None:
        if not settings.fred_api_key:
            return None

        now = datetime.now(self.local_zone)
        today_str = now.date().isoformat()
        if now.hour != 8 or self.last_fred_date == today_str:
            return None

        record = await self.fetch_fred_series("GDP")
        if record:
            self.last_fred_date = today_str
        return record

    async def fetch_fred_series(self, series_id: str) -> dict | None:
        async with AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": settings.fred_api_key,
                    "file_type": "json",
                    "limit": 5,
                },
            )
            response.raise_for_status()
            data = response.json()

        observations = data.get("observations", [])
        if not observations:
            return None

        latest = observations[-1]
        return {
            "id": f"fred_{series_id.lower()}_{latest.get('date')}",
            "source": "FRED",
            "metric": f"fred_{series_id.lower()}",
            "value": {
                "date": latest.get("date"),
                "value": latest.get("value"),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "notes": f"FRED {series_id} observation fetched once daily at 08:00 {settings.timezone}.",
        }

    def _get_cached(self, key: str) -> dict | None:
        entry = self._cache.get(key)
        if not entry:
            return None
        record, expiry = entry
        if datetime.now(timezone.utc) >= expiry:
            del self._cache[key]
            return None
        return record

    def _set_cache(self, key: str, record: dict, ttl_ms: int) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(milliseconds=ttl_ms)
        self._cache[key] = (record, expiry)
