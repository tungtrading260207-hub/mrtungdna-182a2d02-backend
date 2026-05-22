import asyncio
import sys
import os
# Đảm bảo đã cài: pip install supabase
from app.db import SupabaseClient

async def main():
    print("[Test] Đang nạp dữ liệu mẫu vào Supabase...")
    supabase = SupabaseClient()
    
    # Dữ liệu mẫu cứng để đảm bảo bảng không trống
    sample_data = [
        {"ticker": "FPT", "name": "CTCP FPT", "industry": "Công nghệ", "overview": "Tập đoàn công nghệ hàng đầu", "website": "https://fpt.com.vn"},
        {"ticker": "HPG", "name": "CTCP Tập đoàn Hòa Phát", "industry": "Thép", "overview": "Nhà sản xuất thép lớn nhất Đông Nam Á", "website": "https://hoaphat.com.vn"},
        {"ticker": "TCB", "name": "Ngân hàng TMCP Kỹ Thương Việt Nam", "industry": "Ngân hàng", "overview": "Ngân hàng thương mại cổ phần hàng đầu", "website": "https://techcombank.com.vn"}
    ]
    
    try:
        response = supabase.table("vn_stock_profiles").upsert(sample_data).execute()
        print("✅ [THÀNH CÔNG] Dữ liệu mẫu đã được đẩy lên bảng!")
    except Exception as e:
        print(f"❌ [Lỗi Supabase]: {e}")

if __name__ == "__main__":
    asyncio.run(main())