class AntigravityEngine:
    def __init__(self):
        self.version = "1.1"
        self.author = "MrTungTrade2011"

    def classify_asset(self, ticker: str) -> str:
        """
        Bước 1: Thuật toán phân loại tài sản tự động dựa trên hậu tố theo quy tắc sếp Tùng
        """
        ticker_upper = ticker.upper().strip()
        if "USDT.P" in ticker_upper:
            return "CRYPTO_FUTURES"
        elif "USDT" in ticker_upper:
            return "CRYPTO_SPOT"
        else:
            return "VN_STOCK"

    def calculate_pnl_expected(self, asset_class: str, side: str, entry: float, sl: float, tp: float, capital: float, leverage: float) -> dict:
        """
        Bước 2: Thuật toán tính toán Lỗ/Lãi kỳ vọng động và tỷ lệ R:R dựa trên vị thế thực tế
        """
        # Tính toán Quy mô vị thế (Position Size)
        position_size = capital * leverage
        
        # Tính toán khoảng cách % biến động từ Entry đến SL và TP
        delta_sl = abs(entry - sl) / entry if entry > 0 else 0
        delta_tp = abs(tp - entry) / entry if entry > 0 else 0
        
        # Tính số tiền lãi lỗ cụ thể dựa theo vị thế Long/Short
        if side.upper() in ["LONG", "BUY"]:
            pnl_at_sl = -delta_sl * position_size
            pnl_at_tp = delta_tp * position_size
        else: # Vị thế Short/Sell
            pnl_at_sl = -delta_sl * position_size
            pnl_at_tp = delta_tp * position_size
            
        # Tính tỷ lệ Risk:Reward toán học
        risk_reward_ratio = delta_tp / delta_sl if delta_sl > 0 else 0
        
        # Định dạng tiền tệ tương ứng với loại tài sản
        unit = "USD" if "CRYPTO" in asset_class else "VND"
        
        return {
            "position_size": round(position_size, 2),
            "pnl_at_sl": f"{round(pnl_at_sl, 2)} {unit}",
            "pnl_at_tp": f"{round(pnl_at_tp, 2)} {unit}",
            "risk_reward_ratio": round(risk_reward_ratio, 2)
        }

    def generate_realtime_recommendation(self, asset_class: str, side: str, current_price: float, entry: float, hma_slope: float, cvd_trend: str, mfi: float) -> tuple:
        """
        Bước 3: Bộ não quyết định trạng thái và xuất câu lệnh điều hướng hành động cho người dùng
        """
        # Nhóm xử lý Crypto
        if "CRYPTO" in asset_class:
            if current_price < entry and hma_slope <= 0 and cvd_trend == "DOWNTREND":
                status = "CỰC XẤU - BẪY THANH KHOẢN"
                recommendation = "🚨 CẢNH BÁO ĐỎ: Vị thế dính bẫy thanh khoản của phe Gấu. Dòng tiền chủ động (CVD) rút ròng hoàn toàn. KHÔNG TRUNG BÌNH GIÁ. Khuyến nghị cắt lỗ/thoát hàng ngay lập tức để bảo toàn vốn."
            elif mfi > 80 and cvd_trend == "DIVERGENCE":
                status = "CẠN LỰC MUA - CHỐT LỜI CHỦ ĐỘNG"
                recommendation = "⚠️ CẠN LỰC ĐẨY: Giá tăng nhưng Vol mua giảm dần (Exhaustion Mode), cấu trúc có xu hướng tạo Price Trap ở đỉnh. KHUYẾN NGHỊ: Chốt lời chủ động 50-100% vị thế lập tức."
            elif current_price < entry and hma_slope > 0 and cvd_trend == "FLAT":
                status = "TÍCH LŨY CHỜ ENTRY THỨ HAI"
                recommendation = "⏳ GIỮ HÀNG & ĐỢI: Nhịp giảm chỉ là sóng chỉnh kỹ thuật cạn Vol. Tiếp tục giữ vị thế hiện tại và cài lệnh LIMIT mua thêm (DCA Dương) tại vùng FVG H4 để tối ưu giá vốn."
            elif current_price > entry and hma_slope > 0 and cvd_trend == "UPTREND":
                status = "VỊ THẾ ĐẸP - GỒNG LỜI ĐỘNG"
                recommendation = "👑 VỊ THẾ KHỎE: Dòng tiền cá mập đang đẩy mạnh (True Absorption). KHUYẾN NGHỊ: Tiếp tục gồng lãi. Dời SL dương về mốc an toàn. Bật chế độ Trailing Stop theo dõi sát nến H4."
            else:
                status = "THEO DÕI"
                recommendation = "⏳ Vị thế đang đi ngang tích lũy, hệ thống tiếp tục giữ trạng thái quan sát dòng tiền."
                
        # Nhóm xử lý Chứng Khoán VN
        else:
            if current_price < entry and hma_slope <= 0 and cvd_trend == "DOWNTREND":
                status = "RỦI RO CAO - CÂN NHẮC THOÁT"
                recommendation = "🚨 CẢNH BÁO: Cổ phiếu mất cấu trúc tăng, gia tốc HMA Slope cắm đầu. Không trung bình giá dưới mọi hình thức để tránh rủi ro Margin Call từ CTCK."
            elif hma_slope > 0 and cvd_trend == "UPTREND":
                status = "ĐỦ ĐIỀU KIỆN MUA GIA TĂNG"
                recommendation = "🎯 ĐỦ ĐIỀU KIỆN MUA GIA TĂNG: Cổ phiếu chạm đường trục Anchored VWAP Năm, xuất hiện nến rút râu quét thanh khoản, đạt chuẩn nội lực 3T. Khuyến nghị mua gia tăng vị thế."
            else:
                status = "THEO DÕI TÍCH LŨY"
                recommendation = "⏳ Giá đang dao động quanh vùng tích lũy, khối lượng giao dịch nằm dưới MA26. Chờ tín hiệu bứt phá."

        return status, recommendation
