import asyncio
import logging
from dataclasses import dataclass
from time import perf_counter
from datetime import datetime, timezone
from app.services.rumor_hunting import AdvancedRumorHunting
from app.services.anti_trap_short import AntiTrapShortEngine
from app.services.market_analysis import MarketAnalysisEngine
from app.services.macro_scheduler import MacroDataScheduler
from app.db import SupabaseClient


@dataclass
class WorkerStatus:
    name: str
    last_run: str | None = None
    last_success: bool | None = None
    last_error: str | None = None
    last_duration: float | None = None
    iteration: int = 0
    total_records: int = 0


class WorkerBase:
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 900):
        self.supabase_client = supabase_client
        self.interval_seconds = interval_seconds
        self.engine = None
        self.status = WorkerStatus(name=self.__class__.__name__)

    async def start_loop(self):
        while True:
            await self._run_cycle()
            await asyncio.sleep(self.interval_seconds)

    async def run_once(self):
        return await self._run_cycle()

    async def _run_cycle(self):
        self.status.iteration += 1
        self.status.last_run = datetime.now(timezone.utc).isoformat()
        start = perf_counter()

        try:
            records = await self.engine.scan()
            self.status.last_success = True
            self.status.last_error = None
            self.status.total_records = len(records)
            return records
        except Exception as exc:
            self.status.last_success = False
            self.status.last_error = str(exc)
            logging.exception("[%s] Failed to complete scan: %s", self.status.name, exc)
            return []
        finally:
            self.status.last_duration = perf_counter() - start


class RumorHuntingWorker(WorkerBase):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 900):
        super().__init__(supabase_client, interval_seconds)
        self.engine = AdvancedRumorHunting(self.supabase_client)


class AntiTrapShortWorker(WorkerBase):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 1800):
        super().__init__(supabase_client, interval_seconds)
        self.engine = AntiTrapShortEngine(self.supabase_client)


class MarketDataAnalysisWorker(WorkerBase):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 1800):
        super().__init__(supabase_client, interval_seconds)
        self.engine = MarketAnalysisEngine(self.supabase_client)


class MacroDataSchedulerWorker(WorkerBase):
    def __init__(self, supabase_client: SupabaseClient, interval_seconds: int = 3600):
        super().__init__(supabase_client, interval_seconds)
        self.engine = MacroDataScheduler(self.supabase_client)

    async def start_loop(self):
        while True:
            await self._run_cycle()
            await asyncio.sleep(3600)


from .vietnam_stock_worker import VietnamStockWorker
