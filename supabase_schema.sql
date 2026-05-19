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
