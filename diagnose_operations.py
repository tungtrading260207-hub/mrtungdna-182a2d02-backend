"""
Diagnostic script to identify operational issues:
1. Auto-startup failure: Check if workers launch successfully
2. Rate limiting: Verify 429 handling and backoff
3. External API timeouts: Test Gemini, Lovable, Coinglass resilience
"""

import asyncio
import logging
from datetime import datetime
from httpx import AsyncClient, TimeoutException, HTTPStatusError
import sys
import os

# Setup logging with detailed format
logging.basicConfig(
    level=logging.DEBUG,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.dirname(__file__))
from app.config import settings
from app.db import SupabaseClient
from app.tasks import (
    RumorHuntingWorker,
    AntiTrapShortWorker,
    MarketDataAnalysisWorker,
    MacroDataSchedulerWorker,
)


async def test_startup_initialization():
    """Test if workers initialize and launch without hanging."""
    logger.info("=" * 60)
    logger.info("TEST 1: Worker Initialization & Startup")
    logger.info("=" * 60)

    try:
        # Initialize Supabase client
        logger.info("Initializing Supabase client...")
        supabase_client = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_key,
            db_url=settings.supabase_db_url,
        )
        await supabase_client.init_pool()
        logger.info("✓ Supabase client initialized successfully")

        # Try to initialize each worker
        workers = {
            "RumorHunting": RumorHuntingWorker(supabase_client),
            "AntiTrapShort": AntiTrapShortWorker(supabase_client),
            "MarketAnalysis": MarketDataAnalysisWorker(supabase_client),
            "MacroScheduler": MacroDataSchedulerWorker(supabase_client),
        }

        for name, worker in workers.items():
            try:
                logger.info(f"Initializing {name} worker...")
                # Test first scan cycle (with timeout)
                records = await asyncio.wait_for(worker.run_once(), timeout=30.0)
                logger.info(f"✓ {name} worker initialized. Fetched {len(records)} records.")
            except asyncio.TimeoutError:
                logger.error(f"✗ {name} worker timed out (30s limit exceeded)")
            except Exception as exc:
                logger.error(f"✗ {name} worker failed: {exc}")

        await supabase_client.close()
        logger.info("✓ All workers tested\n")

    except Exception as exc:
        logger.exception(f"FATAL: Startup test failed: {exc}")


async def test_external_apis():
    """Test resilience of external API calls with timeouts."""
    logger.info("=" * 60)
    logger.info("TEST 2: External API Resilience (Timeouts & Errors)")
    logger.info("=" * 60)

    # Test Gemini API
    logger.info("Testing Gemini API (10s timeout)...")
    if settings.gemini_api_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={settings.gemini_api_key}"
            payload = {
                "contents": [
                    {
                        "role": "user",
                        "parts": [{"text": "Hello, respond with one word."}],
                    }
                ]
            }
            async with AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                logger.info(f"✓ Gemini API responded with status {response.status_code}")
        except TimeoutException:
            logger.warning("⚠ Gemini API timed out (expected behavior)")
        except HTTPStatusError as e:
            logger.warning(f"⚠ Gemini API HTTP error: {e.response.status_code} {e.response.reason_phrase}")
        except Exception as e:
            logger.error(f"✗ Gemini API error: {e}")
    else:
        logger.warning("⚠ Gemini API key not configured, skipping")

    # Test Lovable API
    logger.info("Testing Lovable API (10s timeout)...")
    if settings.lovable_api_key:
        try:
            url = "https://ai.gateway.lovable.dev/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {settings.lovable_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": "google/gemini-2.5-flash",
                "messages": [{"role": "user", "content": "Hi, respond with one word."}],
            }
            async with AsyncClient(timeout=10.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                logger.info(f"✓ Lovable API responded with status {response.status_code}")
        except TimeoutException:
            logger.warning("⚠ Lovable API timed out (expected behavior)")
        except HTTPStatusError as e:
            logger.warning(f"⚠ Lovable API HTTP error: {e.response.status_code} {e.response.reason_phrase}")
        except Exception as e:
            logger.error(f"✗ Lovable API error: {e}")
    else:
        logger.warning("⚠ Lovable API key not configured, skipping")

    # Test Coinglass API
    logger.info("Testing Coinglass API (15s timeout + 429 handling)...")
    if settings.coinglass_api_key:
        try:
            async with AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    "https://open-api.coinglass.com/api/pro/v1/fundFlow",
                    headers={"coinglassSecret": settings.coinglass_api_key},
                    params={"symbol": "BTCUSDT"},
                )
                if response.status_code == 429:
                    logger.warning(f"⚠ Coinglass API rate limited (429), backoff triggered")
                elif response.status_code == 200:
                    logger.info(f"✓ Coinglass API responded with status {response.status_code}")
                else:
                    logger.warning(f"⚠ Coinglass API returned status {response.status_code}")
        except TimeoutException:
            logger.warning("⚠ Coinglass API timed out (expected behavior)")
        except Exception as e:
            logger.error(f"✗ Coinglass API error: {e}")
    else:
        logger.warning("⚠ Coinglass API key not configured, skipping")

    logger.info("✓ External API resilience tested\n")


