import asyncio
from app.services.no_api_scrapers import NoApiScraper

async def test():
    s = NoApiScraper()
    res = await s.scan_tradingview(['crypto'], ['BINANCE:BTCUSDT'])
    print(res)

if __name__ == '__main__':
    asyncio.run(test())
