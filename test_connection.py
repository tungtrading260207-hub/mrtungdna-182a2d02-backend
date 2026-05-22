import asyncio
import logging
from typing import Any

import httpx
from websockets import connect

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def test_supabase_from() -> dict[str, Any]:
    try:
        from supabase import create_client
    except ImportError as exc:
        raise RuntimeError(
            "Supabase client library is not installed. Install it with `pip install supabase` "
            "or test connection via direct REST if you prefer."
        ) from exc

    url = str(settings.supabase_url).strip().rstrip("/")
    key = settings.supabase_service_key
    if not url or not key:
        raise RuntimeError("SUPABASE_URL or SUPABASE_SERVICE_KEY is not configured.")

    client = create_client(url, key)
    table_name = "market_signals"
    result = client.from_(table_name).select("id").limit(1).execute()

    if hasattr(result, "status_code") and result.status_code not in {200, 206}:
        raise RuntimeError(
            f"Supabase .from_() request failed with status {result.status_code}: {result.response.text if hasattr(result, 'response') else result}"
        )

    if hasattr(result, "error") and result.error:
        raise RuntimeError(f"Supabase .from_() returned error: {result.error}")

    return {"table": table_name, "records": getattr(result, "data", None)}


async def test_http_endpoint() -> dict[str, Any]:
    url = "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT"
    timeout = httpx.Timeout(10.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url)
        response.raise_for_status()
        payload = response.json()

    if not isinstance(payload, dict) or payload.get("symbol") != "BTCUSDT":
        raise RuntimeError("HTTP endpoint returned unexpected payload.")

    return {"url": url, "status_code": response.status_code, "symbol": payload.get("symbol")}


async def test_websocket_connection() -> dict[str, Any]:
    uri = "wss://stream.binance.com:9443/ws/!ticker@arr"
    async with connect(uri) as websocket:
        message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        return {"uri": uri, "received_message_type": type(message).__name__, "sample": str(message)[:200]}


async def main() -> None:
    results = {}
    try:
        logging.info("[test_connection] Running Supabase .from_() check...")
        results["supabase"] = await test_supabase_from()
        logging.info("[test_connection] Supabase .from_() check passed.")
    except Exception as exc:
        logging.error("[test_connection] Supabase .from_() check failed: %s", exc)
        raise

    try:
        logging.info("[test_connection] Running HTTP endpoint check...")
        results["http_endpoint"] = await test_http_endpoint()
        logging.info("[test_connection] HTTP endpoint check passed.")
    except Exception as exc:
        logging.error("[test_connection] HTTP endpoint check failed: %s", exc)
        raise

    try:
        logging.info("[test_connection] Running WebSocket connection check...")
        results["websocket"] = await test_websocket_connection()
        logging.info("[test_connection] WebSocket connection check passed.")
    except Exception as exc:
        logging.error("[test_connection] WebSocket connection check failed: %s", exc)
        raise

    logging.info("[test_connection] All checks passed: %s", results)


if __name__ == "__main__":
    asyncio.run(main())
