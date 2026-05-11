"""
landslide_detector.py
=====================
Phát hiện sạt lở từ Sentinel-1 SAR + Sentinel-2 NDVI.

Đặc điểm sạt lở:
- Phá hủy thực vật → giảm NDVI
- Lộ đất đá → tăng backscatter (VH, VV)
- Vùng dốc 20-55°

Xác nhận:
1. SAR: thay đổi backscatter > 3 dB
2. NDVI: giảm > 0.2
3. Slope: 20-55°
"""

import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LandslideDetector:
    """
    Phát hiện sạt lở kết hợp SAR và optical.
    
    Parameters
    ----------
    sar_change_threshold : float
        Ngưỡng thay đổi SAR (dB, mặc định 3.0)
    ndvi_change_threshold : float
        Ngưỡng giảm NDVI (mặc định -0.2)
    slope_range : Tuple[float, float]
        Khoảng độ dốc (độ, mặc định 20-55)
    """
    
    def __init__(
        self,
        sar_change_threshold: float = 3.0,
        ndvi_change_threshold: float = -0.2,
        slope_range: Tuple[float, float] = (20, 55)
    ):
        self.sar_thresh = sar_change_threshold
        self.ndvi_thresh = ndvi_change_threshold
        self.slope_min, self.slope_max = slope_range
        
        logger.info(
            f"LandslideDetector: SAR={sar_change_threshold}dB, "
            f"NDVI={ndvi_change_threshold}, slope={slope_range}"
        )
    
    def detect_sar_changes(
        self,
        diff_vh: np.ndarray,
        diff_vv: Optional[np.ndarray] = None,
        slope: Optional[np.ndarray] = None,
        flood_mask: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Phát hiện thay đổi SAR (dấu hiệu sạt lở).
        
        Parameters
        ----------
        diff_vh : np.ndarray
            Sai biệt VH (post - pre)
        diff_vv : np.ndarray
            Sai biệt VV (tùy chọn)
        slope : np.ndarray
            Bản đồ độ dốc
        flood_mask : np.ndarray
            Mask ngập lụt (loại trùng)
            
        Returns
        -------
        np.ndarray : Boolean mask sạt lở từ SAR
        """
        # Điều kiện 1: Thay đổi VH > ngưỡng (tăng hoặc giảm mạnh)
        sar_mask = np.abs(diff_vh) > self.sar_thresh
        
        # Điều kiện 2: Nếu có VV, cũng phải thay đổi
        if diff_vv is not None:
            sar_mask = sar_mask & (np.abs(diff_vv) > self.sar_thresh * 0.7)
        
        # Điều kiện 3: Độ dốc phù hợp
        if slope is not None:
            slope_mask = (slope > self.slope_min) & (slope < self.slope_max)
            sar_mask = sar_mask & slope_mask
        
        # Điều kiện 4: Không phải ngập lụt
        if flood_mask is not None:
            sar_mask = sar_mask & (~flood_mask)
        
        logger.info(f"SAR changes: {np.sum(sar_mask)} pixels")
        return sar_mask
    
    def confirm_with_ndvi(
        self,
        sar_mask: np.ndarray,
        d_ndvi: np.ndarray,
        forest_mask: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Xác nhận sạt lở bằng NDVI.
        
        Parameters
        ----------
        sar_mask : np.ndarray
            Mask từ SAR
        d_ndvi : np.ndarray
            Thay đổi NDVI (post - pre)
        forest_mask : np.ndarray
            Mask vùng rừng (tùy chọn)
            
        Returns
        -------
        np.ndarray : Boolean mask đã xác nhận
        """
        # NDVI giảm > 0.2
        ndvi_mask = d_ndvi < self.ndvi_thresh
        
        # Chỉ xác nhận nếu cả SAR và NDVI đều phát hiện
        confirmed = sar_mask & ndvi_mask
        
        # Nếu có forest mask, ưu tiên vùng rừng
        if forest_mask is not None:
            # Trong rừng, NDVI giảm mạnh = sạt lở chắc chắn
            forest_confirmed = confirmed & forest_mask
            non_forest_confirmed = confirmed & (~forest_mask)
            
            # Cả hai đều tính, nhưng forest có độ tin cậy cao hơn
            logger.info(
                f"NDVI confirmation: {np.sum(forest_confirmed)} in forest, "
                f"{np.sum(non_forest_confirmed)} non-forest"
            )
        
        logger.info(f"Confirmed landslides: {np.sum(confirmed)} pixels")
        return confirmed
    
    def classify_landslide_type(
        self,
        landslide_mask: np.ndarray,
        slope: np.ndarray,
        dem: Optional[np.ndarray] = None
    ) -> Dict[str, np.ndarray]:
        """
        Phân loại loại sạt lở.
        
        Returns
        -------
        Dict : Masks cho từng loại
        """
        types = {}
        
        if slope is not None:
            # Shallow landslide: 20-30°
            types["shallow"] = landslide_mask & (slope >= 20) & (slope < 30)
            
            # Deep landslide: 30-45°
            types["deep"] = landslide_mask & (slope >= 30) & (slope < 45)
            
            # Rockfall/avalanche: > 45°
            types["rockfall"] = landslide_mask & (slope >= 45)
        
        # Thống kê
        for name, mask in types.items():
            logger.info(f"{name}: {np.sum(mask)} pixels")
        
        return types
    
    def calculate_volume_estimate(
        self,
        landslide_mask: np.ndarray,
        dem: np.ndarray,
        area_per_pixel: float = 100.0  # m²
    ) -> Dict:
        """
        Ước tính thể tích sạt lở đơn giản.
        
        Parameters
        ----------
        landslide_mask : np.ndarray
            Mask sạt lở
        dem : np.ndarray
            Digital Elevation Model
        area_per_pixel : float
            Diện tích mỗi pixel (m²)
            
        Returns
        -------
        Dict : Thống kê thể tích
        """
        if dem is None:
            return {"error": "DEM required for volume estimation"}
        
        # Tính độ cao trung bình trong vùng sạt lở
        heights = dem[landslide_mask]
        if len(heights) == 0:
            return {"volume_m3": 0, "area_m2": 0}
        
        mean_height = np.mean(heights)
        min_height = np.min(heights)
        max_height = np.max(heights)
        
        # Ước tính đơn giản: giả định độ dày trung bình = (max - min) / 3
        estimated_thickness = (max_height - min_height) / 3
        
        area_m2 = np.sum(landslide_mask) * area_per_pixel
        volume_m3 = area_m2 * estimated_thickness
        
        stats = {
            "area_m2": float(area_m2),
            "area_ha": float(area_m2 / 10000),
            "estimated_thickness_m": float(estimated_thickness),
            "volume_m3": float(volume_m3),
            "height_range_m": float(max_height - min_height),
            "mean_elevation_m": float(mean_height)
        }
        
        logger.info(
            f"Volume estimate: {volume_m3:.0f} m³ "
            f"({stats['area_ha']:.2f} ha × {estimated_thickness:.1f} m)"
        )
        return stats
    
    def run_full_detection(
        self,
        diff_vh: np.ndarray,
        d_ndvi: np.ndarray,
        slope: np.ndarray,
        diff_vv: Optional[np.ndarray] = None,
        flood_mask: Optional[np.ndarray] = None,
        forest_mask: Optional[np.ndarray] = None,
        dem: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Chạy pipeline phát hiện sạt lở đầy đủ.
        
        Returns
        -------
        Dict : Kết quả phát hiện
        """
        logger.info("Starting landslide detection pipeline...")
        
        # Bước 1: Phát hiện SAR
        sar_mask = self.detect_sar_changes(
            diff_vh, diff_vv, slope, flood_mask
        )
        
        # Bước 2: Xác nhận NDVI
        confirmed = self.confirm_with_ndvi(sar_mask, d_ndvi, forest_mask)
        
        # Bước 3: Phân loại
        types = self.classify_landslide_type(confirmed, slope, dem)
        
        # Bước 4: Ước tính thể tích
        volume_stats = self.calculate_volume_estimate(confirmed, dem)
        
        results = {
            "sar_candidates": sar_mask,
            "confirmed": confirmed,
            "by_type": types,
            "volume_estimate": volume_stats,
            "statistics": {
                "total_pixels": int(np.sum(confirmed)),
                "sar_only_pixels": int(np.sum(sar_mask & ~confirmed)),
                **volume_stats
            }
        }
        
        logger.info("Landslide detection complete")
        return results


class DebrisFlowDetector:
    """
    Phát hiện dòng chảy bùn đất (debris flow).
    Đặc điểm: Vùng thấp, dốc 28-35°, thay đổi liên tục.
    """
    
    def __init__(self):
        self.slope_range = (28, 35)
        logger.info("DebrisFlowDetector initialized")
    
    def detect_debris_flow_zones(
        self,
        diff_vh: np.ndarray,
        slope: np.ndarray,
        dem: np.ndarray,
        flow_accumulation: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Phát hiện vùng debris flow.
        
        Parameters
        ----------
        diff_vh : np.ndarray
            Thay đổi SAR
        slope : np.ndarray
            Độ dốc
        dem : np.ndarray
            DEM (để tìm vùng thấp)
        flow_accumulation : np.ndarray
            Tích lũy dòng chảy (tùy chọn)
            
        Returns
        -------
        np.ndarray : Mask debris flow
        """
        # Điều kiện: độ dốc 28-35°, thay đổi SAR > 2 dB
        slope_mask = (slope >= self.slope_range[0]) & (slope <= self.slope_range[1])
        change_mask = np.abs(diff_vh) > 2.0
        
        mask = slope_mask & change_mask
        
        # Ưu tiên vùng thấp nếu có DEM
        if dem is not None:
            elevation_threshold = np.percentile(dem, 33)  # 1/3 thấp nhất
            low_mask = dem < elevation_threshold
            mask = mask & low_mask
        
        logger.info(f"Debris flow zones: {np.sum(mask)} pixels")
        return mask
