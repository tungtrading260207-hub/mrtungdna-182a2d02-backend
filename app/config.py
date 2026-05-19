from pathlib import Path
from pydantic import BaseSettings, AnyHttpUrl, Field


class Settings(BaseSettings):
    supabase_url: AnyHttpUrl
    supabase_service_key: str
    supabase_db_url: str | None = None
    coinglass_api_key: str | None = None
    vn_stock_api_url: str | None = None
    vn_stock_api_key: str | None = None
    vn_stock_source: str | None = None
    rumour_table: str = Field("Rumor_Hunting_Top20")
    inverse_short_table: str = Field("Inverse_Short_Setup")
    rate_limit_min: float = Field(3.0, env="BINANCE_RATE_LIMIT_SECONDS_MIN")
    rate_limit_max: float = Field(5.0, env="BINANCE_RATE_LIMIT_SECONDS_MAX")
    timezone: str = "Asia/Ho_Chi_Minh"

    class Config:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        env_file_encoding = "utf-8"


settings = Settings()
