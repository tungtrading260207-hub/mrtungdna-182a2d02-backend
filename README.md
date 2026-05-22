# Mr Tung Python FastAPI Backend

Backend này là engine Python FastAPI chạy 24/7 để quét Rumor Hunting và Anti-Trap Short.

## File chính
- `main.py`
- `app/config.py`
- `app/db.py`
- `app/rate_limiter.py`
- `app/tasks.py`
- `app/services/rumor_hunting.py`
- `app/services/anti_trap_short.py`
- `app/services/vn_stock_source.py`

## Cài đặt
```bash
python -m pip install -r requirements.txt
```

## Chạy
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Kiểm tra đồng bộ schema
Chạy script kiểm tra schema giữa code và database:
```bash
python sync_check.py
```

## Endpoints bổ sung
- `GET /health` — kiểm tra trạng thái service
- `POST /trigger/rumor` — chạy Rumor Hunting một lần
- `POST /trigger/anti_short` — chạy Anti-Trap Short một lần
- `POST /trigger/analysis` — chạy Market Data Analysis một lần
- `POST /trigger/schema-sync` — chạy kiểm tra đồng bộ schema giữa code và database
- `POST /trigger/function/{function_name}` — gọi Supabase edge function được phép
- `GET /tasks/status` — lấy trạng thái worker và lần quét cuối cùng
- `GET /data/{table_name}` — lấy dữ liệu từ một số bảng Supabase được phép (`Rumor_Hunting_Top20`, `Inverse_Short_Setup`, `system_health`, `market_scans`, `market_signals`, `market_news`, `macro_indicators`)

## Biến môi trường
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_DB_URL`
- `COINGLASS_API_KEY`
- `GEMINI_API_KEY`
- `LOVABLE_API_KEY`
- `NEWS_API_KEY`
- `NEWS_API_URL`
- `VN_STOCK_API_URL`
- `VN_STOCK_API_KEY`
- `VN_STOCK_SOURCE`
- `BINANCE_RATE_LIMIT_SECONDS_MIN`
- `BINANCE_RATE_LIMIT_SECONDS_MAX`
- `DASHBOARD_ALERT_URL`
- `DASHBOARD_ALERT_API_KEY`
- `SCHEMA_SYNC_INTERVAL_SECONDS`
