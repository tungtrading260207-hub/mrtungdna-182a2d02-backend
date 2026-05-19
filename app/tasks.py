import asyncio
import logging
from .services.rumor_hunting import AdvancedRumorHunting
from .services.anti_trap_short import AntiTrapShortEngine
from .db import SupabaseClient


class RumorHuntingWorker:
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 900):
        self.supabase_client = supabase_client
        self.interval_seconds = interval_seconds
        self.engine = AdvancedRumorHunting(self.supabase_client)

    async def start_loop(self):
        while True:
            try:
                logging.info("[RumorHunting] Starting scan cycle.")
                await self.engine.scan()
                logging.info("[RumorHunting] Scan cycle completed.")
            except Exception as exc:
                logging.exception("[RumorHunting] Failed to complete scan: %s", exc)
            await asyncio.sleep(self.interval_seconds)


class AntiTrapShortWorker:
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 1800):
        self.supabase_client = supabase_client
        self.interval_seconds = interval_seconds
        self.engine = AntiTrapShortEngine(self.supabase_client)

    async def start_loop(self):
        while True:
            try:
                logging.info("[AntiTrapShort] Starting scan cycle.")
                await self.engine.scan()
                logging.info("[AntiTrapShort] Scan cycle completed.")
            except Exception as exc:
                logging.exception("[AntiTrapShort] Failed to complete scan: %s", exc)
            await asyncio.sleep(self.interval_seconds)
