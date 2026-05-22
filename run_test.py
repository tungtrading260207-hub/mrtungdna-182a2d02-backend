import asyncio
import sys
import os

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
    
    print("[Test] Thực hiện vá ép kiểu dữ liệu URL từ AnyHttpUrl sang String thuần...")
    # Biến đổi object AnyHttpUrl thành chuỗi string thuần để httpx không bị lỗi ép kiểu
    if settings.dainam_api_url:
        settings.dainam_api_url = str(settings.dainam_api_url)
    
    print("[Test] Ép worker bơi ra API lấy dữ liệu và đẩy lên Supabase...")
    records = await worker.scan()
    
    print(f"[Test] Chu kỳ hoàn tất! Đã xử lý và đẩy thành công dữ liệu lên bảng vn_stock_profiles.")

if __name__ == "__main__":
    asyncio.run(main())