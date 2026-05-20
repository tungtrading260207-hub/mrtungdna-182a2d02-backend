import { createClient } from '@supabase/supabase-js'

// 1. ĐIỀN THÔNG TIN SUPABASE CỦA ANH VÀO ĐÂY
const SUPABASE_URL = 'https://bxpzbiprucavzybmloib.supabase.co' // Thay bằng URL của anh
const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJ4cHpiaXBydWNhdnp5Ym1sb2liIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Nzg0NjYzMzMsImV4cCI6MjA5NDA0MjMzM30.bp_11xJoLh1ayWKDZAi9kv87qsxf5FgIfay1TOBDZ2c'                 // Thay bằng Anon Key của anh

// Khởi tạo Client
const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

async function runSupabaseDiagnostic() {
  console.log('🏁 Bắt đầu kiểm tra kết nối Supabase...\n')

  // --- BƯỚC 1: KIỂM TRA THÔNG SỐ KHỞI TẠO ---
  if (!SUPABASE_URL || SUPABASE_URL.includes('your-project-id')) {
    console.error('❌ LỖI: Anh chưa thay đổi cấu hình SUPABASE_URL kìa!')
    return
  }

  // --- BƯỚC 2: PING TEST (GỌI THỬ HỆ THỐNG) ---
  console.log('🔄 1. Đang gửi gói tin Ping Test tới Supabase...')
  try {
    // Truy vấn thử danh sách bảng hệ thống để xem có thông mạng không
    const { data, error, status } = await supabase
      .from('_analytics') 
      .select('*')
      .limit(1)

    // Lưu ý: bảng _analytics có thể không tồn tại hoặc bị chặn RLS, 
    // nhưng nếu status trả về khác 0 hoặc không bị lỗi mạng thì kết nối đã thông suốt.
    if (error && status === 0) {
      throw new Error(error.message)
    }

    console.log(`✅ Kết nối mạng OK! Server phản hồi với mã trạng thái HTTP: ${status}`)
  } catch (err) {
    console.error('❌ LỖI KẾT NỐI MẠNG:')
    console.error(`👉 Kiểm tra lại mạng internet hoặc URL: "${SUPABASE_URL}" có gõ sai không.\n`)
    return
  }

  // --- BƯỚC 3: TEST ĐỌC/GHI THỰC TẾ (CRUD) ---
  console.log('\n🔄 2. Đang test quyền Đọc/Ghi dữ liệu...')
  
  // Mẹo: Anh hãy thay 'profiles' hoặc 'users' bằng tên một bảng thực tế trong DB của anh để test chuẩn nhất
  const targetTable = 'profiles' 

  const { data: readData, error: readError } = await supabase
    .from(targetTable)
    .select('*')
    .limit(1)

  if (readError) {
    console.log(`⚠️  Cảnh báo lệnh ĐỌC trên bảng [${targetTable}]:`, readError.message)
    console.log('👉 Gợi ý: Có thể do anh chưa tắt RLS (Row Level Security) hoặc bảng này chưa được tạo trên Supabase Dashboard.\n')
  } else {
    console.log(`✅ Quyền ĐỌC OK! Đã tiếp cận được bảng [${targetTable}].`)
  }

  // --- BƯỚC 4: TEST REALTIME (ĐỒNG BỘ SỐNG) ---
  console.log('\n🔄 3. Đang thiết lập kênh lắng nghe Realtime...');
  
  const testChannel = supabase
    .channel('diagnostic_room')
    .on('postgres_changes', { event: '*', schema: 'public', table: targetTable }, (payload) => {
      console.log('🔔 [SỰ KIỆN SỐNG]: Có thay đổi dữ liệu realtime:', payload)
    })
    .subscribe((status) => {
      if (status === 'SUBSCRIBED') {
        console.log('✅ Kênh Realtime: THÔNG SUỐT (SUBSCRIBED)!')
        console.log('💡 Trạng thái này chuẩn rồi. Nếu anh sửa dữ liệu trên Dashboard, web sẽ nhận được ngay.')
      } else if (status === 'CHANNEL_ERROR') {
        console.log('❌ Kênh Realtime: THẤT BẠI (CHANNEL_ERROR)!')
        console.log('👉 Gợi ý: Anh đã bật tính năng "Replication > Source" cho bảng này trên Dashboard chưa?')
      } else {
        console.log(`📡 Trạng thái kênh hiện tại: ${status}`)
      }
    })
}

// Kích hoạt lệnh kiểm tra
runSupabaseDiagnostic()