import logging
from httpx import AsyncClient
from ..config import settings
from .no_api_scrapers import NoApiScraper


class VNStockSource:
    def __init__(self):
        self.base_url = settings.vn_stock_api_url
        self.api_key = settings.vn_stock_api_key
        self.source_name = settings.vn_stock_source or "DNS"

    async def fetch_symbol_flow(self, symbol: str) -> dict | None:
        if self.source_name == settings.dns_source_label or self.source_name == "DNS":
            return {"source": settings.dns_source_label}

        if self.base_url:
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
        
        logging.info(f"[VNStockSource] 🚨 API chính lỗi/thiếu! Kích hoạt cơ chế Fallback No-API cho mã {symbol}")
        scraper = NoApiScraper()
        fallback_data = await scraper.fetch_tcbs_finance(symbol)
        return self.process_fallback_data(fallback_data)

    def process_fallback_data(self, data: dict) -> dict:
        """Chuẩn hóa dữ liệu TCBS sang định dạng mong muốn"""
        if not data:
            return {}
        # Đảm bảo schema an toàn (Mockup data tuỳ theo thực tế payload của TCBS)
        return {
            "source": "TCBS_Fallback",
            "netFlow": data.get("netRevenue") or data.get("revenue") or 0,
            "raw_fallback": data
        }

    async def fetch_market_snapshot(self) -> dict | None:
        if self.source_name == settings.dns_source_label or self.source_name == "DNS":
            return {"source": settings.dns_source_label}

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
