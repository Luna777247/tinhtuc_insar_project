"""
level2_offset.py
================
Cấp 2: Offset Tracking - Dịch chuyển thô ~0.5m.

Phương pháp:
- Cross-correlation giữa cặp ảnh
- Feature tracking (SIFT/ORB) hoặc pixel-wise correlation
- Đo dịch chuyển ngang/dọc (range/azimuth)

Độ chính xác: ~0.5m (relative deformation)
Dữ liệu: Sentinel-1 GRD từ GEE hoặc local

Reference: Phần 0.6 tài liệu Sentinel1_TinhTuc_PhanTich_KichBan_ChiTiet.md
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass
from scipy import ndimage
from scipy.signal import correlate2d
import warnings

logger = logging.getLogger(__name__)


@dataclass
class OffsetTrackingResult:
    """Kết quả offset tracking"""
    range_offset: np.ndarray      # Dịch chuyển range (m)
    azimuth_offset: np.ndarray    # Dịch chuyển azimuth (m)
    magnitude: np.ndarray         # Độ lớn dịch chuyển (m)
    direction: np.ndarray       # Hướng (rad)
    confidence: np.ndarray      # Độ tin cậy (0-1)
    hotspot_mask: np.ndarray      # Vùng dịch chuyển đáng kể
    metadata: Dict              # Thông tin


class OffsetTrackingDetector:
    """
    Cấp 2: Offset Tracking cho dịch chuyển thô ~0.5m.
    
    Parameters
    ----------
    window_size : int
        Kích thước cửa sổ correlation (default: 32)
    search_range : int
        Phạm vi tìm kiếm (pixels, default: 8)
    min_correlation : float
        Ngưỡng correlation tối thiểu (default: 0.3)
    pixel_size_m : float
        Kích thước pixel (m, default: 10)
    """
    
    def __init__(
        self,
        window_size: int = 32,
        search_range: int = 8,
        min_correlation: float = 0.3,
        pixel_size_m: float = 10.0
    ):
        self.window_size = window_size
        self.search_range = search_range
        self.min_correlation = min_correlation
        self.pixel_size_m = pixel_size_m
        
        logger.info(f"OffsetTrackingDetector: window={window_size}, "
                   f"search_range={search_range}, pixel_size={pixel_size_m}m")
    
    def compute_offset_tracking(
        self,
        image_pre: np.ndarray,   # Ảnh trước (VH hoặc VV, dB)
        image_post: np.ndarray,  # Ảnh sau
        date_pre: datetime,
        date_post: datetime,
        mask: Optional[np.ndarray] = None,
        step_size: int = 8       # Bước nhảy (pixel)
    ) -> OffsetTrackingResult:
        """
        Tính offset tracking giữa 2 ảnh.
        
        Parameters
        ----------
        image_pre : np.ndarray
            Ảnh trước
        image_post : np.ndarray
            Ảnh sau
        date_pre, date_post : datetime
            Thời gian 2 ảnh
        mask : np.ndarray
            Mask ROI
        step_size : int
            Bước nhảy (giảm để tăng resolution)
            
        Returns
        -------
        OffsetTrackingResult
            Kết quả offset tracking
        """
        logger.info(f"Computing offset: {date_pre.date()} → {date_post.date()}")
        
        height, width = image_pre.shape
        
        # Tạo lưới điểm tính offset
        y_coords = np.arange(self.window_size, height - self.window_size, step_size)
        x_coords = np.arange(self.window_size, width - self.window_size, step_size)
        
        # Khởi tạo output (low resolution)
        out_h, out_w = len(y_coords), len(x_coords)
        range_offset = np.zeros((out_h, out_w), dtype=np.float32)
        azimuth_offset = np.zeros((out_h, out_w), dtype=np.float32)
        confidence = np.zeros((out_h, out_w), dtype=np.float32)
        
        logger.info(f"Processing {len(y_coords) * len(x_coords)} windows...")
        
        # Tính offset cho từng cửa sổ
        for i, y in enumerate(y_coords):
            for j, x in enumerate(x_coords):
                if mask is not None:
                    # Kiểm tra mask tại vị trí này
                    y_start = max(0, y - self.window_size)
                    y_end = min(height, y + self.window_size)
                    x_start = max(0, x - self.window_size)
                    x_end = min(width, x + self.window_size)
                    if not np.any(mask[y_start:y_end, x_start:x_end]):
                        continue
                
                # Extract windows
                half_w = self.window_size // 2
                pre_win = image_pre[
                    y - half_w:y + half_w,
                    x - half_w:x + half_w
                ]
                
                post_win_large = image_post[
                    y - half_w - self.search_range:y + half_w + self.search_range,
                    x - half_w - self.search_range:x + half_w + self.search_range
                ]
                
                if pre_win.size == 0 or post_win_large.size == 0:
                    continue
                
                # Normalized cross-correlation
                dy, dx, corr = self._normalized_cross_correlation(
                    pre_win, post_win_large
                )
                
                range_offset[i, j] = dx * self.pixel_size_m
                azimuth_offset[i, j] = dy * self.pixel_size_m
                confidence[i, j] = corr
        
        # Interpolate về resolution gốc
        logger.info("Interpolating to full resolution...")
        range_offset_full = self._interpolate_to_full(
            range_offset, y_coords, x_coords, (height, width)
        )
        azimuth_offset_full = self._interpolate_to_full(
            azimuth_offset, y_coords, x_coords, (height, width)
        )
        confidence_full = self._interpolate_to_full(
            confidence, y_coords, x_coords, (height, width)
        )
        
        # Tính magnitude và direction
        magnitude = np.sqrt(range_offset_full**2 + azimuth_offset_full**2)
        direction = np.arctan2(azimuth_offset_full, range_offset_full)
        
        # Phát hiện hotspot (dịch chuyển > 0.5m với confidence cao)
        hotspot_mask = (
            (magnitude > 0.5) &  # > 0.5m
            (confidence_full > self.min_correlation)
        )
        
        # Metadata
        time_span = (date_post - date_pre).days / 365.25
        metadata = {
            "date_pre": date_pre.isoformat(),
            "date_post": date_post.isoformat(),
            "time_span_years": time_span,
            "pixel_size_m": self.pixel_size_m,
            "window_size": self.window_size,
            "min_correlation": self.min_correlation,
            "n_hotspots": int(hotspot_mask.sum()),
            "mean_displacement_m": float(np.mean(magnitude[hotspot_mask])) if hotspot_mask.any() else 0.0,
            "analysis_type": "Level 2 - Offset Tracking (GEE GRD)"
        }
        
        logger.info(f"Detected {metadata['n_hotspots']} displacement hotspots")
        
        return OffsetTrackingResult(
            range_offset=range_offset_full,
            azimuth_offset=azimuth_offset_full,
            magnitude=magnitude,
            direction=direction,
            confidence=confidence_full,
            hotspot_mask=hotspot_mask,
            metadata=metadata
        )
    
    def _normalized_cross_correlation(
        self,
        template: np.ndarray,
        search_image: np.ndarray
    ) -> Tuple[int, int, float]:
        """
        Tính normalized cross-correlation.
        
        Returns
        -------
        dy, dx : int
            Offset tối ưu (pixels)
        correlation : float
            Giá trị correlation (0-1)
        """
        # Normalize template
        template = template - np.mean(template)
        template = template / (np.std(template) + 1e-8)
        
        # Cross-correlation
        correlation = correlate2d(
            search_image - np.mean(search_image),
            template,
            mode='valid'
        )
        
        # Normalize
        correlation = correlation / (np.std(search_image) * template.size + 1e-8)
        
        # Tìm vị trí tối đa
        max_idx = np.unravel_index(np.argmax(correlation), correlation.shape)
        
        # Tính offset từ center
        center_y = (search_image.shape[0] - template.shape[0]) // 2
        center_x = (search_image.shape[1] - template.shape[1]) // 2
        
        dy = max_idx[0] - center_y
        dx = max_idx[1] - center_x
        max_corr = correlation[max_idx]
        
        return dy, dx, float(max_corr)
    
    def _interpolate_to_full(
        self,
        low_res: np.ndarray,
        y_coords: np.ndarray,
        x_coords: np.ndarray,
        target_shape: Tuple[int, int]
    ) -> np.ndarray:
        """Nội suy từ low-res về full resolution"""
        from scipy.interpolate import RegularGridInterpolator
        
        # Tạo grid interpolator
        interpolator = RegularGridInterpolator(
            (y_coords, x_coords),
            low_res,
            method='linear',
            bounds_error=False,
            fill_value=0
        )
        
        # Grid đích
        target_y = np.arange(target_shape[0])
        target_x = np.arange(target_shape[1])
        grid_y, grid_x = np.meshgrid(target_y, target_x, indexing='ij')
        
        # Interpolate
        points = np.stack([grid_y.ravel(), grid_x.ravel()], axis=-1)
        full_res = interpolator(points).reshape(target_shape)
        
        return full_res.astype(np.float32)
    
    def compute_velocity(
        self,
        results: List[OffsetTrackingResult]
    ) -> np.ndarray:
        """
        Tính vận tốc dịch chuyển trung bình (m/year).
        
        Parameters
        ----------
        results : List[OffsetTrackingResult]
            Danh sách kết quả từ nhiều cặp ảnh
            
        Returns
        -------
        np.ndarray
            Vận tốc (m/year)
        """
        if not results:
            return np.array([])
        
        total_displacement = np.zeros_like(results[0].magnitude)
        total_time = 0.0
        
        for result in results:
            time_span = result.metadata['time_span_years']
            if time_span > 0:
                # Weighted by confidence
                weighted_disp = result.magnitude * result.confidence
                total_displacement += weighted_disp
                total_time += time_span
        
        if total_time > 0:
            velocity = total_displacement / total_time
        else:
            velocity = np.zeros_like(total_displacement)
        
        return velocity
    
    def generate_report(self, result: OffsetTrackingResult) -> str:
        """Tạo báo cáo tóm tắt"""
        meta = result.metadata
        
        report = f"""
========================================
BÁO CÁO OFFSET TRACKING (CẤP 2)
========================================

Thông tin phân tích:
- Loại: {meta['analysis_type']}
- Thời gian: {meta['date_pre'][:10]} → {meta['date_post'][:10]}
- Khoảng thời gian: {meta['time_span_years']:.2f} năm

Kết quả:
- Số vùng dịch chuyển: {meta['n_hotspots']} pixels
- Dịch chuyển trung bình: {meta['mean_displacement_m']:.2f} m
- Độ chính xác: ~{self.pixel_size_m}m (1 pixel)

⚠️ LƯU Ý QUAN TRỌNG:
Đây là phân tích OFFSET TRACKING với độ chính xác ~0.5m.
Phù hợp phát hiện dịch chuyển lớn (>0.5m).

KHÔNG phải đo sụt lún chính xác mm-level.

Để đo chính xác (3-10 mm/năm):
→ Dùng Cấp 3: SBAS-InSAR với SLC data (ASF HyP3 + MintPy)

========================================
"""
        return report
