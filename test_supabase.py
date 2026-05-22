import asyncio
import sys
import os

# Ép hệ thống nhận diện thư mục gốc để không bao giờ bị lỗi Module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SupabaseClient
from app.config import settings
from app.tasks.vietnam_stock_worker import VietnamStockWorker

async def main():
    print("[Test] Đang khởi tạo kết nối Supabase...")
    supabase = SupabaseClient(settings.supabase_url, settings.supabase_service_key)
    
    print("[Test] Đang ép VietnamStockWorker chạy một chu kỳ quét dữ liệu (Bỏ qua giờ giao dịch)...")
    worker = VietnamStockWorker(supabase_client=supabase)
    
    # Gọi thẳng hàm scan và xử lý ghi dữ liệu của worker
    records = await worker.scan()
    print(f"[Test] Chu kỳ hoàn tất! Đã xử lý và đẩy {len(records)} mã cổ phiếu lên Supabase.")

if __name__ == "__main__":
    asyncio.run(main())