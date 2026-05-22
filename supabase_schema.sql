-- Supabase/PostgreSQL schema for Mr Tung backend

create table if not exists Rumor_Hunting_Top20 (
    id bigserial primary key,
    ticker text not null,
    source text not null,
    intel_source text,
    rumor_summary text,
    analysis_score numeric(5,2),
    live_status text,
    detected_at timestamptz,
    details text,
    quote_volume numeric(20,6),
    price_change_percent numeric(8,4),
    created_at timestamptz default now()
);

create index if not exists idx_rumor_hunting_ticker on Rumor_Hunting_Top20 (ticker);
create index if not exists idx_rumor_hunting_score on Rumor_Hunting_Top20 (analysis_score desc);

create table if not exists Inverse_Short_Setup (
    id bigserial primary key,
    ticker text not null,
    timeframe text,
    entry_price numeric(20,8),
    stop_loss numeric(20,8),
    take_profit numeric(20,8),
    analysis_score numeric(5,2),
    detected_at timestamptz,
    trigger_details text,
    source text,
    notes text,
    fvg_top numeric(20,8),
    fvg_bottom numeric(20,8),
    created_at timestamptz default now()
);

create index if not exists idx_inverse_short_ticker on Inverse_Short_Setup (ticker);
create index if not exists idx_inverse_short_score on Inverse_Short_Setup (analysis_score desc);

create table if not exists market_scans (
    id text primary key,
    symbol text not null,
    score numeric(8,2),
    price numeric(20,8),
    volume numeric(20,8),
    signal text,
    created_at timestamptz default now()
);

create index if not exists idx_market_scans_symbol on market_scans (symbol);
create index if not exists idx_market_scans_score on market_scans (score desc);

create table if not exists market_signals (
    id text primary key,
    symbol text not null,
    signal text,
    score numeric(8,2),
    price numeric(20,8),
    created_at timestamptz default now()
);

create index if not exists idx_market_signals_symbol on market_signals (symbol);
create index if not exists idx_market_signals_score on market_signals (score desc);

create table if not exists vn_stock_profiles (
    id text primary key,
    symbol text,
    source text,
    payload jsonb,
    updated_at timestamptz,
    created_at timestamptz default now()
);
create index if not exists idx_vn_stock_profiles_symbol on vn_stock_profiles (symbol);

create table if not exists system_health (
    id bigserial primary key,
    service text,
    status text,
    message text,
    checked_at timestamptz default now()
);

create table if not exists market_news (
    id bigserial primary key,
    title text,
    summary text,
    source text,
    url text,
    published_at timestamptz,
    created_at timestamptz default now()
);

create table if not exists macro_indicators (
    id bigserial primary key,
    indicator_name text,
    value numeric(20,8),
    timeframe text,
    source text,
    created_at timestamptz default now()
);
