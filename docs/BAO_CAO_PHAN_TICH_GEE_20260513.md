# BÁO CÁO CÔNG TÁC PHÂN TÍCH DỮ LIỆU SAR (GEE) — KHU VỰC TĨNH TÚC

**Ngày báo cáo:** 13/05/2026
**Dữ liệu nguồn:** Sentinel-1 (SAR) & Sentinel-2 (NDVI) qua Google Earth Engine

---

## 1. Tóm tắt kết quả diện tích

| File kết quả | Thông số | Diện tích (km²) | Diện tích (Hecta) |
| :--- | :--- | :---: | :---: |
| `Landslide_Confirmed` | Vùng sạt lở xác định (SAR + NDVI) | **35.6376** | 3,563.76 |
| `Flood_Orbit55` | Vùng ngập lụt xác nhận | **0.9917** | 99.17 |
| `Flood_Diff_VV` | Vùng biến động tán xạ (Độ ẩm/Thay đổi bề mặt) | **201.2230** | 20,122.30 |

---

## 2. Giải thích chi tiết kết quả

### 2.1. Phân tích Sạt lở (`Landslide_Confirmed_*.tif`)

* **Giá trị:** 35.6376 km².
* **Cơ chế phát hiện:** Đây là diện tích kết hợp giữa hai điều kiện:
    1. **SAR**: Độ tán xạ VH thay đổi mạnh (> 3dB) trên các sườn dốc (20° - 55°).
    2. **NDVI**: Chỉ số thực vật giảm đáng kể (> 0.2), cho thấy thực vật bị mất đi/vùi lấp.
* **Giải thích:** Con số 35.6 km² là diện tích có sự biến động mạnh về địa chất và thảm thực vật. Kết quả này bao gồm cả:
  * Các khu vực sạt lở thực tế do mưa lũ.
  * Các hoạt động bóc tách tầng phủ và dịch chuyển đất đá tại các bãi thải mỏ Tĩnh Túc.
* **Tính ổn định:** Việc hai lượt chạy (`174635` và `174720`) cho kết quả khớp nhau hoàn toàn cho thấy thuật toán vận hành rất ổn định.

### 2.2. Phân tích Ngập lụt xác nhận (`Flood_Orbit55_*.tif`)

* **Giá trị:** 0.9917 km² (xấp xỉ 100 Hecta).
* **Cơ chế phát hiện:** Vùng có độ tán xạ VH giảm mạnh, nằm trên địa hình bằng phẳng (độ dốc < 5°) và không phải là vùng nước thường xuyên.
* **Giải thích:** Đây là diện tích thực sự bị ngập lụt trong sự kiện quan trắc. Với đặc thù địa hình núi cao tại Tĩnh Túc, diện tích ngập ~100 ha tập trung chủ yếu ở các thung lũng, khu dân cư thấp trũng và hạ lưu hệ thống thoát nước mỏ.

### 2.3. Biến động tán xạ tổng thể (`Flood_Diff_VV_*.tif`)

* **Giá trị:** 201.2230 km².
* **Cơ chế phát hiện:** Tổng diện tích có sự thay đổi giá trị band VV giữa trước và sau sự kiện trên toàn bộ vùng quan sát (AOI).
* **Giải thích:**
  * Đây **không phải** là diện tích ngập lụt.
  * Con số này phản ánh độ nhạy của radar với sự thay đổi độ ẩm đất trên diện rộng sau mưa. Hầu hết khu vực nghiên cứu đều ghi nhận sự thay đổi đặc tính bề mặt do độ ẩm tăng cao, kể cả các vùng rừng núi không bị sạt lở hay ngập lụt.

---

## 3. Nhận xét và khuyến nghị

1. **Độ tin cậy:** Thuật toán GEE đã xử lý tốt các tình huống thiếu ảnh quang học (Sentinel-2) bằng cơ chế fallback, đảm bảo pipeline không bị gián đoạn.
2. **Trọng điểm giám sát:** Cần thực hiện chồng lớp (overlay) vùng 35.6 km² biến động với bản đồ hiện trạng bãi thải mỏ để tách lọc chính xác các điểm sạt lở tự nhiên mới phát sinh.
3. **Hành động tiếp theo:**
    * Sử dụng tọa độ các vùng ngập xác nhận (`0.99 km²`) để kiểm tra thiệt hại hạ tầng thực địa.
    * Chạy `run_processing_gee_result.py` để trích xuất các bản đồ PNG phục vụ thuyết minh báo cáo gửi các cơ quan chức năng.

---
**Người lập báo cáo:** Antigravity (AI Assistant)
**Dự án:** Giám sát Biến dạng và Ngập lụt Tĩnh Túc.
