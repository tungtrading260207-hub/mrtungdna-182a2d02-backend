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
    supabase = SupabaseClient(settings.supabase_url, settings.supabase_service_key)
    
    print("[Test] Khởi tạo VietnamStockWorker...")
    worker = VietnamStockWorker(supabase_client=supabase)
    
    print("[Test] Ép worker chạy một chu kỳ quét dữ liệu thực tế...")
    # Gọi chính xác hàm chạy chu kỳ của Worker để kích hoạt luồng cào Đại Nam và đẩy Supabase
    await worker._run_cycle()
    
    print("[Test] Chu kỳ chạy thử hoàn tất! Anh quay lại kiểm tra bảng trên Supabase nhé.")

if __name__ == "__main__":
    asyncio.run(main())