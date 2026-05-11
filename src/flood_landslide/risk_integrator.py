"""
risk_integrator.py
==================
Tích hợp ngập lụt + sạt lở + bãi thải thành bản đồ rủi ro tổng hợp.

Mức rủi ro:
- 0: Không có rủi ro (bình thường)
- 1: Thấp (Low)
- 2: Trung bình (Medium)  
- 3: Cao (High)
- 4: Cực cao (Extreme)
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class RiskIntegrator:
    """
    Tích hợp đa rủi ro.
    
    Parameters
    ----------
    weights : Dict[str, float]
        Trọng số cho từng loại rủi ro
    thresholds : Dict[str, float]
        Ngưỡng diện tích cho từng mức
    """
    
    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        thresholds: Optional[Dict[str, float]] = None
    ):
        # Trọng số mặc định
        self.weights = weights or {
            "flood": 1.0,
            "landslide": 2.0,
            "mine_waste": 1.5
        }
        
        # Ngưỡng diện tích (ha)
        self.thresholds = thresholds or {
            "low": 0.5,
            "medium": 5.0,
            "high": 20.0,
            "extreme": 50.0
        }
        
        logger.info(f"RiskIntegrator: weights={self.weights}")
    
    def calculate_composite_risk(
        self,
        flood_mask: np.ndarray,
        landslide_mask: np.ndarray,
        mine_mask: np.ndarray,
        pixel_size_m: float = 10.0
    ) -> np.ndarray:
        """
        Tính bản đồ rủi ro tổng hợp.
        
        Parameters
        ----------
        flood_mask : np.ndarray
            Mask ngập lụt
        landslide_mask : np.ndarray
            Mask sạt lở
        mine_mask : np.ndarray
            Mask bãi thải
        pixel_size_m : float
            Kích thước pixel
            
        Returns
        -------
        np.ndarray : Risk score (0-4)
        """
        H, W = flood_mask.shape
        risk_score = np.zeros((H, W), dtype=np.uint8)
        
        # Tính diện tích cho từng pixel
        pixel_area_ha = (pixel_size_m ** 2) / 10000
        
        # Cộng dồn rủi ro
        risk_score = risk_score + flood_mask.astype(np.uint8) * 1
        risk_score = np.maximum(risk_score, landslide_mask.astype(np.uint8) * 2)
        risk_score = np.maximum(risk_score, mine_mask.astype(np.uint8) * 1)
        
        # Vùng có nhiều loại rủi ro cùng lúc
        multi_risk = (
            flood_mask.astype(int) +
            landslide_mask.astype(int) +
            mine_mask.astype(int)
        )
        
        # 2 loại trở lên = tăng cấp
        risk_score = np.where(
            multi_risk >= 2,
            np.minimum(risk_score + 1, 4),
            risk_score
        )
        
        # Cực cao: 3 loại cùng lúc
        risk_score = np.where(
            multi_risk >= 3,
            4,
            risk_score
        )
        
        logger.info(
            f"Risk map: min={risk_score.min()}, max={risk_score.max()}, "
            f"mean={risk_score.mean():.2f}"
        )
        return risk_score
    
    def generate_risk_statistics(
        self,
        risk_map: np.ndarray,
        pixel_size_m: float = 10.0
    ) -> Dict:
        """
        Thống kê rủi ro.
        """
        pixel_area_ha = (pixel_size_m ** 2) / 10000
        
        # Đếm pixels theo mức rủi ro
        risk_levels = ["Normal", "Low", "Medium", "High", "Extreme"]
        stats = {}
        
        for i, level in enumerate(risk_levels):
            mask = risk_map == i
            area_ha = np.sum(mask) * pixel_area_ha
            stats[level] = {
                "pixels": int(np.sum(mask)),
                "area_ha": float(area_ha),
                "percentage": float(np.sum(mask) / risk_map.size * 100)
            }
        
        # Tổng hợp
        total_risk_area = sum(stats[l]["area_ha"] for l in risk_levels[1:])
        
        stats["summary"] = {
            "total_risk_area_ha": float(total_risk_area),
            "high_extreme_ha": float(stats["High"]["area_ha"] + stats["Extreme"]["area_ha"]),
            "dominant_risk": max(
                [(l, stats[l]["area_ha"]) for l in risk_levels[1:]],
                key=lambda x: x[1]
            )[0]
        }
        
        logger.info(
            f"Risk stats: {total_risk_area:.2f} ha total risk, "
            f"dominant={stats['summary']['dominant_risk']}"
        )
        return stats
    
    def identify_hotspots(
        self,
        risk_map: np.ndarray,
        min_area_ha: float = 1.0,
        pixel_size_m: float = 10.0
    ) -> List[Dict]:
        """
        Xác định điểm nóng (hotspots).
        
        Parameters
        ----------
        risk_map : np.ndarray
            Bản đồ rủi ro
        min_area_ha : float
            Diện tích tối thiểu để được coi là hotspot
        pixel_size_m : float
            Kích thước pixel
            
        Returns
        -------
        List[Dict] : Danh sách hotspots
        """
        from scipy import ndimage
        
        pixel_area_ha = (pixel_size_m ** 2) / 10000
        min_pixels = int(min_area_ha / pixel_area_ha)
        
        hotspots = []
        
        # Xử lý từng mức rủi ro >= Medium
        for risk_level in [2, 3, 4]:
            mask = risk_map >= risk_level
            
            if not np.any(mask):
                continue
            
            # Label connected components
            labeled, num_features = ndimage.label(mask)
            
            for i in range(1, num_features + 1):
                component_mask = labeled == i
                area_ha = np.sum(component_mask) * pixel_area_ha
                
                if area_ha >= min_area_ha:
                    # Tính centroid
                    coords = np.argwhere(component_mask)
                    centroid = coords.mean(axis=0)
                    
                    hotspot = {
                        "id": len(hotspots) + 1,
                        "risk_level": risk_level,
                        "level_name": ["", "", "Medium", "High", "Extreme"][risk_level],
                        "area_ha": float(area_ha),
                        "pixel_count": int(np.sum(component_mask)),
                        "centroid_pixel": (float(centroid[0]), float(centroid[1])),
                        "max_risk": int(risk_map[component_mask].max())
                    }
                    hotspots.append(hotspot)
        
        # Sắp xếp theo diện tích
        hotspots.sort(key=lambda x: x["area_ha"], reverse=True)
        
        logger.info(f"Found {len(hotspots)} hotspots (>{min_area_ha} ha)")
        return hotspots


class AlertSystem:
    """
    Hệ thống cảnh báo 4 mức.
    """
    
    ALERT_LEVELS = {
        "GREEN": {
            "level": 0,
            "name": "Bình thường",
            "color": "#27AE60",
            "action": "Giám sát bình thường"
        },
        "YELLOW": {
            "level": 1,
            "name": "Canh cánh",
            "color": "#F1C40F",
            "action": "Email cảnh báo, kiểm tra Sentinel-2"
        },
        "ORANGE": {
            "level": 2,
            "name": "Cảnh báo",
            "color": "#E67E22",
            "action": "SMS + Email + cập nhật dashboard"
        },
        "RED": {
            "level": 3,
            "name": "Khẩn cấp",
            "color": "#E74C3C",
            "action": "Sơ tán khẩn cấp, báo UBND tỉnh"
        }
    }
    
    def __init__(self):
        self.alert_history = []
        logger.info("AlertSystem initialized")
    
    def evaluate_alert(
        self,
        risk_stats: Dict,
        flood_ha: float,
        landslide_ha: float,
        near_population: bool = False
    ) -> Dict:
        """
        Đánh giá mức cảnh báo.
        
        Parameters
        ----------
        risk_stats : Dict
            Thống kê rủi ro
        flood_ha : float
            Diện tích ngập (ha)
        landslide_ha : float
            Diện tích sạt lở (ha)
        near_population : bool
            Gần khu dân cư
            
        Returns
        -------
        Dict : Thông tin cảnh báo
        """
        # Logic cảnh báo
        if flood_ha > 200 or landslide_ha > 50:
            alert_key = "RED"
        elif flood_ha > 50 or landslide_ha > 20:
            alert_key = "ORANGE"
        elif flood_ha > 20 or landslide_ha > 5:
            alert_key = "YELLOW"
        else:
            alert_key = "GREEN"
        
        # Tăng cấp nếu gần dân cư
        if near_population and alert_key == "YELLOW":
            alert_key = "ORANGE"
        elif near_population and alert_key == "ORANGE":
            alert_key = "RED"
        
        alert_info = self.ALERT_LEVELS[alert_key].copy()
        alert_info["triggered_at"] = datetime.now().isoformat()
        alert_info["flood_ha"] = flood_ha
        alert_info["landslide_ha"] = landslide_ha
        
        # Lưu lịch sử
        self.alert_history.append(alert_info)
        if len(self.alert_history) > 100:
            self.alert_history.pop(0)
        
        logger.warning(f"Alert: {alert_key} - {alert_info['name']}")
        return alert_info
    
    def get_alert_summary(self) -> Dict:
        """Tóm tắt lịch sử cảnh báo."""
        if not self.alert_history:
            return {"status": "NO_ALERTS"}
        
        recent = self.alert_history[-10:]  # 10 cảnh báo gần nhất
        
        counts = {"GREEN": 0, "YELLOW": 0, "ORANGE": 0, "RED": 0}
        for alert in recent:
            for key in counts:
                if alert["name"] == self.ALERT_LEVELS[key]["name"]:
                    counts[key] += 1
        
        return {
            "total_alerts": len(self.alert_history),
            "recent_distribution": counts,
            "current_level": recent[-1]["name"],
            "last_alert": recent[-1]["triggered_at"]
        }


class ReportGenerator:
    """
    Tạo báo cáo tổng hợp.
    """
    
    def generate_daily_report(
        self,
        date: datetime,
        flood_results: Dict,
        landslide_results: Dict,
        mine_results: Dict,
        risk_stats: Dict,
        alert_info: Dict
    ) -> str:
        """
        Tạo báo cáo hàng ngày.
        
        Returns
        -------
        str : Nội dung báo cáo
        """
        report = f"""
{'='*60}
BÁO CÁO GIÁM SÁT RỦI RO - TĨNH TÚC, CAO BẰNG
{'='*60}
Ngày: {date.strftime('%Y-%m-%d')}

