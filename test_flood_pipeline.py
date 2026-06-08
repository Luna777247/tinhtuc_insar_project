import numpy as np
from src.flood_landslide.flood_detector import FloodDetector, OpticalFusionTrigger
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def test_new_flood_pipeline():
    print("=== KIỂM THỬ THUẬT TOÁN NGẬP LỤT Z-SCORE ANOMALY & HAND ===")
    
    # 1. Khởi tạo detector
    aoi_bbox = [105.85, 22.65, 105.95, 22.75]
    detector = FloodDetector(aoi_bbox=aoi_bbox, orbit_numbers=[55, 91])
    
    # 2. Tạo mảng dữ liệu giả lập (mock data) kích thước 100x100 pixel (10m/pixel = 1km2)
    shape = (100, 100)
    
    # Baseline: Trung bình VH mùa khô là -12 dB, độ lệch chuẩn 1.5 dB
    mean_vh = np.full(shape, -12.0)
    std_vh = np.full(shape, 1.5)
    
    # Post-event VH: 
    # - Vùng 1: Open Water (-18 dB -> Z ~ -4.0)
    # - Vùng 2: Flooded Vegetation / Bùn (-6 dB -> Z ~ +4.0)
    # - Vùng 3: Bình thường (-11 dB -> Z ~ +0.66)
    post_vh = np.full(shape, -11.0)
    post_vh[10:30, 10:30] = -18.0  # Open water (20x20 = 400 pixel)
    post_vh[70:90, 70:90] = -6.0   # Flooded veg (20x20 = 400 pixel)
    
    # Mô hình thủy văn
    hand = np.full(shape, 10.0) # Mặc định cao hơn suối 10m
    hand[10:30, 10:30] = 5.0    # Vùng 1 ngập: Rất gần suối (hợp lý)
    hand[70:90, 70:90] = 50.0   # Vùng 2: Trên sườn núi cách suối 50m (Báo động giả, sẽ bị chặn)
    
    slope = np.full(shape, 2.0) # Địa hình tương đối bằng phẳng
    slope[70:90, 70:90] = 15.0  # Vùng 2: Sườn dốc 15 độ (Sẽ bị chặn)
    
    # Đóng gói dữ liệu cho orbit 55
    post_vh_dict = {55: post_vh}
    mean_vh_dict = {55: mean_vh}
    std_vh_dict = {55: std_vh}
    
    # 3. Chạy pipeline
    results = detector.run_full_detection(
        post_vh_dict=post_vh_dict,
        mean_vh_dict=mean_vh_dict,
        std_vh_dict=std_vh_dict,
        hand=hand,
        slope=slope
    )
    
    print("\n[KẾT QUẢ]")
    print(f"- Open Water (Nước mặt tĩnh): {results['statistics']['open_water_ha']} ha")
    print(f"- Flooded Vegetation (Nước xù xì/Tán cây): {results['statistics']['flooded_veg_ha']} ha")
    print(f"- Tổng ngập lụt: {results['statistics']['total_ha']} ha")
    
    # 4. Kiểm tra Trigger Giai đoạn 3
    trigger = OpticalFusionTrigger(rainfall_threshold_mm=100.0)
    print("\n[KIỂM TRA TRIGGER]")
    trigger.check_trigger(rainfall_24h=150.5)

if __name__ == "__main__":
    test_new_flood_pipeline()
