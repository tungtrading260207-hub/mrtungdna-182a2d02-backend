import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from httpx import AsyncClient
from ..config import settings
from ..db import SupabaseClient
from . import WorkerBase


class VietnamStockWorker(WorkerBase):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 15):
        super().__init__(supabase_client, interval_seconds)
        self.engine = self
        try:
            self.local_zone = ZoneInfo(settings.timezone)
        except Exception:
            self.local_zone = timezone.utc

    async def start_loop(self):
        while True:
            now = datetime.now(self.local_zone)
            if self._is_trading_hours(now):
                await self._run_cycle()
                await asyncio.sleep(self.interval_seconds)
            else:
                await asyncio.sleep(300)

    async def scan(self) -> list[dict]:
        if not settings.dainam_api_url or not settings.dainam_api_key:
            logging.warning("[VietnamStockWorker] DAINAM_API_URL or DAINAM_API_KEY is not configured.")
            return []

        raw_data = await self.fetch_vietnam_stock_data()
        records = self.normalize_records(raw_data)
        if not records:
            return []

        await self.supabase_client.upsert_rows("vn_market_scans", records, conflict="id")
        return records

    async def fetch_vietnam_stock_data(self) -> dict | list[dict] | None:
        headers = {
            "Authorization": f"Bearer {settings.dainam_api_key}",
            "Content-Type": "application/json",
        }

        async with AsyncClient(timeout=30.0) as client:
            response = await client.get(settings.dainam_api_url, headers=headers)
            response.raise_for_status()
            return response.json()

    def normalize_records(self, payload: dict | list[dict] | None) -> list[dict]:
        if payload is None:
            return []

        if isinstance(payload, dict):
            items = payload.get("data") or payload.get("items") or payload.get("results") or payload.get("stocks") or [payload]
        else:
            items = payload

        if not isinstance(items, list):
            items = [items]

        records: list[dict] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol") or item.get("code") or item.get("ticker") or item.get("id") or f"vn_{idx}"
            record = {**item}
            record["id"] = symbol
            record["source"] = "DaiNam_DNS"
            record["updated_at"] = datetime.now(timezone.utc).isoformat()
            records.append(record)

        return records

    def _is_trading_hours(self, now: datetime) -> bool:
        return now.weekday() < 5 and now.hour >= 9 and now.hour < 15
