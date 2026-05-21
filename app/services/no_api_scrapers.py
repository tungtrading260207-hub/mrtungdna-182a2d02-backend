import httpx
import asyncio
import websockets
import json
import logging
from typing import Dict, List

# Global cache for websocket pool
_global_ws_cache: Dict[str, dict] = {}

class NoApiScraper:
    def __init__(self):
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://www.tradingview.com"
        }
        self.local_cache = _global_ws_cache

    async def scan_tradingview(self, markets: List[str], tickers: List[str]) -> dict:
        """Fetch multiple technical indicators (RSI, MFI, HMA, Vol) in 1 Request"""
        url = "https://scanner.tradingview.com/global/scan"
        payload = {
            "markets": markets,
            "symbols": {"tickers": tickers, "query": {"types": []}},
            "columns": ["close", "volume", "change", "RSI", "MoneyFlow", "HullMA9", "Recommend.All"]
        }
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=15.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logging.warning(f"[NoApiScraper] TradingView Scanner Error: {e}")
        return {}

    async def fetch_tcbs_finance(self, symbol: str) -> dict:
        """Fetch basic finance data from TCBS as fallback"""
        url = f"https://apipublish.tcbs.com.vn/api/v1/ticker-profile/finance-index?ticker={symbol}"
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=10.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logging.warning(f"[NoApiScraper] TCBS Scraper Error for {symbol}: {e}")
        return {}

    async def start_binance_ws_pool(self):
        """Websocket Pool running continuously, caching data into RAM"""
        url = "wss://stream.binance.com:9443/ws/!ticker@arr"
        while True:
            try:
                async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
                    logging.info("[NoApiScraper] Binance Public WS Pool Connected.")
                    while True:
                        msg = await ws.recv()
                        data = json.loads(msg)
                        for ticker in data:
                            sym = ticker.get('s')
                            if not sym:
                                continue
                            try:
                                self.local_cache[sym] = {
                                    "price": float(ticker.get('c', 0)),
                                    "volume": float(ticker.get('v', 0)),
                                    "change": float(ticker.get('P', 0)),
                                    "quote_volume": float(ticker.get('q', 0))
                                }
                            except (ValueError, TypeError):
                                pass
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.warning(f"[NoApiScraper] WS Connection Lost: {e}. Reconnecting in 5s...")
                await asyncio.sleep(5)
