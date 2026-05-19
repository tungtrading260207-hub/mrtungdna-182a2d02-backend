import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI
from app.config import settings
from app.db import SupabaseClient
from app.tasks import RumorHuntingWorker, AntiTrapShortWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="Mr Tung Python Quant Engine",
    description="Backend worker for advanced rumor hunting and anti-trap short setup.",
    version="0.1.0",
)

supabase_client = SupabaseClient()
worker_tasks: list[asyncio.Task] = []

@app.on_event("startup")
async def startup_event():
    logging.info("Starting Mr Tung Python FastAPI worker...")
    await supabase_client.init_pool()
    rumor_worker = RumorHuntingWorker(supabase_client)
    anti_short_worker = AntiTrapShortWorker(supabase_client)
    worker_tasks.append(asyncio.create_task(rumor_worker.start_loop()))
    worker_tasks.append(asyncio.create_task(anti_short_worker.start_loop()))
    logging.info("Background workers launched.")

@app.on_event("shutdown")
async def shutdown_event():
    logging.info("Shutting down background workers...")
    for task in worker_tasks:
        task.cancel()
    await supabase_client.close()

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "Mr Tung Python Quant Engine",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "supabase_url": str(settings.supabase_url),
    }
