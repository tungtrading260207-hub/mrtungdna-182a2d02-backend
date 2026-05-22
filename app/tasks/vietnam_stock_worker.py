import asyncio
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from httpx import AsyncClient
from ..config import settings
from ..db import SupabaseClient
from core.worker import BaseWorker
from core.schemas.stock_schema import VNStockProfile


class VietnamStockWorker(BaseWorker):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 15):
        super().__init__(supabase_client, schema=VNStockProfile, table_name=VNStockProfile.table_name, conflict="id")
        self.interval_seconds = interval_seconds
        try:
            self.local_zone = ZoneInfo(settings.timezone)
        except Exception:
            self.local_zone = timezone.utc
        try:
            self.local_zone = ZoneInfo(settings.timezone)
        except Exception:
            self.local_zone = timezone.utc

    async def start_loop(self):
        while True:
            now = datetime.now(self.local_zone)
            if self._is_trading_hours(now):
                try:
                    await self.run_once()
                except Exception as exc:
                    logging.exception("[VietnamStockWorker] Fetch/load cycle failed: %s", exc)
                await asyncio.sleep(self.interval_seconds)
            else:
                await asyncio.sleep(300)

    async def scan(self) -> list[dict]:
        if not settings.dainam_api_url or not settings.dainam_api_key:
            logging.warning("[VietnamStockWorker] DAINAM_API_URL or DAINAM_API_KEY is not configured.")
            return []

        return await self.run_once()

    async def fetch_vietnam_stock_data(self) -> dict | list[dict] | None:
        api_url = str(settings.dainam_api_url).strip().rstrip("/")
        endpoints = []

        if settings.dainam_api_path:
            endpoints.append(f"{api_url}/{str(settings.dainam_api_path).strip().lstrip('/')}")
        else:
            endpoints.extend([
                api_url,
                f"{api_url}/market/symbols",
                f"{api_url}/symbols",
                f"{api_url}/market/tickers",
                f"{api_url}/tickers",
            ])

        headers = {
            "Authorization": f"Bearer {settings.dainam_api_key}",
            "Content-Type": "application/json",
        }
        if settings.dainam_api_secret:
            headers["X-API-SECRET"] = settings.dainam_api_secret

        async with AsyncClient(timeout=30.0) as client:
            last_error = None
            for endpoint in endpoints:
                try:
                    response = await client.get(endpoint, headers=headers)
                    if response.status_code == 404:
                        logging.debug("[VietnamStockWorker] Endpoint not found: %s", endpoint)
                        continue
                    response.raise_for_status()
                    return response.json()
                except Exception as exc:
                    last_error = exc
                    logging.debug("[VietnamStockWorker] Failed endpoint %s: %s", endpoint, exc)
            if last_error:
                raise last_error
            return None

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
            record = {
                "id": symbol,
                "symbol": symbol,
                "source": settings.dns_source_label,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "payload": item,
            }
            records.append(record)

        return records

    def _is_trading_hours(self, now: datetime) -> bool:
        return now.weekday() < 5 and now.hour >= 9 and now.hour < 15
