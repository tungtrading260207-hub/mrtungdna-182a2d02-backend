from pathlib import Path
from pydantic import AnyHttpUrl, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
    )

    supabase_url: AnyHttpUrl
    supabase_service_key: str = Field(
        ...,
        validation_alias=AliasChoices(
            "supabase_service_key",
            "SUPABASE_SERVICE_KEY",
            "SUPABASE_SERVICE_ROLE_KEY",
        ),
    )
    supabase_db_url: str | None = None
    coinglass_api_key: str | None = None
    gemini_api_key: str | None = None
    lovable_api_key: str | None = None
    news_api_key: str | None = None
    news_api_url: str | None = None
    vn_stock_api_url: str | None = None
    vn_stock_api_key: str | None = None
    vn_stock_source: str | None = None
    rumour_table: str = Field("Rumor_Hunting_Top20")
    inverse_short_table: str = Field("Inverse_Short_Setup")
    rate_limit_min: float = Field(3.0, validation_alias="BINANCE_RATE_LIMIT_SECONDS_MIN")
    rate_limit_max: float = Field(5.0, validation_alias="BINANCE_RATE_LIMIT_SECONDS_MAX")
    timezone: str = "Asia/Ho_Chi_Minh"


settings = Settings()
