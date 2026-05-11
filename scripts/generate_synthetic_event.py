#!/usr/bin/env python
"""
Tạo kết quả synthetic cho sự kiện mưa lũ 28/09-01/10/2025.
"""

import numpy as np
import pandas as pd
import json
import logging
from pathlib import Path
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thông số
H, W = 100, 100  # 1km x 1km với 10m resolution
PIXEL_SIZE = 10  # meters

def generate_synthetic_event_data():
    """Tạo dữ liệu synthetic cho sự kiện mưa lũ."""
    
    logger.info("=" * 60)
    logger.info("TẠO KẾT QUẢ SYNTHETIC - SỰ KIỆN MƯA LŨ 28/09-01/10/2025")
    logger.info("=" * 60)
    
    # 1. Tạo bản đồ độ dốc
    x = np.linspace(0, 1, W)
    y = np.linspace(0, 1, H)
    X, Y = np.meshgrid(x, y)
    
    # Địa hình: thung lũng ở giữa, núi xung quanh
    elevation = 500 + 300 * (np.abs(X - 0.5) + np.abs(Y - 0.5))**2
    elevation += np.random.normal(0, 20, (H, W))
    
    # Độ dốc
    slope = np.gradient(elevation)[0]
    slope = np.abs(slope) / 10  # Đơn vị độ
    slope = np.clip(slope, 0, 60)
    
    # 2. Tạo vùng ngập lụt (vùng thấp, dốc < 5°)
    flood_mask = np.zeros((H, W), dtype=bool)
    flood_zones = [
        (slice(70, 85), slice(30, 50)),   # Thung lũng phía Nam
        (slice(60, 75), slice(60, 80)),   # Vùng trũng phía Đông Nam
    ]
    
    for y_sl, x_sl in flood_zones:
        if np.mean(slope[y_sl, x_sl]) < 10:  # Kiểm tra độ dốc
            flood_mask[y_sl, x_sl] = True
    
    # Thêm nhiễu
    flood_mask = flood_mask & (slope < 5)
    flood_mask = np.random.choice([False, True], size=(H, W), p=[0.92, 0.08])
    flood_mask = flood_mask & (slope < 5)  # Chỉ ngập vùng bằng
    
    # 3. Tạo vùng sạt lở (vùng dốc 20-55°)
    landslide_mask = np.zeros((H, W), dtype=bool)
    landslide_zones = [
        (slice(40, 55), slice(20, 35)),   # Sườn Tây Bắc
        (slice(30, 50), slice(70, 85)),   # Sườn Đông
    ]
    
    for y_sl, x_sl in landslide_zones:
        if 20 < np.mean(slope[y_sl, x_sl]) < 55:
            landslide_mask[y_sl, x_sl] = True
    
    landslide_mask = landslide_mask & (slope > 20) & (slope < 55)
    
    # 4. Bãi thải mỏ (3 vị trí)
    mine_mask = np.zeros((H, W), dtype=bool)
    mine_centers = [(20, 25), (30, 72), (25, 85)]  # (y, x)
    
    for cy, cx in mine_centers:
        y_start, y_end = max(0, cy-5), min(H, cy+5)
        x_start, x_end = max(0, cx-5), min(W, cx+5)
        mine_mask[y_start:y_end, x_start:x_end] = True
    
    # 5. Tính bản đồ rủi ro
    risk_map = np.zeros((H, W), dtype=np.uint8)
    risk_map = risk_map + flood_mask.astype(np.uint8) * 1
    risk_map = np.maximum(risk_map, landslide_mask.astype(np.uint8) * 2)
    risk_map = np.maximum(risk_map, mine_mask.astype(np.uint8) * 1)
    
    # Vùng có cả ngập và sạt lở = Extreme (4)
    multi_risk = flood_mask.astype(int) + landslide_mask.astype(int) + mine_mask.astype(int)
    risk_map = np.where(multi_risk >= 2, 4, risk_map)
    
    # 6. Thống kê
    pixel_area_ha = (PIXEL_SIZE ** 2) / 10000
    
    flood_area = np.sum(flood_mask) * pixel_area_ha
    landslide_area = np.sum(landslide_mask) * pixel_area_ha
    mine_area = np.sum(mine_mask) * pixel_area_ha
    
    flood_pixels = np.sum(flood_mask)
    landslide_pixels = np.sum(landslide_mask)
    
    # Đếm risk levels
    risk_counts = {
        "Normal (0)": int(np.sum(risk_map == 0)),
        "Low (1)": int(np.sum(risk_map == 1)),
        "Medium (2)": int(np.sum(risk_map == 2)),
        "High (3)": int(np.sum(risk_map == 3)),
        "Extreme (4)": int(np.sum(risk_map == 4)),
    }
    
    # 7. Tạo hotspots
    from scipy import ndimage
    
    hotspots = []
    for level in [2, 3, 4]:
        mask = risk_map >= level
        if np.any(mask):
            labeled, num = ndimage.label(mask)
            for i in range(1, num + 1):
                component = labeled == i
                area = np.sum(component) * pixel_area_ha
                if area >= 1.0:  # > 1 ha
                    coords = np.argwhere(component)
                    centroid = coords.mean(axis=0)
                    hotspots.append({
                        "id": len(hotspots) + 1,
                        "risk_level": level,
                        "level_name": ["", "", "Medium", "High", "Extreme"][level],
                        "area_ha": float(area),
                        "pixel_count": int(np.sum(component)),
                        "centroid_pixel": [float(centroid[0]), float(centroid[1])]
                    })
    
    # Sắp xếp theo diện tích
    hotspots.sort(key=lambda x: x["area_ha"], reverse=True)
    
    # 8. Tạo báo cáo
    report = f"""
{'='*60}
BÁO CÁO SỰ KIỆN MƯA LŨ (SYNTHETIC)
Tĩnh Túc, Cao Bằng
28/09/2025 - 01/10/2025
{'='*60}

1. TỔNG QUAN
   - Ngày sự kiện: 28/09/2025 - 01/10/2025
   - Dữ liệu: Sentinel-1 (Orbit 55: 29/09, Orbit 91: 01/10)
   - Phương pháp: Change detection + Consensus

2. NGẬP LỤT
   - Diện tích xác nhận: {flood_area:.2f} ha
   - Số pixel: {flood_pixels}
   - Vùng: Thung lũng phía Nam, trũng Đông Nam

3. SẠT LỞ
   - Diện tích phát hiện: {landslide_area:.2f} ha
   - Số pixel: {landslide_pixels}
   - Vùng: Sườn Tây Bắc, sườn Đông (dốc 20-55°)

4. BÃI THẢI MỎ
   - Số vị trí: 3
   - Diện tích: {mine_area:.2f} ha
   - Tọa độ: (20,25), (30,72), (25,85) [pixel]

5. ĐIỂM NÓNG (HOTSPOTS)
   - Tổng số: {len(hotspots)} vị trí
"""
    
    if hotspots:
        report += "   Chi tiết:\n"
        for i, h in enumerate(hotspots[:5], 1):
            report += f"   {i}. {h['level_name']} - {h['area_ha']:.2f} ha @ ({h['centroid_pixel'][0]:.0f}, {h['centroid_pixel'][1]:.0f})\n"
    
    report += f"""
6. PHÂN BỐ RỦI RO
   - Normal (0): {risk_counts['Normal (0)']} pixels
   - Low (1): {risk_counts['Low (1)']} pixels
   - Medium (2): {risk_counts['Medium (2)']} pixels
   - High (3): {risk_counts['High (3)']} pixels
   - Extreme (4): {risk_counts['Extreme (4)']} pixels

7. KHUYẾN NGHỊ
"""
    
    if flood_area > 50:
        report += "   ⚠️ Ngập lụt diện rộng - Cần sơ tán vùng thấp\n"
    if landslide_area > 10:
        report += "   ⚠️ Sạt lở nhiều - Cấm đường vùng núi\n"
    if any(h['risk_level'] >= 3 for h in hotspots):
        report += "   🚨 Có vùng rủi ro cực cao - Ưu tiên cứu hộ\n"
    
    report += "\n" + "="*60 + "\n"
    report += "Ghi chú: Đây là dữ liệu synthetic cho demo.\n"
    report += "Để có kết quả thực, chạy GEE script:\n"
    report += "  gee_scripts/06_flood_event_20250929_1001.js\n"
    report += "="*60 + "\n"
    
    # 9. Lưu kết quả
    out_dir = Path("outputs/events/20250928_1001")
    out_dir.mkdir(parents=True, exist_ok=True)
    
    np.save(out_dir / "flood_mask.npy", flood_mask)
    np.save(out_dir / "landslide_mask.npy", landslide_mask)
    np.save(out_dir / "mine_mask.npy", mine_mask)
    np.save(out_dir / "risk_map.npy", risk_map)
    np.save(out_dir / "slope.npy", slope)
    np.save(out_dir / "elevation.npy", elevation)
    
    # Thống kê
    stats = {
        "event_name": "Mưa lũ 28/09-01/10/2025",
        "generated_at": datetime.now().isoformat(),
        "data_type": "synthetic",
        "grid_size": {"H": H, "W": W, "pixel_m": PIXEL_SIZE},
        "flood": {
            "area_ha": float(flood_area),
            "pixels": int(flood_pixels)
        },
        "landslide": {
            "area_ha": float(landslide_area),
            "pixels": int(landslide_pixels)
        },
        "mine_waste": {
            "area_ha": float(mine_area),
            "locations": 3
        },
        "risk_distribution": risk_counts,
        "hotspot_count": len(hotspots)
    }
    
    with open(out_dir / "statistics.json", 'w') as f:
        json.dump(stats, f, indent=2)
    
    with open(out_dir / "hotspots.json", 'w') as f:
        json.dump(hotspots, f, indent=2)
    
    with open(out_dir / "report.txt", 'w', encoding='utf-8') as f:
        f.write(report)
    
    # Lưu CSV cho GIS
    df_stats = pd.DataFrame([{
        "type": "flood",
        "area_ha": float(flood_area),
        "pixels": int(flood_pixels)
    }, {
        "type": "landslide",
        "area_ha": float(landslide_area),
        "pixels": int(landslide_pixels)
    }, {
        "type": "mine_waste",
        "area_ha": float(mine_area),
        "pixels": int(np.sum(mine_mask))
    }])
    df_stats.to_csv(out_dir / "areas.csv", index=False)
    
    logger.info(f"\n{'='*60}")
    logger.info("KẾT QUẢ SYNTHETIC ĐÃ TẠO")
    logger.info(f"{'='*60}")
    logger.info(f"Ngập lụt: {flood_area:.2f} ha ({flood_pixels} pixels)")
    logger.info(f"Sạt lở: {landslide_area:.2f} ha ({landslide_pixels} pixels)")
    logger.info(f"Bãi thải: {mine_area:.2f} ha (3 vị trí)")
    logger.info(f"Hotspots: {len(hotspots)} vị trí")
    logger.info(f"\nLưu tại: {out_dir}/")
    logger.info(f"  - report.txt")
    logger.info(f"  - statistics.json")
    logger.info(f"  - flood_mask.npy")
    logger.info(f"  - landslide_mask.npy")
    logger.info(f"  - risk_map.npy")
    
    return stats

if __name__ == "__main__":
    generate_synthetic_event_data()
