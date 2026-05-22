import asyncio
import sys
import os
import time
import jwt

# Ép hệ thống nhận diện thư mục gốc để tránh lỗi import module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SupabaseClient
from app.config import settings
from app.tasks.vietnam_stock_worker import VietnamStockWorker

async def main():
    print("[Test] Đang kết nối Supabase Cloud...")
    supabase = SupabaseClient()
    
    print("[Test] Khởi tạo VietnamStockWorker...")
    worker = VietnamStockWorker(supabase_client=supabase)
    
    print("[Test] Sử dụng endpoint DaiNam từ file .env...")
    if not settings.dainam_api_url:
        raise RuntimeError("DAINAM_API_URL không được cấu hình trong .env")
    settings.dainam_api_url = str(settings.dainam_api_url)
    print(f"[📡 Target URL]: {settings.dainam_api_url}")
    print("[Test] Worker sẽ dùng endpoint cấu hình để lấy dữ liệu và đẩy lên Supabase...")
    
    try:
        records = await worker.scan()
        print(f"[Test] Chu kỳ hoàn tất! Đã xử lý dữ liệu.")
    except Exception as e:
        print(f"[Lỗi hệ thống]: {e}")

if __name__ == "__main__":
    asyncio.run(main())