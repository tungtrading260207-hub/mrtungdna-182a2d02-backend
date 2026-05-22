from pathlib import Path
from pydantic import AnyHttpUrl, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
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
    coinglass_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("coinglass_api_key", "COINGLASS_API_KEY", "VITE_COINGLASS_API_KEY"),
    )
    news_api_key: str | None = None
    news_api_url: str | None = None
    coingecko_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("coingecko_api_key", "COINGECKO_API_KEY", "VITE_COINGECKO_API_KEY"),
    )
    lunarcrush_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("lunarcrush_api_key", "LUNARCRUSH_API_KEY", "VITE_LUNARCRUSH_API_KEY"),
    )
    alpha_vantage_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("alpha_vantage_api_key", "ALPHA_VANTAGE_API_KEY", "VITE_ALPHA_VANTAGE_API_KEY"),
    )
    fred_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("fred_api_key", "FRED_API_KEY"),
    )
    etherscan_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("etherscan_api_key", "ETHERSCAN_API_KEY", "VITE_ETHERSCAN_API_KEY"),
    )
    dainam_api_url: AnyHttpUrl | None = Field(
        None,
        validation_alias=AliasChoices("dainam_api_url", "DAINAM_API_URL"),
    )
    dainam_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("dainam_api_key", "DAINAM_API_KEY"),
    )
    dainam_api_secret: str | None = Field(
        None,
        validation_alias=AliasChoices("dainam_api_secret", "DAINAM_API_SECRET"),
    )
    dainam_api_path: str | None = Field(
        None,
        validation_alias=AliasChoices("dainam_api_path", "DAINAM_API_PATH"),
    )
    dns_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("dns_api_key", "DNS_API_KEY"),
    )
    vn_stock_api_url: str | None = None
    vn_stock_api_key: str | None = None
    vn_stock_source: str | None = None
    dns_source_label: str = Field(
        "DaiNam_DNS",
        validation_alias=AliasChoices("dns_source_label", "DNS_SOURCE_LABEL"),
    )
    rumour_table: str = Field("rumor_hunting_top20")
    inverse_short_table: str = Field("inverse_short_setup")
    rate_limit_min: float = Field(3.0, validation_alias="BINANCE_RATE_LIMIT_SECONDS_MIN")
    rate_limit_max: float = Field(5.0, validation_alias="BINANCE_RATE_LIMIT_SECONDS_MAX")
    cache_time_realtime_slow: int = Field(
        300000,
        validation_alias=AliasChoices("cache_time_realtime_slow", "CACHE_TIME_REALTIME_SLOW"),
    )
    cache_time_social: int = Field(
        1800000,
        validation_alias=AliasChoices("cache_time_social", "CACHE_TIME_SOCIAL"),
    )
    cache_time_macro: int = Field(
        86400000,
        validation_alias=AliasChoices("cache_time_macro", "CACHE_TIME_MACRO"),
    )
    dashboard_alert_url: AnyHttpUrl | None = Field(
        None,
        validation_alias=AliasChoices("dashboard_alert_url", "DASHBOARD_ALERT_URL"),
    )
    dashboard_alert_api_key: str | None = Field(
        None,
        validation_alias=AliasChoices("dashboard_alert_api_key", "DASHBOARD_ALERT_API_KEY"),
    )
    schema_sync_interval_seconds: int = Field(
        3600,
        validation_alias=AliasChoices("schema_sync_interval_seconds", "SCHEMA_SYNC_INTERVAL_SECONDS"),
    )
    timezone: str = "Asia/Ho_Chi_Minh"


settings = Settings()
