import numpy as np
import rasterio
from src.flood_landslide.flood_detector import FloodDetector
import logging
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_real_baseline_test():
    tif_path = r"D:\tinhtuc_insar_project\gee_results\harmonic_baseline_orbit55_vh.tif"
    
    if not os.path.exists(tif_path):
        print(f"Lỗi: Không tìm thấy file {tif_path}")
        return
        
    print(f"=== ĐỌC FILE THẬT: {tif_path} ===")
    with rasterio.open(tif_path) as src:
        # Band 1: mean_vh, Band 2: std_vh
        mean_vh = src.read(1)
        std_vh = src.read(2)
        
        # In thông tin file
        print(f"- Kích thước ảnh: {src.shape}")
        print(f"- Độ phân giải: {src.res} (m/pixel)")
        print(f"- CRS: {src.crs}")
        print(f"- Mean VH (trung bình): {np.nanmean(mean_vh):.2f} dB")
        print(f"- StdDev VH (trung bình): {np.nanmean(std_vh):.2f} dB")
        
        # 1. Khởi tạo detector (dùng 10m/pixel do GEE scale=10)
        # Giả sử BBox là toàn bộ ảnh
        bounds = src.bounds
        aoi_bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
        detector = FloodDetector(aoi_bbox=aoi_bbox, orbit_numbers=[55])
        
        # 2. Sinh dữ liệu sự kiện (POST-EVENT) dựa trên nền tảng THẬT
        # Bắt đầu với post_vh bằng đúng mean_vh để giả lập không có gì thay đổi
        post_vh = mean_vh.copy()
        
        # Tạo một vụ ngập lụt "giả lập" ở giữa tâm bức ảnh (kích thước 100x100 pixel = 1km2)
        height, width = mean_vh.shape
        cy, cx = height // 2, width // 2
        
        # Giảm VH đi một lượng bằng 4 lần độ lệch chuẩn để tạo Nước Tĩnh (Open Water)
        post_vh[cy-50:cy+50, cx-50:cx+50] -= 4 * std_vh[cy-50:cy+50, cx-50:cx+50]
        
        # 3. Tạo mô hình thủy văn giả định (do chưa có DEM thật)
        # Cho toàn bộ vùng là đồng bằng (hand=5, slope=2) để ngập lụt được thông qua
        hand = np.full((height, width), 5.0)
        slope = np.full((height, width), 2.0)
        
        post_vh_dict = {55: post_vh}
        mean_vh_dict = {55: mean_vh}
        std_vh_dict = {55: std_vh}
        
        # 4. Chạy Detection
        print("\n=== CHẠY Z-SCORE ANOMALY TRÊN DỮ LIỆU THẬT ===")
        results = detector.run_full_detection(
            post_vh_dict=post_vh_dict,
            mean_vh_dict=mean_vh_dict,
            std_vh_dict=std_vh_dict,
            hand=hand,
            slope=slope
        )
        
        print("\n[KẾT QUẢ PHÂN TÍCH]")
        print(f"- Open Water: {results['statistics']['open_water_ha']} ha")
        print(f"- Flooded Vegetation: {results['statistics']['flooded_veg_ha']} ha")
        print(f"- Tổng diện tích: {results['statistics']['total_ha']} ha")

if __name__ == "__main__":
    run_real_baseline_test()
