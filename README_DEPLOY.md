# Deploy Mr Tung Python FastAPI backend to Render

## 1. Chuẩn bị repository GitHub

1. Tạo repo mới trên GitHub cá nhân.
2. Đẩy toàn bộ thư mục `mrtungdna-182a2d02-backend/` lên repo mới.
   - `main.py`
   - `app/...`
   - `requirements.txt`
   - `Dockerfile`
   - `.env.example`
   - `supabase_schema.sql`
   - `scripts/create_supabase_tables.py`
   - `render.yaml`
   - `README.md`

## 2. Cấu hình Supabase

Sử dụng `supabase_schema.sql` để tạo bảng trong Supabase SQL Editor:

- `Rumor_Hunting_Top20`
- `Inverse_Short_Setup`

Hoặc chạy script Python nếu bạn đã thiết lập `.env` với `SUPABASE_DB_URL`:

```bash
cd mrtungdna-182a2d02-backend
python scripts/create_supabase_tables.py
```

## 3. Cấu hình Render

1. Đăng nhập vào Render.
2. Tạo `Web Service` mới.
3. Chọn `Docker` làm môi trường deploy.
4. Kết nối repo GitHub chứa `mrtungdna-182a2d02-backend`.
5. Chọn branch `main`.
6. Build Command:
   - `docker build -t mrtung-python-engine .`
7. Start Command:
   - `uvicorn main:app --host 0.0.0.0 --port $PORT`
8. Thêm biến môi trường Render:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `SUPABASE_DB_URL`
   - `COINGLASS_API_KEY`
   - `VN_STOCK_API_URL`
   - `VN_STOCK_API_KEY`
   - `VN_STOCK_SOURCE`
   - `BINANCE_RATE_LIMIT_SECONDS_MIN=3`
   - `BINANCE_RATE_LIMIT_SECONDS_MAX=5`

## 4. Kiểm tra sau deploy

- Endpoint: `https://<render-service>.onrender.com/health`
- Trả về JSON với `status: ok`.

> Like & Follow tài khoản MrTungTrade2011 trên Trading View, để liên tục cập nhật những đợt nâng cấp thuật toán tiếp theo, cũng như nhận thông báo sớm nhất về các bộ chỉ báo độc quyền khác đang được chia sẻ! 🔥
