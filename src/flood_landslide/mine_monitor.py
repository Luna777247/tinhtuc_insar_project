"""
mine_monitor.py
===============
Giám sát bãi thải mỏ và khu vực khai thác.

Đặc điểm:
- Bãi thải thay đổi liên tục
- Phản xạ mạnh (high backscatter)
- Nguy cơ sạt lở cao khi mưa
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class MineWasteMonitor:
    """
    Giám sát bãi thải mỏ Tĩnh Túc.
    
    Parameters
    ----------
    mine_locations : List[Tuple[float, float]]
        Tọa độ tâm các bãi thải [(lon, lat), ...]
    buffer_radius_m : float
        Bán kính buffer (m, mặc định 300)
    change_threshold_db : float
        Ngưỡng thay đổi (dB, mặc định 4.0)
    """
    
    def __init__(
        self,
        mine_locations: List[Tuple[float, float]] = None,
        buffer_radius_m: float = 300,
        change_threshold_db: float = 4.0
    ):
        # Mặc định: 3 bãi thải chính Tĩnh Túc
        self.mines = mine_locations or [
            (105.920, 22.715),
            (105.935, 22.720),
            (105.950, 22.705)
        ]
        self.buffer = buffer_radius_m
        self.threshold = change_threshold_db
        
        logger.info(f"MineWasteMonitor: {len(self.mines)} sites, "
                   f"buffer={buffer_radius_m}m, thresh={change_threshold_db}dB")
    
    def create_mine_roi(
        self,
        reference_array: np.ndarray,
        geotransform: Tuple[float, float, float, float, float, float]
    ) -> np.ndarray:
        """
        Tạo mask ROI cho các bãi thải.
        
        Parameters
        ----------
        reference_array : np.ndarray
            Mảng tham chiếu để lấy shape
        geotransform : Tuple
            (ulx, xres, xskew, uly, yskew, yres)
            
        Returns
        -------
        np.ndarray : Boolean mask các bãi thải
        """
        from scipy import ndimage
        
        H, W = reference_array.shape
        mask = np.zeros((H, W), dtype=bool)
        
        ulx, xres, _, uly, _, yres = geotransform
        
        for lon, lat in self.mines:
            # Chuyển tọa độ sang pixel
            x = int((lon - ulx) / xres)
            y = int((lat - uly) / yres)
            
            # Buffer radius in pixels
            buffer_px = int(self.buffer / abs(xres))
            
            # Vẽ circle
            y_grid, x_grid = np.ogrid[:H, :W]
            dist = np.sqrt((x_grid - x)**2 + (y_grid - y)**2)
            mask |= dist <= buffer_px
        
        logger.info(f"Mine ROI: {np.sum(mask)} pixels")
        return mask
    
    def detect_waste_movement(
        self,
        diff_vh: np.ndarray,
        diff_vv: np.ndarray,
        mine_mask: np.ndarray
    ) -> np.ndarray:
        """
        Phát hiện dịch chuyển bãi thải.
        
        Parameters
        ----------
        diff_vh : np.ndarray
            Sai biệt VH
        diff_vv : np.ndarray
            Sai biệt VV
        mine_mask : np.ndarray
            Mask bãi thải
            
        Returns
        -------
        np.ndarray : Mask thay đổi
        """
        # Thay đổi > ngưỡng trong vùng bãi thải
        change_mask = (
            (np.abs(diff_vh) > self.threshold) &
            (np.abs(diff_vv) > self.threshold * 0.8)
        )
        
        # Chỉ trong mine mask
        movement = change_mask & mine_mask
        
        logger.info(f"Waste movement: {np.sum(movement)} pixels")
        return movement
    
    def calculate_movement_statistics(
        self,
        movement_mask: np.ndarray,
        diff_vh: np.ndarray,
        area_per_pixel: float = 100.0
    ) -> Dict:
        """
        Thống kê dịch chuyển.
        """
        if np.sum(movement_mask) == 0:
            return {"movement_pixels": 0, "movement_area_ha": 0}
        
        changes = diff_vh[movement_mask]
        
        stats = {
            "movement_pixels": int(np.sum(movement_mask)),
            "movement_area_m2": float(np.sum(movement_mask) * area_per_pixel),
            "movement_area_ha": float(np.sum(movement_mask) * area_per_pixel / 10000),
            "mean_change_db": float(np.mean(changes)),
            "max_change_db": float(np.max(np.abs(changes))),
            "std_change_db": float(np.std(changes))
        }
        
        logger.info(
            f"Movement: {stats['movement_area_ha']:.2f} ha, "
            f"mean={stats['mean_change_db']:.2f}dB"
        )
        return stats
    
    def assess_risk_level(
        self,
        movement_mask: np.ndarray,
        slope: np.ndarray,
        rainfall: Optional[float] = None
    ) -> str:
        """
        Đánh giá mức rủi ro.
        
        Returns
        -------
        str : 'LOW', 'MEDIUM', 'HIGH', 'EXTREME'
        """
        area_ha = np.sum(movement_mask) * 100 / 10000  # Giả định 10m pixel
        
        # Ngưỡng theo tài liệu
        if area_ha < 0.5:
            level = 'LOW'
        elif area_ha < 1.0:
            level = 'MEDIUM'
        elif area_ha < 2.0:
            level = 'HIGH'
        else:
            level = 'EXTREME'
        
        # Tăng cấp nếu có mưa lớn
        if rainfall and rainfall > 100:  # mm
            if level == 'LOW':
                level = 'MEDIUM'
            elif level == 'MEDIUM':
                level = 'HIGH'
            elif level == 'HIGH':
                level = 'EXTREME'
        
        logger.info(f"Risk level: {level} ({area_ha:.2f} ha)")
        return level


class MineStabilityTracker:
    """
    Theo dõi độ ổn định bãi thải theo thời gian.
    """
    
    def __init__(self):
        self.history = []
        logger.info("MineStabilityTracker initialized")
    
    def add_measurement(
        self,
        date: datetime,
        movement_mask: np.ndarray,
        risk_level: str
    ):
        """Thêm đo lường vào lịch sử."""
        measurement = {
            "date": date,
            "area_pixels": int(np.sum(movement_mask)),
            "risk_level": risk_level
        }
        self.history.append(measurement)
        
        # Giữ tối đa 100 điểm
        if len(self.history) > 100:
            self.history.pop(0)
    
    def detect_trend(self) -> Dict:
        """
        Phát hiện xu hướng.
        
        Returns
        -------
        Dict : Phân tích xu hướng
        """
        if len(self.history) < 3:
            return {"trend": "INSUFFICIENT_DATA"}
        
        areas = [m["area_pixels"] for m in self.history]
        dates = [(m["date"] - self.history[0]["date"]).days for m in self.history]
        
        # Linear regression đơn giản
        slope = np.polyfit(dates, areas, 1)[0]
        
        if slope > 10:
            trend = "INCREASING"
        elif slope < -10:
            trend = "DECREASING"
        else:
            trend = "STABLE"
        
        return {
            "trend": trend,
            "slope_pixels_per_day": float(slope),
            "measurements": len(self.history),
            "current_level": self.history[-1]["risk_level"] if self.history else None
        }
    
    def get_alert_status(self) -> Dict:
        """Trạng thái cảnh báo hiện tại."""
        if not self.history:
            return {"status": "NO_DATA"}
        
        latest = self.history[-1]
        trend = self.detect_trend()
        
        # Logic cảnh báo
        if latest["risk_level"] in ["HIGH", "EXTREME"]:
            status = "ALERT"
        elif trend["trend"] == "INCREASING":
            status = "WARNING"
        else:
            status = "NORMAL"
        
        return {
            "status": status,
            "latest_risk": latest["risk_level"],
            "trend": trend["trend"],
            "last_update": latest["date"].isoformat()
        }
