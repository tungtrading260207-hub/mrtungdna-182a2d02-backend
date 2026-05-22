from datetime import datetime
from typing import Any, ClassVar
from pydantic import BaseModel


class MacroIndicator(BaseModel):
    table_name: ClassVar[str] = "macro_indicators"

    id: str
    indicator_name: str
    value: float | str | dict[str, Any] | list[Any]
    timeframe: str | None = None
    source: str | None = None
    created_at: datetime | None = None
    notes: str | None = None

    model_config = {
        "extra": "ignore",
    }


class SystemHealth(BaseModel):
    table_name: ClassVar[str] = "system_health"

    id: int | None = None
    service: str
    status: str
    message: str | None = None
    checked_at: datetime | None = None

    model_config = {
        "extra": "ignore",
    }


class MarketNews(BaseModel):
    table_name: ClassVar[str] = "market_news"

    id: int | None = None
    title: str
    summary: str | None = None
    source: str | None = None
    url: str | None = None
    published_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {
        "extra": "ignore",
    }