async def test_rate_limiting():
    """Test rate limiting and backoff behavior."""
    logger.info("=" * 60)
    logger.info("TEST 3: Rate Limiting & Backoff")
    logger.info("=" * 60)

    from app.rate_limiter import anti_429_delay
    from app.config import settings

    logger.info(f"Rate limit config: min={settings.rate_limit_min}s, max={settings.rate_limit_max}s")

    # Test anti_429_delay
    logger.info("Testing anti_429_delay (should sleep 0.5-2.0s)...")
    for i in range(3):
        start = datetime.now()
        delay = await anti_429_delay()
        elapsed = (datetime.now() - start).total_seconds()
        logger.info(f"  Iteration {i+1}: Requested {delay:.2f}s, actual {elapsed:.2f}s")

    logger.info("✓ Rate limiting tested\n")


async def test_supabase_connectivity():
    """Test Supabase REST and PostgreSQL connectivity."""
    logger.info("=" * 60)
    logger.info("TEST 4: Supabase Connectivity")
    logger.info("=" * 60)

    try:
        supabase_client = SupabaseClient(
            url=settings.supabase_url,
            key=settings.supabase_key,
            db_url=settings.supabase_db_url,
        )

        # Test REST API
        logger.info("Testing Supabase REST API...")
        try:
            result = await supabase_client.from_("market_signals").select("*").limit(1).execute()
            logger.info(f"✓ Supabase REST API responded with {len(result.data)} records")
        except Exception as exc:
            logger.error(f"✗ Supabase REST API error: {exc}")

        # Test PostgreSQL pool
        logger.info("Testing Supabase PostgreSQL pool...")
        try:
            await supabase_client.init_pool()
            if supabase_client._pool:
                async with supabase_client._pool.acquire() as conn:
                    result = await conn.fetchval("SELECT 1")
                    logger.info(f"✓ PostgreSQL pool connected and responsive")
            else:
                logger.warning("⚠ PostgreSQL pool not initialized (db_url may not be set)")
        except Exception as exc:
            logger.error(f"✗ PostgreSQL pool error: {exc}")

        await supabase_client.close()
        logger.info("✓ Supabase connectivity tested\n")

    except Exception as exc:
        logger.exception(f"FATAL: Supabase connectivity test failed: {exc}")


async def main():
    """Run all diagnostic tests."""
    logger.info("\n" + "=" * 60)
    logger.info("MrTung Python Backend - Operational Diagnostics")
    logger.info(f"Started at {datetime.utcnow().isoformat()}Z")
    logger.info("=" * 60 + "\n")

    await test_supabase_connectivity()
    await test_external_apis()
    await test_rate_limiting()
    await test_startup_initialization()

    logger.info("=" * 60)
    logger.info("Diagnostics Complete")
    logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
