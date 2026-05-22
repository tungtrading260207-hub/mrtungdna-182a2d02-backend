import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db import SupabaseClient
from app.config import settings
from app.tasks.vietnam_stock_worker import VietnamStockWorker

async def main():
    print("[Test] Đang kết nối Supabase...")
    supabase = SupabaseClient(settings.supabase_url, settings.supabase_service_key)
    
    print("[Test] Khởi tạo worker lấy dữ liệu...")
    worker = VietnamStockWorker(supabase_client=supabase)
    
    # 1. Lấy dữ liệu thật từ API Đại Nam về
    records = await worker.scan()
    
    if records:
        print(f"[Test] Đã lấy được {len(records)} mã. Dữ liệu thực tế gồm:")
        # In 2 mã đầu tiên ra màn hình xem các cột tên là gì
        print(records[:2]) 
        
        print(f"[Test] Tiến hành ÉP đẩy vào bảng rumor_hunting_top20...")
        res = await supabase.table("rumor_hunting_top20").upsert(records).execute()
        print("[Test] Đã ép ghi dữ liệu thành công!")

if __name__ == "__main__":
    asyncio.run(main())