from datetime import datetime
from typing import Any, ClassVar
from pydantic import BaseModel


class VNStockProfile(BaseModel):
    table_name: ClassVar[str] = "vn_stock_profiles"

    id: str
    symbol: str
    source: str
    payload: dict[str, Any]
    updated_at: datetime

    model_config = {
        "extra": "ignore",
    }


class MarketScan(BaseModel):
    table_name: ClassVar[str] = "market_scans"

    id: str
    symbol: str
    score: float
    price: float
    volume: float
    signal: str
    created_at: datetime | None = None

    model_config = {
        "extra": "ignore",
    }


class MarketSignal(BaseModel):
    table_name: ClassVar[str] = "market_signals"

    id: str
    symbol: str
    signal: str
    score: float
    price: float
    created_at: datetime | None = None

    model_config = {
        "extra": "ignore",
    }
