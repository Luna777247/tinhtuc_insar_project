"""
level1_proxy.py
===============
Cấp 1: Phát hiện sụt lún gián tiếp (Proxy) qua backscatter trend.

Phương pháp:
- Long-term VH/VV trend analysis (linear regression)
- Temporal variance & stability index
- Hotspot detection vùng biến động mạnh

Độ chính xác: qualitative (visual change, hotspot screening)
Dữ liệu: Sentinel-1 GRD từ GEE

Reference: Phần 0.6 tài liệu Sentinel1_TinhTuc_PhanTich_KichBan_ChiTiet.md
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
import warnings

logger = logging.getLogger(__name__)


@dataclass
class ProxyDetectionResult:
    """Kết quả phát hiện proxy subsidence"""
    hotspot_mask: np.ndarray          # Vùng nghi ngờ (boolean)
    stability_index: np.ndarray       # Chỉ số bất ổn (0-1)
    trend_slope: np.ndarray          # Độ dốc xu hướng VH/VV
    variance_map: np.ndarray         # Phương sai thời gian
    change_points: np.ndarray        # Điểm thay đổi đột ngột
    metadata: Dict                   # Thông tin phân tích


class ProxySubsidenceDetector:
    """
    Cấp 1: Phát hiện sụt lún proxy qua backscatter trend.
    
    Parameters
    ----------
    stability_threshold : float
        Ngưỡng chỉ số bất ổn (default: 0.7)
    trend_threshold : float  
        Ngưỡng độ dốc xu hướng dB/năm (default: -2.0)
    variance_threshold : float
        Ngưỡng phương sai (default: 5.0)
    min_timeseries_length : int
        Số ảnh tối thiểu (default: 10)
    """
    
    def __init__(
        self,
        stability_threshold: float = 0.7,
        trend_threshold: float = -2.0,  # VH giảm 2dB/năm
        variance_threshold: float = 5.0,
        min_timeseries_length: int = 10
    ):
        self.stability_threshold = stability_threshold
        self.trend_threshold = trend_threshold
        self.variance_threshold = variance_threshold
        self.min_timeseries_length = min_timeseries_length
        
        logger.info(f"ProxySubsidenceDetector: stability_threshold={stability_threshold}, "
                   f"trend_threshold={trend_threshold} dB/year")
    
    def analyze_backscatter_trend(
        self,
        vh_timeseries: np.ndarray,  # Shape: (n_time, height, width)
        vv_timeseries: np.ndarray,
        dates: List[datetime],
        mask: Optional[np.ndarray] = None
    ) -> ProxyDetectionResult:
        """
        Phân tích xu hướng backscatter dài hạn.
        
        Parameters
        ----------
        vh_timeseries : np.ndarray
            Chuỗi thời gian VH (dB), shape (n_time, H, W)
        vv_timeseries : np.ndarray
            Chuỗi thời gian VV (dB), shape (n_time, H, W)
        dates : List[datetime]
            Danh sách ngày
        mask : np.ndarray, optional
            Mask vùng ROI
            
        Returns
        -------
        ProxyDetectionResult
            Kết quả phân tích
        """
        n_time = len(dates)
        if n_time < self.min_timeseries_length:
            raise ValueError(f"Cần ít nhất {self.min_timeseries_length} ảnh, có {n_time}")
        
        logger.info(f"Analyzing {n_time} images over {(dates[-1] - dates[0]).days} days")
        
        # Tính thời gian (năm)
        times = np.array([(d - dates[0]).days / 365.25 for d in dates])
        
        # Khởi tạo kết quả
        _, height, width = vh_timeseries.shape
        trend_vh = np.zeros((height, width), dtype=np.float32)
        trend_vv = np.zeros((height, width), dtype=np.float32)
        variance_vh = np.zeros((height, width), dtype=np.float32)
        
        # Tính trend bằng linear regression (theo pixel)
        logger.info("Computing linear trends...")
        for i in range(height):
            for j in range(width):
                if mask is not None and not mask[i, j]:
                    continue
                    
                vh_pixel = vh_timeseries[:, i, j]
                vv_pixel = vv_timeseries[:, i, j]
                
                # Bỏ qua NaN
                valid = ~(np.isnan(vh_pixel) | np.isnan(vv_pixel))
                if valid.sum() < 5:
                    continue
                
                # Linear regression: y = a*x + b
                # Trend slope (dB/year)
                trend_vh[i, j] = self._linear_slope(times[valid], vh_pixel[valid])
                trend_vv[i, j] = self._linear_slope(times[valid], vv_pixel[valid])
                variance_vh[i, j] = np.var(vh_pixel[valid])
        
        # Tính stability index (0 = ổn định, 1 = bất ổn)
        logger.info("Computing stability index...")
        stability_index = self._compute_stability_index(
            trend_vh, trend_vv, variance_vh
        )
        
        # Phát hiện hotspot
        logger.info("Detecting hotspots...")
        hotspot_mask = self._detect_hotspots(
            stability_index, trend_vh, variance_vh
        )
        
        # Phát hiện change points
        logger.info("Detecting change points...")
        change_points = self._detect_change_points(vh_timeseries, dates)
        
        # Metadata
        metadata = {
            "n_images": n_time,
            "date_range": (dates[0].isoformat(), dates[-1].isoformat()),
            "stability_threshold": self.stability_threshold,
            "trend_threshold": self.trend_threshold,
            "n_hotspots": int(hotspot_mask.sum()),
            "analysis_type": "Level 1 - Proxy Detection (GEE GRD)"
        }
        
        logger.info(f"Detected {metadata['n_hotspots']} potential instability hotspots")
        
        return ProxyDetectionResult(
            hotspot_mask=hotspot_mask,
            stability_index=stability_index,
            trend_slope=trend_vh,  # Dùng VH làm đại diện
            variance_map=variance_vh,
            change_points=change_points,
            metadata=metadata
        )
    
    def _linear_slope(self, x: np.ndarray, y: np.ndarray) -> float:
        """Tính độ dốc hồi quy tuyến tính"""
        if len(x) < 2:
            return 0.0
        
        # Least squares: slope = Cov(x,y) / Var(x)
        x_mean, y_mean = np.mean(x), np.mean(y)
        cov = np.sum((x - x_mean) * (y - y_mean))
        var = np.sum((x - x_mean) ** 2)
        
        if var == 0:
            return 0.0
        
        return cov / var
    
    def _compute_stability_index(
        self,
        trend_vh: np.ndarray,
        trend_vv: np.ndarray,
        variance: np.ndarray
    ) -> np.ndarray:
        """
        Tính chỉ số bất ổn (0-1).
        
        Kết hợp:
        - Độ lớn của trend (|slope|)
        - Phương sai (variance)
        - VH/VV consistency
        """
        # Normalize trend magnitude (0-1)
        trend_mag = np.abs(trend_vh)
        trend_norm = np.clip(trend_mag / 5.0, 0, 1)  # 5 dB/year = max
        
        # Normalize variance (0-1)
        variance_norm = np.clip(variance / 10.0, 0, 1)  # variance 10 = max
        
        # VH/VV consistency (đồng nhất giảm = instability)
        trend_consistency = np.abs(trend_vh - trend_vv) / 2.0
        consistency_norm = np.clip(trend_consistency / 3.0, 0, 1)
        
        # Combined stability index (trung bình có trọng số)
        stability = (
            0.4 * trend_norm +
            0.4 * variance_norm +
            0.2 * consistency_norm
        )
        
        return np.clip(stability, 0, 1).astype(np.float32)
    
    def _detect_hotspots(
        self,
        stability_index: np.ndarray,
        trend_vh: np.ndarray,
        variance: np.ndarray
    ) -> np.ndarray:
        """
        Phát hiện vùng nghi ngờ bất ổn.
        
        Điều kiện:
        - Stability index cao (> threshold)
        - Trend VH giảm mạnh (< threshold)
        - Variance cao (> threshold)
        """
        hotspot = (
            (stability_index > self.stability_threshold) |
            (trend_vh < self.trend_threshold) |
            (variance > self.variance_threshold)
        )
        
        # Morphological filtering để loại bỏ noise
        from scipy import ndimage
        hotspot = ndimage.binary_opening(hotspot, iterations=1)
        hotspot = ndimage.binary_closing(hotspot, iterations=2)
        
        return hotspot
    
    def _detect_change_points(
        self,
        timeseries: np.ndarray,
        dates: List[datetime],
        window_size: int = 5
    ) -> np.ndarray:
        """
        Phát hiện điểm thay đổi đột ngột (CUSUM-like).
        
        Parameters
        ----------
        timeseries : np.ndarray
            Shape (n_time, H, W)
        window_size : int
            Kích thước cửa sổ sliding
            
        Returns
        -------
        np.ndarray
            Số lần thay đổi đột ngột tại mỗi pixel
        """
        n_time, height, width = timeseries.shape
        change_count = np.zeros((height, width), dtype=np.int32)
        
        # Sliding window change detection
        for t in range(window_size, n_time - window_size):
            before = np.mean(timeseries[t-window_size:t], axis=0)
            after = np.mean(timeseries[t:t+window_size], axis=0)
            
            # Change nếu chênh lệch > 3 dB
            significant_change = np.abs(after - before) > 3.0
            change_count += significant_change.astype(np.int32)
        
        return change_count
    
    def generate_report(self, result: ProxyDetectionResult) -> str:
        """Tạo báo cáo tóm tắt"""
        meta = result.metadata
        
        report = f"""
========================================
BÁO CÁO PHÁT HIỆN SỤT LÚN PROXY (CẤP 1)
========================================

Thông tin phân tích:
- Loại: {meta['analysis_type']}
- Số ảnh: {meta['n_images']}
- Khoảng thời gian: {meta['date_range'][0][:10]} → {meta['date_range'][1][:10]}

Kết quả:
- Số vùng nghi ngờ (hotspots): {meta['n_hotspots']} pixels
- Chỉ số bất ổn trung bình: {np.mean(result.stability_index):.3f}
- Xu hướng VH trung bình: {np.mean(result.trend_slope):.2f} dB/year

⚠️ LƯU Ý QUAN TRỌNG:
Đây là phân tích PROXY (gián tiếp) qua backscatter trend.
KHÔNG phải đo sụt lún chính xác mm-level.

Để đo chính xác:
→ Dùng Cấp 3: SBAS-InSAR với SLC data (ASF HyP3 + MintPy)

========================================
"""
        return report
