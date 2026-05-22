import asyncio
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException
from app.config import settings
from app.db import SupabaseClient
from app.tasks import RumorHuntingWorker, AntiTrapShortWorker, MarketDataAnalysisWorker, MacroDataSchedulerWorker, VNStockWorker
from app.services.no_api_scrapers import NoApiScraper
from core.schema_sync import SchemaSyncChecker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(
    title="Mr Tung Python Quant Engine",
    description="Backend worker for advanced rumor hunting and anti-trap short setup.",
    version="0.1.0",
)

supabase_client = SupabaseClient()
worker_tasks: list[asyncio.Task] = []
rumor_worker: RumorHuntingWorker | None = None
anti_short_worker: AntiTrapShortWorker | None = None
analysis_worker: MarketDataAnalysisWorker | None = None
macro_worker: MacroDataSchedulerWorker | None = None
vn_stock_worker: VNStockWorker | None = None
schema_sync_worker: SchemaSyncChecker | None = None
no_api_scraper = NoApiScraper()


# ==================== ĐOẠN THÊM MỚI VÀO ĐÂY ====================
@app.get("/")
async def read_root():
    return {
        "status": "ok",
        "message": "Mr Tung Python Quant Engine is running smoothly!",
        "uptime_robot_status": "connected"
    }
# =============================================================


@app.on_event("startup")
async def startup_event():
    global rumor_worker, anti_short_worker, analysis_worker, macro_worker, vn_stock_worker, schema_sync_worker
    try:
        logging.info("Starting Mr Tung Python FastAPI worker...")
        await supabase_client.init_pool()
        rumor_worker = RumorHuntingWorker(supabase_client)
        anti_short_worker = AntiTrapShortWorker(supabase_client)
        analysis_worker = MarketDataAnalysisWorker(supabase_client)
        macro_worker = MacroDataSchedulerWorker(supabase_client)
        vn_stock_worker = VNStockWorker(supabase_client)
        worker_tasks.append(asyncio.create_task(rumor_worker.start_loop()))
        worker_tasks.append(asyncio.create_task(anti_short_worker.start_loop()))
        worker_tasks.append(asyncio.create_task(analysis_worker.start_loop()))
        worker_tasks.append(asyncio.create_task(macro_worker.start_loop()))
        worker_tasks.append(asyncio.create_task(vn_stock_worker.start_loop()))
        if supabase_client._pool:
            schema_sync_worker = SchemaSyncChecker(
                supabase_client=supabase_client,
                dashboard_url=settings.dashboard_alert_url,
                dashboard_api_key=settings.dashboard_alert_api_key,
                interval_seconds=settings.schema_sync_interval_seconds,
            )
            worker_tasks.append(asyncio.create_task(schema_sync_worker.start_loop()))
        else:
            logging.warning("[main] Schema sync worker disabled because SUPABASE_DB_URL is not configured.")
        worker_tasks.append(asyncio.create_task(no_api_scraper.start_binance_ws_pool()))
        logging.info("Background workers launched.")
    except Exception as exc:
        logging.exception("[main] FATAL: Startup failed: %s", exc)
        raise

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


@app.post("/trigger/{task_name}")
async def trigger_task(task_name: str):
    if task_name == "rumor":
        worker = rumor_worker
    elif task_name == "anti_short":
        worker = anti_short_worker
    elif task_name == "market":
        worker = analysis_worker
    elif task_name == "macro":
        worker = macro_worker
    elif task_name == "vn_stock":
        worker = vn_stock_worker
    else:
        raise HTTPException(status_code=404, detail="Unknown task")

    if worker is None:
        raise HTTPException(status_code=503, detail="Worker not initialized")

    records = await worker.run_once()
    return {
        "status": "ok",
        "task": task_name,
        "records_written": len(records),
        "worker_status": worker.status.__dict__,
    }


@app.get("/tasks/status")
async def tasks_status():
    return {
        "rumor_hunting": rumor_worker.status.__dict__ if rumor_worker else None,
        "anti_trap_short": anti_short_worker.status.__dict__ if anti_short_worker else None,
        "market_analysis": analysis_worker.status.__dict__ if analysis_worker else None,
        "macro_scheduler": macro_worker.status.__dict__ if macro_worker else None,
        "vn_stock_analyzer": vn_stock_worker.status.__dict__ if vn_stock_worker else None,
        "schema_sync": schema_sync_worker.status.__dict__ if schema_sync_worker else None,
    }


@app.post("/trigger/analysis")
async def trigger_market_analysis():
    if analysis_worker is None:
        raise HTTPException(status_code=503, detail="Analysis worker not initialized")
    records = await analysis_worker.run_once()
    return {
        "status": "ok",
        "records_written": len(records),
        "worker_status": analysis_worker.status.__dict__,
    }


@app.post("/trigger/schema-sync")
async def trigger_schema_sync():
    if schema_sync_worker is None:
        raise HTTPException(status_code=503, detail="Schema sync worker not initialized")
    result = await schema_sync_worker.run_once()
    return {
        "status": "ok",
        "result": result,
    }


@app.get("/data/{table_name}")
async def fetch_table_data(table_name: str, limit: int = 20, order_by: str | None = None):
    allowed_tables = {
        "rumor_hunting_top20",
        "inverse_short_setup",
        "system_health",
        "market_scans",
        "market_signals",
        "market_news",
        "macro_indicators",
        "vn_stock_profiles",
    }
    normalized_name = table_name.strip().lower()
    if normalized_name not in allowed_tables:
        raise HTTPException(status_code=403, detail="Table access restricted")
    return {
        "table": normalized_name,
        "rows": await supabase_client.fetch_rows(normalized_name, limit=limit, order_by=order_by),
    }


@app.post("/trigger/function/{function_name}")
async def trigger_supabase_function(function_name: str, method: str = "POST"):
    allowed_functions = {
        "market-scan",
        "vn-scan",
        "multi-scan",
        "news-crawler",
        "macro-crawler",
        "vn-profile-crawler",
    }
    if function_name not in allowed_functions:
        raise HTTPException(status_code=404, detail="Unknown function")

    payload = await supabase_client.invoke_function(function_name, method=method)
    return {
        "status": "ok",
        "function": function_name,
        "method": method,
        "result": payload,
    }
