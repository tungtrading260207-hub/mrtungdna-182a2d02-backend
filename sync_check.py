import asyncio
import logging
from app.config import settings
from app.db import SupabaseClient
from core.schema_sync import SchemaSyncChecker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


async def main() -> None:
    supabase_client = SupabaseClient()
    await supabase_client.init_pool()

    checker = SchemaSyncChecker(
        supabase_client=supabase_client,
        dashboard_url=settings.dashboard_alert_url,
        dashboard_api_key=settings.dashboard_alert_api_key,
        interval_seconds=settings.schema_sync_interval_seconds,
    )

    result = await checker.run_once()
    logging.info("Schema sync result: %s", result)
    await supabase_client.close()


if __name__ == "__main__":
    asyncio.run(main())
