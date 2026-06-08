"""
flood_detector.py
=================
Phát hiện ngập lụt từ Sentinel-1 SAR (Đã nâng cấp theo chuẩn Geophysics/Hydrology).

Giai đoạn 1: Nâng cấp Thuật toán Nhận diện (Z-Score Anomaly)
- Tìm Open Water (Z < -2.5)
- Tìm Flooded Vegetation/Rough Water (Z > 2.5)

Giai đoạn 2: Khóa chặt Báo động giả bằng Mô hình Thủy văn
- Sử dụng chỉ số HAND (Height Above Nearest Drainage)
- Sử dụng Slope (Độ dốc)
"""

import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from scipy import ndimage

logger = logging.getLogger(__name__)


class FloodDetector:
    """
    Phát hiện ngập lụt từ Sentinel-1 GRD sử dụng thống kê chuỗi thời gian (Z-Score)
    và mô hình thủy văn (HAND).
    
    Parameters
    ----------
    aoi_bbox : List[float]
        [lon_min, lat_min, lon_max, lat_max]
    orbit_numbers : List[int]
        Danh sách orbit (55, 91, 128)
    slope_threshold : float
        Độ dốc tối đa có thể giữ nước (mặc định 5.0 độ)
    hand_threshold : float
        Độ cao tối đa so với suối gần nhất (mặc định 15.0 m)
    z_score_threshold : float
        Ngưỡng bất thường thống kê (mặc định 2.5)
    """
    
    def __init__(
        self,
        aoi_bbox: List[float],
        orbit_numbers: List[int] = None,
        slope_threshold: float = 5.0,
        hand_threshold: float = 15.0,
        z_score_threshold: float = 2.5
    ):
        self.aoi = aoi_bbox
        self.orbits = orbit_numbers if orbit_numbers is not None else [55]
        self.slope_thresh = slope_threshold
        self.hand_thresh = hand_threshold
        self.z_thresh = z_score_threshold
        
        logger.info(f"FloodDetector initialized: AOI={aoi_bbox}, orbits={self.orbits}")
        logger.info(f"Thresholds: Slope <= {self.slope_thresh}°, HAND <= {self.hand_thresh}m, |Z-Score| > {self.z_thresh}")
    
    def detect_flood_single_orbit(
        self,
        post_vh: np.ndarray,
        mean_vh: np.ndarray,
        std_vh: np.ndarray,
        post_vv: np.ndarray,
        mean_vv: np.ndarray,
        std_vv: np.ndarray,
        hand: np.ndarray,
        slope: np.ndarray,
        permanent_water: Optional[np.ndarray] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Phát hiện ngập từ 1 orbit. 
        Sử dụng VH cho Open Water và VV cho Flooded Vegetation (Double-bounce).
        """
        # Tránh chia cho 0
        std_vh_safe = np.where(std_vh == 0, 1e-6, std_vh)
        std_vv_safe = np.where(std_vv == 0, 1e-6, std_vv)
        
        # 1. Tính Z-Score Anomaly riêng cho 2 phân cực
        z_score_vh = (post_vh - mean_vh) / std_vh_safe
        z_score_vv = (post_vv - mean_vv) / std_vv_safe
        
        # 2. Hai nhánh nhận diện chuẩn vật lý
        # Open Water làm giảm mạnh phân cực chéo VH
        open_water = z_score_vh < -self.z_thresh
        # Ngập dưới tán cây tạo Double-bounce làm tăng vọt phân cực đồng phẳng VV
        flooded_veg = z_score_vv > self.z_thresh
        
        # 3. Khóa chặt bằng Mô hình Thủy văn (HAND & Slope)
        topo_mask = (hand <= self.hand_thresh) & (slope <= self.slope_thresh)
        
        open_water = open_water & topo_mask
        flooded_veg = flooded_veg & topo_mask
        
        if permanent_water is not None:
            open_water = open_water & (~permanent_water)
            flooded_veg = flooded_veg & (~permanent_water)
            
        # Loại bỏ pixel nhỏ (noise) bằng morphological opening
        open_water = ndimage.binary_opening(open_water, iterations=1)
        flooded_veg = ndimage.binary_opening(flooded_veg, iterations=1)
        
        logger.info(f"Single orbit detection: Open Water = {np.sum(open_water)} px, Flooded Veg = {np.sum(flooded_veg)} px")
        return open_water, flooded_veg
    
    def consensus_detection(
        self,
        flood_masks: Dict[int, np.ndarray],
        min_agreement: int = 2
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Consensus detection từ nhiều orbit.
        """
        if not flood_masks:
            return np.array([]), np.array([])
            
        mask_stack = np.stack(list(flood_masks.values()), axis=0)
        agreement = np.sum(mask_stack, axis=0)
        
        confirmed = agreement >= min_agreement
        suspect = agreement == 1
        
        return confirmed, suspect
    
    def calculate_flood_statistics(
        self,
        flood_mask: np.ndarray,
        pixel_size: float = 10.0
    ) -> Dict:
        """
        Tính thống kê diện tích ngập.
        """
        if flood_mask.size == 0:
            return {"area_m2": 0.0, "area_ha": 0.0, "pixel_count": 0, "percentage": 0.0}
            
        pixel_area = pixel_size ** 2
        area_m2 = np.sum(flood_mask) * pixel_area
        area_ha = area_m2 / 10000
        
        stats = {
            "area_m2": float(area_m2),
            "area_ha": float(area_ha),
            "pixel_count": int(np.sum(flood_mask)),
            "percentage": float(np.sum(flood_mask) / flood_mask.size * 100)
        }
        return stats
    
    def run_full_detection(
        self,
        post_vh_dict: Dict[int, np.ndarray],
        mean_vh_dict: Dict[int, np.ndarray],
        std_vh_dict: Dict[int, np.ndarray],
        post_vv_dict: Dict[int, np.ndarray],
        mean_vv_dict: Dict[int, np.ndarray],
        std_vv_dict: Dict[int, np.ndarray],
        hand: np.ndarray,
        slope: np.ndarray,
        permanent_water: Optional[np.ndarray] = None,
        built_up: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Chạy pipeline phát hiện ngập đầy đủ dựa trên Z-Score Anomaly và Thủy văn.
        """
        logger.info("Starting advanced flood detection pipeline...")
        
        open_water_masks = {}
        flooded_veg_masks = {}
        
        for orbit in post_vh_dict.keys():
            logger.info(f"Processing orbit {orbit}...")
            ow, fv = self.detect_flood_single_orbit(
                post_vh_dict[orbit],
                mean_vh_dict[orbit],
                std_vh_dict[orbit],
                post_vv_dict[orbit],
                mean_vv_dict[orbit],
                std_vv_dict[orbit],
                hand,
                slope,
                permanent_water
            )
            open_water_masks[orbit] = ow
            flooded_veg_masks[orbit] = fv
        
        # Hợp nhất Consensus cho cả 2 loại ngập
        # Lưu ý: Do độ trễ vệ tinh 12 ngày, đôi khi ảnh ASC chụp lúc ngập, DESC chụp lúc cạn.
        # Ở môi trường núi, nên dùng min_agreement=1 (suspect) làm vùng ngập tổng nếu chỉ có dữ liệu từ 1 quỹ đạo gần ngày mưa.
        # Để an toàn, lấy tổng mask của tất cả orbit (Logical OR).
        
        total_open_water = np.zeros_like(slope, dtype=bool)
        total_flooded_veg = np.zeros_like(slope, dtype=bool)
        
        for orbit in open_water_masks.keys():
            total_open_water = total_open_water | open_water_masks[orbit]
            total_flooded_veg = total_flooded_veg | flooded_veg_masks[orbit]
        
        # Loại khu dân cư khỏi cảnh báo (nếu cần thiết, hoặc giữ để biết ngập đô thị)
        if built_up is not None:
            total_open_water = total_open_water & (~built_up)
            total_flooded_veg = total_flooded_veg & (~built_up)
            
        all_flood = total_open_water | total_flooded_veg
        
        # Thống kê
        ow_stats = self.calculate_flood_statistics(total_open_water)
        fv_stats = self.calculate_flood_statistics(total_flooded_veg)
        all_stats = self.calculate_flood_statistics(all_flood)
        
        results = {
            "open_water_mask": total_open_water,
            "flooded_veg_mask": total_flooded_veg,
            "total_flood_mask": all_flood,
            "statistics": {
                "open_water_ha": ow_stats["area_ha"],
                "flooded_veg_ha": fv_stats["area_ha"],
                "total_ha": all_stats["area_ha"]
            }
        }
        
        logger.info(f"Detection complete: Open Water {ow_stats['area_ha']:.2f} ha, Flooded Veg {fv_stats['area_ha']:.2f} ha.")
        return results

class OpticalFusionTrigger:
    """
    Giai đoạn 3: Hệ thống kích hoạt dữ liệu quang học Sentinel-2.
    """
    def __init__(self, rainfall_threshold_mm: float = 100.0):
        self.rain_thresh = rainfall_threshold_mm
        
    def check_trigger(self, rainfall_24h: float) -> bool:
        if rainfall_24h > self.rain_thresh:
            logger.warning(f"CẢNH BÁO: Lượng mưa {rainfall_24h}mm vượt ngưỡng {self.rain_thresh}mm. Kích hoạt Optical SAR Fusion!")
            return True
        return False
