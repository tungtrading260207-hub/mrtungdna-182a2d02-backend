from datetime import datetime
from typing import Any
from pydantic import BaseModel


class RumorHuntingRecord(BaseModel):
    table_name = "rumor_hunting_top20"

    id: int | None = None
    ticker: str
    source: str
    intel_source: str
    rumor_summary: str
    analysis_score: float
    live_status: str
    detected_at: datetime
    details: str | None = None
    quote_volume: float | None = None
    price_change_percent: float | None = None

    model_config = {
        "extra": "ignore",
    }


class InverseShortSetup(BaseModel):
    table_name = "inverse_short_setup"

    id: int | None = None
    ticker: str
    timeframe: str | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    analysis_score: float | None = None
    detected_at: datetime | None = None
    trigger_details: str | None = None
    source: str | None = None
    notes: str | None = None
    fvg_top: float | None = None
    fvg_bottom: float | None = None

    model_config = {
        "extra": "ignore",
    }