1. TÌNH HÌNH NGẬP LỤT
   - Diện tích ngập xác nhận: {flood_results.get('confirmed_ha', 0):.2f} ha
   - Diện tích nghi vấn: {flood_results.get('suspect_ha', 0):.2f} ha
   - Mức cảnh báo: {flood_results.get('alert_level', 'Không')}

2. TÌNH HÌNH SẠT LỞ
   - Sạt lở đã xác nhận: {landslide_results.get('confirmed_pixels', 0)} pixels
   - Thể tích ước tính: {landslide_results.get('volume_m3', 0):.0f} m³
   - Phân loại: {landslide_results.get('by_type', {})}

3. BÃI THẢI MỎ
   - Diện tích dịch chuyển: {mine_results.get('movement_area_ha', 0):.2f} ha
   - Mức rủi ro: {mine_results.get('risk_level', 'Không')}

4. TỔNG HỢP RỦI RO
   - Diện tích rủi ro tổng: {risk_stats.get('summary', {}).get('total_risk_area_ha', 0):.2f} ha
   - Mức rủi ro cao/cực cao: {risk_stats.get('summary', {}).get('high_extreme_ha', 0):.2f} ha
   - Điểm nóng (hotspots): {risk_stats.get('hotspot_count', 0)} vị trí

5. CẢNH BÁO HIỆN TẠI
   - Mức độ: {alert_info.get('name', 'Bình thường')}
   - Hành động: {alert_info.get('action', 'Giám sát bình thường')}

{'='*60}
        """
        return report
    
    def save_report(self, report: str, output_path: str):
        """Lưu báo cáo."""
        from pathlib import Path
        path = Path(output_path)
        path.write_text(report, encoding='utf-8')
        logger.info(f"Report saved: {output_path}")
