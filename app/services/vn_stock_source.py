import logging
from httpx import AsyncClient
from ..config import settings


class VNStockSource:
    def __init__(self):
        self.base_url = settings.vn_stock_api_url
        self.api_key = settings.vn_stock_api_key
        self.source_name = settings.vn_stock_source or "DNS"

    async def fetch_symbol_flow(self, symbol: str) -> dict | None:
        if not self.base_url:
            logging.debug("[VNStockSource] No VN stock API URL configured.")
            return None

        async with AsyncClient(timeout=20.0) as client:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                response = await client.get(
                    f"{self.base_url.rstrip('/')}/flow",
                    params={"symbol": symbol},
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except Exception as err:
                logging.warning("[VNStockSource] Failed to fetch VN symbol %s: %s", symbol, err)
                return None

    async def fetch_market_snapshot(self) -> dict | None:
        if not self.base_url:
            logging.debug("[VNStockSource] No VN stock API URL configured.")
            return None

        async with AsyncClient(timeout=20.0) as client:
            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                response = await client.get(
                    f"{self.base_url.rstrip('/')}/snapshot",
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except Exception as err:
                logging.warning("[VNStockSource] Failed to fetch VN market snapshot: %s", err)
                return None
