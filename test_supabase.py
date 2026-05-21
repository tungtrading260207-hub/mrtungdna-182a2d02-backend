import asyncio
import os
import httpx
from app.config import settings

async def main():
    supabase_url = str(settings.supabase_url).rstrip("/")
    api_key = settings.supabase_service_key
    
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    async with httpx.AsyncClient() as client:
        # Requesting table list or checking if we can insert to trading_logs
        res = await client.get(f"{supabase_url}/rest/v1/", headers=headers)
        print(res.status_code)
        if res.status_code == 200:
            print(res.json())

if __name__ == "__main__":
    asyncio.run(main())
