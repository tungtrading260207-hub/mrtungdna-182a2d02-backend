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

## Biến môi trường
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`
- `SUPABASE_DB_URL`
- `COINGLASS_API_KEY`
- `VN_STOCK_API_URL`
- `VN_STOCK_API_KEY`
- `VN_STOCK_SOURCE`
- `BINANCE_RATE_LIMIT_SECONDS_MIN`
- `BINANCE_RATE_LIMIT_SECONDS_MAX`
