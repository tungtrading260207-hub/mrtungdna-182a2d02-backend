import asyncio
from supabase import create_client
from app.config import settings

async def test_supabase():
    print("--- 🔍 Đang khởi tạo Supabase Client ---")
    
    # Sử dụng đúng tên biến đã xác định từ dir(settings)
    url = settings.supabase_url
    key = settings.supabase_service_key
    
    if not url or not key:
        print(f"❌ [LỖI] Thiếu thông tin! URL: {url}, Key: {key}")
        return

    try:
        # Ép kiểu url về string để tránh lỗi AnyHttpUrl
        supabase = create_client(str(url), key)
        print("--- 🔍 Đang thử truy vấn bảng 'vn_stock_profiles' ---")
        
        # Dùng .from_() chuẩn v2
        response = supabase.from_("vn_stock_profiles").select("*").limit(1).execute()
        
        print("✅ [THÀNH CÔNG] Kết nối và truy vấn Supabase ổn định!")
        print(f"📦 Dữ liệu nhận được: {response.data}")
            
    except Exception as e:
        print(f"❌ [THẤT BẠI] Lỗi xảy ra: {e}")

if __name__ == "__main__":
    asyncio.run(test_supabase())