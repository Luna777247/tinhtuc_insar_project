# Sự kiện Mưa lũ 28/09 - 01/10/2025 - Tĩnh Túc

## Tổng quan

Phân tích ngập lụt và sạt lở cho sự kiện mưa lũ từ 28/09 đến 01/10/2025.

## Dữ liệu Sentinel-1

### Ảnh có sẵn cho sự kiện

| Ngày | Giờ | Orbit | Hướng | Mục đích |
|------|-----|-------|-------|----------|
| **17/09/2025** | 10:58 | 55 | ASC | Baseline ngập |
| **19/09/2025** | 22:50 | 91 | DESC | Baseline sạt lở |
| **29/09/2025** | 10:58 | 55 | ASC | **Phát hiện ngập** |
| **01/10/2025** | 22:50 | 91 | DESC | **Phát hiện sạt lở** |

### Tốc độ sụt lún (SBAS)

Sử dụng toàn bộ dữ liệu `S1_Metadata_TinhTuc_2014_to_Now.csv`:

| Orbit | Số ảnh | Thời gian | Tần suất |
|-------|--------|-----------|----------|
| 55 (ASC) | 543 | 2015-2026 | ~7 ngày |
| 91 (DESC) | 319 | 2015-2026 | ~12 ngày |
| 128 (ASC) | 268 | 2017-2026 | ~12 ngày |

## Cách chạy

### 1. Kiểm tra dữ liệu

```bash
python run_pipeline.py --event 20250928
```

### 2. Chạy GEE cho ngập lụt và sạt lở

```javascript
// Mở trong Google Earth Engine Code Editor:
// gee_scripts/06_flood_event_20250929_1001.js
```

Các bước:
1. Copy script từ `gee_scripts/06_flood_event_20250929_1001.js`
2. Paste vào GEE Code Editor
3. Chạy và xuất kết quả
4. Tải về thư mục `outputs/events/20250928_1001/`

### 3. Xử lý SBAS cho sụt lún

Theo tài liệu `docs/Sentinel1_TinhTuc_PhanTich_KichBan_ChiTiet.md`:

```bash
# 1. Tải SLC từ ASF Vertex
# 2. Xử lý bằng SNAP hoặc ASF HyP3
# 3. Time-series bằng MintPy
```

## File đã tạo

### Scripts GEE
- `gee_scripts/06_flood_event_20250929_1001.js` - Phân tích sự kiện

### Modules Python
- `src/flood_landslide/flood_detector.py` - Phát hiện ngập
- `src/flood_landslide/landslide_detector.py` - Phát hiện sạt lở
- `src/flood_landslide/mine_monitor.py` - Giám sát bãi thải
- `src/flood_landslide/risk_integrator.py` - Tích hợp rủi ro
- `src/flood_landslide/event_processor.py` - Xử lý sự kiện

## Kết quả đầu ra

```
outputs/events/20250928_1001/
├── event_config.json          # Cấu hình sự kiện
├── flood_mask.npy            # Mask ngập lụt
├── landslide_mask.npy        # Mask sạt lở
├── risk_map.npy              # Bản đồ rủi ro
├── hotspots.json             # Điểm nóng
├── statistics.json           # Thống kê
└── report.txt                # Báo cáo
```

## Ngưỡng phát hiện

### Ngập lụt
- **Ngưỡng**: μ - 1.5σ (adaptive)
- **Điều kiện**: VH giảm, độ dốc < 5°, không phải nước thường xuyên
- **Xác nhận**: ≥ 2/3 track đồng ý

### Sạt lở
- **Ngưỡng**: |ΔVH| > 3 dB
- **Điều kiện**: Độ dốc 20-55°, không phải ngập
- **Xác nhận**: NDVI giảm > 0.2 (Sentinel-2)

## Tham khảo

- Twele et al. (2016): Sentinel-1 flood mapping
- Bovenga et al. (2021): SAR landslide detection

## Liên hệ

GIS/InSAR Analysis Team
