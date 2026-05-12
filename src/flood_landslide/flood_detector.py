"""
flood_detector.py
=================
Phát hiện ngập lụt từ Sentinel-1 SAR.

Nguyên lý:
- Nước phẳng làm giảm backscatter (VH < -10 dB)
- So sánh trước-sau (change detection)
- Consensus 3 track để giảm false alarm
"""

import numpy as np
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FloodDetector:
    """
    Phát hiện ngập lụt từ Sentinel-1 GRD.
    
    Parameters
    ----------
    aoi_bbox : List[float]
        [lon_min, lat_min, lon_max, lat_max]
    orbit_numbers : List[int]
        Danh sách orbit (55, 91, 128)
    threshold_sigma : float
        Hệ số sigma cho ngưỡng thích nghi (mặc định 1.5)
    """
    
    def __init__(
        self,
        aoi_bbox: List[float],
        orbit_numbers: List[int] = None,  # Default: [55] - Primary orbit
        threshold_sigma: float = 1.5,
        slope_threshold: float = 5.0
    ):
        self.aoi = aoi_bbox
        # Default to Orbit 55 (Primary orbit with best coverage)
        self.orbits = orbit_numbers if orbit_numbers is not None else [55]
        self.sigma = threshold_sigma
        self.slope_thresh = slope_threshold
        
        logger.info(f"FloodDetector initialized: AOI={aoi_bbox}, orbits={self.orbits}")
        if 55 in self.orbits:
            logger.info("  Using Orbit 55 (ASCENDING) - Primary orbit with 544 images (48% coverage)")
    
    def calculate_adaptive_threshold(
        self,
        diff_vh: np.ndarray,
        stable_mask: Optional[np.ndarray] = None
    ) -> float:
        """
        Tính ngưỡng thích nghi: μ - 1.5σ
        
        Parameters
        ----------
        diff_vh : np.ndarray
            Sai biệt VH (post - pre) trong dB
        stable_mask : np.ndarray
            Mask vùng ổn định (không ngập lịch sử)
            
        Returns
        -------
        float : Ngưỡng trong dB
        """
        if stable_mask is not None:
            stable_diff = diff_vh[stable_mask]
        else:
            # Loại bỏ outliers (5-95 percentile)
            p5, p95 = np.percentile(diff_vh, [5, 95])
            stable_diff = diff_vh[(diff_vh > p5) & (diff_vh < p95)]
        
        mu = np.mean(stable_diff)
        sigma = np.std(stable_diff)
        threshold = mu - self.sigma * sigma
        
        logger.info(f"Adaptive threshold: {threshold:.2f} dB (μ={mu:.2f}, σ={sigma:.2f})")
        return threshold
    
    def detect_flood_single_orbit(
        self,
        diff_vh: np.ndarray,
        slope: np.ndarray,
        permanent_water: Optional[np.ndarray] = None,
        stable_mask: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Phát hiện ngập từ 1 orbit.
        
        Returns
        -------
        np.ndarray : Boolean mask (True = ngập)
        """
        # Ngưỡng thích nghi
        threshold = self.calculate_adaptive_threshold(diff_vh, stable_mask)
        
        # Điều kiện ngập:
        # 1. VH giảm > ngưỡng (âm lớn)
        # 2. Độ dốc < 5° (vùng bằng)
        # 3. Không phải nước thường xuyên
        flood_mask = (
            (diff_vh < threshold) &
            (slope < self.slope_thresh)
        )
        
        if permanent_water is not None:
            flood_mask = flood_mask & (~permanent_water)
        
        # Loại bỏ pixel nhỏ (noise) bằng morphological opening
        from scipy import ndimage
        flood_mask = ndimage.binary_opening(flood_mask, iterations=1)
        
        logger.info(f"Single orbit detection: {np.sum(flood_mask)} pixels")
        return flood_mask
    
    def consensus_detection(
        self,
        flood_masks: Dict[int, np.ndarray],
        min_agreement: int = 2
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Consensus detection từ nhiều orbit.
        
        Parameters
        ----------
        flood_masks : Dict[int, np.ndarray]
            {orbit: mask} cho từng orbit
        min_agreement : int
            Số orbit tối thiểu để xác nhận (mặc định 2)
            
        Returns
        -------
        (confirmed, suspect) : Tuple[np.ndarray, np.ndarray]
            confirmed: ≥ min_agreement
            suspect: = 1
        """
        # Stack masks
        mask_stack = np.stack(list(flood_masks.values()), axis=0)
        agreement = np.sum(mask_stack, axis=0)
        
        confirmed = agreement >= min_agreement
        suspect = agreement == 1
        
        logger.info(
            f"Consensus: {np.sum(confirmed)} confirmed, "
            f"{np.sum(suspect)} suspect (from {len(flood_masks)} orbits)"
        )
        return confirmed, suspect
    
    def calculate_flood_statistics(
        self,
        flood_mask: np.ndarray,
        pixel_size: float = 10.0
    ) -> Dict:
        """
        Tính thống kê diện tích ngập.
        
        Parameters
        ----------
        flood_mask : np.ndarray
            Boolean mask ngập
        pixel_size : float
            Kích thước pixel (m)
            
        Returns
        -------
        Dict : Thống kê diện tích
        """
        pixel_area = pixel_size ** 2
        area_m2 = np.sum(flood_mask) * pixel_area
        area_ha = area_m2 / 10000
        
        stats = {
            "area_m2": float(area_m2),
            "area_ha": float(area_ha),
            "pixel_count": int(np.sum(flood_mask)),
            "percentage": float(np.sum(flood_mask) / flood_mask.size * 100)
        }
        
        logger.info(f"Flood area: {area_ha:.2f} ha ({stats['pixel_count']} pixels)")
        return stats
    
    def run_full_detection(
        self,
        diff_vh_dict: Dict[int, np.ndarray],
        slope: np.ndarray,
        permanent_water: Optional[np.ndarray] = None,
        stable_mask: Optional[np.ndarray] = None,
        built_up: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Chạy pipeline phát hiện ngập đầy đủ.
        
        Parameters
        ----------
        diff_vh_dict : Dict[int, np.ndarray]
            Sai biệt VH cho từng orbit
        slope : np.ndarray
            Bản đồ độ dốc
        permanent_water : np.ndarray
            Mask nước thường xuyên
        stable_mask : np.ndarray
            Mask vùng ổn định
        built_up : np.ndarray
            Mask khu dân cư
            
        Returns
        -------
        Dict : Kết quả phát hiện
        """
        logger.info("Starting flood detection pipeline...")
        
        # Phát hiện từng orbit
        flood_masks = {}
        for orbit, diff_vh in diff_vh_dict.items():
            logger.info(f"Processing orbit {orbit}...")
            flood_masks[orbit] = self.detect_flood_single_orbit(
                diff_vh, slope, permanent_water, stable_mask
            )
        
        # Consensus
        confirmed, suspect = self.consensus_detection(flood_masks, min_agreement=2)
        
        # Loại khu dân cư
        if built_up is not None:
            confirmed = confirmed & (~built_up)
            suspect = suspect & (~built_up)
        
        # Thống kê
        confirmed_stats = self.calculate_flood_statistics(confirmed)
        suspect_stats = self.calculate_flood_statistics(suspect)
        
        results = {
            "flood_confirmed": confirmed,
            "flood_suspect": suspect,
            "flood_all": confirmed | suspect,
            "orbit_masks": flood_masks,
            "statistics": {
                "confirmed": confirmed_stats,
                "suspect": suspect_stats,
                "total_ha": confirmed_stats["area_ha"] + suspect_stats["area_ha"]
            }
        }
        
        logger.info(
            f"Detection complete: {results['statistics']['total_ha']:.2f} ha total"
        )
        return results


class FloodChangeDetector:
    """
    Change detection cho chuỗi thời gian ngập lụt.
    """
    
    def __init__(self, baseline_period_days: int = 30):
        self.baseline_days = baseline_period_days
    
    def create_baseline(
        self,
        vh_series: List[np.ndarray],
        dates: List[datetime]
    ) -> np.ndarray:
        """
        Tạo ảnh baseline từ chuỗi thời gian.
        
        Parameters
        ----------
        vh_series : List[np.ndarray]
            Chuỗi ảnh VH
        dates : List[datetime]
            Ngày tương ứng
            
        Returns
        -------
        np.ndarray : Baseline (median)
        """
        # Stack và tính median
        stack = np.stack(vh_series, axis=0)
        baseline = np.median(stack, axis=0)
        
        logger.info(f"Baseline created from {len(vh_series)} images")
        return baseline
    
    def detect_changes(
        self,
        new_image: np.ndarray,
        baseline: np.ndarray,
        threshold_db: float = -3.0
    ) -> np.ndarray:
        """
        Phát hiện thay đổi so với baseline.
        """
        diff = new_image - baseline
        change_mask = diff < threshold_db
        
        return change_mask
