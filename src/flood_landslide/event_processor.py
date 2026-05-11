"""
event_processor.py
====================
Xử lý sự kiện mưa lũ cụ thể (28/09 - 01/10/2025).

Dữ liệu Sentinel-1:
- 29/09/2025: Orbit 55 (ASC) - 10:58
- 01/10/2025: Orbit 91 (DESC) - 22:50
"""

import numpy as np
import pandas as pd
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FloodEventProcessor:
    """
    Xử lý sự kiện mưa lũ.
    
    Parameters
    ----------
    event_date_start : str
        Ngày bắt đầu sự kiện (YYYY-MM-DD)
    event_date_end : str
        Ngày kết thúc sự kiện (YYYY-MM-DD)
    baseline_days : int
        Số ngày baseline trước sự kiện
    """
    
    def __init__(
        self,
        event_date_start: str = "2025-09-28",
        event_date_end: str = "2025-10-01",
        baseline_days: int = 10
    ):
        self.event_start = datetime.strptime(event_date_start, "%Y-%m-%d")
        self.event_end = datetime.strptime(event_date_end, "%Y-%m-%d")
        self.baseline_start = self.event_start - timedelta(days=baseline_days)
        self.baseline_end = self.event_start - timedelta(days=3)
        
        logger.info(
            f"Event: {event_date_start} to {event_date_end}, "
            f"Baseline: {self.baseline_start.date()} to {self.baseline_end.date()}"
        )
    
    def get_available_images(
        self,
        csv_path: str = "docs/Sentinel1_Metadata_TinhTuc_2025_06_12.csv"
    ) -> pd.DataFrame:
        """
        Lấy danh sách ảnh có sẵn cho sự kiện.
        
        Returns
        -------
        pd.DataFrame : Thông tin ảnh phù hợp
        """
        # Đọc metadata
        df = pd.read_csv(csv_path)
        df['date'] = pd.to_datetime(df['date'])
        
        # Lọc ảnh trong thời gian baseline và event
        all_dates = pd.concat([
            df[(df['date'] >= self.baseline_start) & 
               (df['date'] <= self.baseline_end)],
            df[(df['date'] >= self.event_start) & 
               (df['date'] <= self.event_end + timedelta(days=1))]
        ])
        
        # Chỉ lấy S1A, lọc slice_number=1 cho Orbit 91
        filtered = all_dates[
            (all_dates['platform'] == 'A') &
            ((all_dates['relativeOrbit'] != 91) | 
             (all_dates['sliceNumber'] == 1.0))
        ].copy()
        
        # Sắp xếp theo ngày và orbit
        filtered = filtered.sort_values(['date', 'relativeOrbit'])
        
        logger.info(f"Found {len(filtered)} images for event processing")
        
        # Log chi tiết
        for _, row in filtered.iterrows():
            logger.info(
                f"  {row['date']}: Orbit {row['relativeOrbit']} "
                f"({row['orbit']}) - Slice {row['sliceNumber']}"
            )
        
        return filtered
    
    def analyze_event(
        self,
        diff_vh_55: np.ndarray,
        diff_vh_91: np.ndarray,
        slope: np.ndarray,
        permanent_water: Optional[np.ndarray] = None,
        dem: Optional[np.ndarray] = None
    ) -> Dict:
        """
        Phân tích toàn diện sự kiện.
        
        Parameters
        ----------
        diff_vh_55 : np.ndarray
            Sai biệt VH Orbit 55 (29/09 vs baseline)
        diff_vh_91 : np.ndarray
            Sai biệt VH Orbit 91 (01/10 vs baseline)
        slope : np.ndarray
            Bản đồ độ dốc
        permanent_water : np.ndarray
            Mask nước thường xuyên
        dem : np.ndarray
            Digital Elevation Model
            
        Returns
        -------
        Dict : Kết quả phân tích
        """
        from .flood_detector import FloodDetector
        from .landslide_detector import LandslideDetector
        from .risk_integrator import RiskIntegrator
        
        logger.info("Starting event analysis...")
        
        # 1. Phát hiện ngập lụt từ Orbit 55
        flood_detector = FloodDetector(
            aoi_bbox=[105.85, 22.62, 106.05, 22.80],
            orbit_numbers=[55],
            threshold_sigma=1.5
        )
        
        flood_result = flood_detector.detect_flood_single_orbit(
            diff_vh_55, slope, permanent_water
        )
        
        # 2. Phát hiện sạt lở từ Orbit 91
        landslide_detector = LandslideDetector(
            sar_change_threshold=3.0,
            slope_range=(20, 55)
        )
        
        landslide_result = landslide_detector.detect_sar_changes(
            diff_vh_91,
            slope=slope,
            flood_mask=flood_result
        )
        
        # 3. Tích hợp rủi ro
        integrator = RiskIntegrator()
        risk_map = integrator.calculate_composite_risk(
            flood_result,
            landslide_result,
            np.zeros_like(flood_result),  # Không có mine data
            pixel_size_m=10.0
        )
        
        # 4. Thống kê
        flood_stats = flood_detector.calculate_flood_statistics(flood_result)
        
        # Đếm sạt lở
        landslide_pixels = np.sum(landslide_result)
        landslide_area_ha = landslide_pixels * 100 / 10000  # 10m pixel
        
        # 5. Xác định hotspots
        hotspots = integrator.identify_hotspots(
            risk_map,
            min_area_ha=1.0,
            pixel_size_m=10.0
        )
        
        # 6. Tạo báo cáo
        report = self._generate_event_report(
            flood_stats,
            landslide_area_ha,
            hotspots,
            risk_map
        )
        
        results = {
            "event_period": {
                "start": self.event_start.isoformat(),
                "end": self.event_end.isoformat()
            },
            "flood": {
                "mask": flood_result,
                "area_ha": flood_stats["area_ha"],
                "pixels": flood_stats["pixel_count"]
            },
            "landslide": {
                "mask": landslide_result,
                "area_ha": landslide_area_ha,
                "pixels": int(landslide_pixels)
            },
            "risk_map": risk_map,
            "hotspots": hotspots,
            "report": report
        }
        
        logger.info("Event analysis complete")
        logger.info(f"  Flood: {results['flood']['area_ha']:.2f} ha")
        logger.info(f"  Landslide: {results['landslide']['area_ha']:.2f} ha")
        logger.info(f"  Hotspots: {len(hotspots)}")
        
        return results
    
    def _generate_event_report(
        self,
        flood_stats: Dict,
        landslide_area_ha: float,
        hotspots: List[Dict],
        risk_map: np.ndarray
    ) -> str:
        """Tạo báo cáo sự kiện."""
        
        # Phân loại hotspots
        high_risk = [h for h in hotspots if h['risk_level'] >= 3]
        
        report = f"""
{'='*60}
BÁO CÁO SỰ KIỆN MƯA LŨ
Tĩnh Túc, Cao Bằng
{self.event_start.strftime('%d/%m/%Y')} - {self.event_end.strftime('%d/%m/%Y')}
{'='*60}

1. TỔNG QUAN
   - Ngày sự kiện: {self.event_start.strftime('%d/%m/%Y')} - {self.event_end.strftime('%d/%m/%Y')}
   - Dữ liệu: Sentinel-1 (Orbit 55: 29/09, Orbit 91: 01/10)
   - Phương pháp: Change detection + Consensus

2. NGẬP LỤT
   - Diện tích xác nhận: {flood_stats['area_ha']:.2f} ha
   - Số pixel: {flood_stats['pixel_count']}
   - Phần trăm vùng nghiên cứu: {flood_stats['percentage']:.2f}%

3. SẠT LỞ
   - Diện tích phát hiện: {landslide_area_ha:.2f} ha
   - Số pixel: {int(landslide_area_ha * 100)}
   - Phương pháp: SAR change detection (>|3| dB)

4. ĐIỂM NÓNG (HOTSPOTS)
   - Tổng số: {len(hotspots)} vị trí
   - Rủi ro cao/cực cao: {len(high_risk)} vị trí
"""
        
        if hotspots:
            report += "\n   Chi tiết hotspots:\n"
            for i, h in enumerate(hotspots[:5], 1):  # Top 5
                report += (
                    f"   {i}. Vị trí ({h['centroid_pixel'][0]:.0f}, "
                    f"{h['centroid_pixel'][1]:.0f}) - "
                    f"{h['level_name']} - {h['area_ha']:.2f} ha\n"
                )
        
        report += f"""
5. PHÂN BỐ RỦI RO
   - Normal (0): {np.sum(risk_map == 0)} pixels
   - Low (1): {np.sum(risk_map == 1)} pixels  
   - Medium (2): {np.sum(risk_map == 2)} pixels
   - High (3): {np.sum(risk_map == 3)} pixels
   - Extreme (4): {np.sum(risk_map == 4)} pixels

6. KHUYẾN NGHỊ
"""
        
        if flood_stats['area_ha'] > 50:
            report += "   ⚠️ Ngập lụt diện rộng - Cần sơ tán vùng thấp\n"
        if landslide_area_ha > 10:
            report += "   ⚠️ Sạt lở nhiều - Cấm đường vùng núi\n"
        if len(high_risk) > 0:
            report += "   🚨 Có vùng rủi ro cực cao - Ưu tiên cứu hộ\n"
        
        report += "\n" + "="*60 + "\n"
        
        return report
    
    def save_results(
        self,
        results: Dict,
        output_dir: str = "outputs/events/20250928_1001"
    ):
        """
        Lưu kết quả sự kiện.
        
        Parameters
        ----------
        results : Dict
            Kết quả từ analyze_event()
        output_dir : str
            Thư mục đầu ra
        """
        import json
        from pathlib import Path
        
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        
        # Lưu masks
        np.save(out_path / "flood_mask.npy", results['flood']['mask'])
        np.save(out_path / "landslide_mask.npy", results['landslide']['mask'])
        np.save(out_path / "risk_map.npy", results['risk_map'])
        
        # Lưu thống kê
        stats = {
            "event_period": results['event_period'],
            "flood_area_ha": results['flood']['area_ha'],
            "landslide_area_ha": results['landslide']['area_ha'],
            "hotspot_count": len(results['hotspots'])
        }
        
        with open(out_path / "statistics.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
        # Lưu hotspots
        with open(out_path / "hotspots.json", 'w') as f:
            json.dump(results['hotspots'], f, indent=2)
        
        # Lưu báo cáo
        with open(out_path / "report.txt", 'w', encoding='utf-8') as f:
            f.write(results['report'])
        
        logger.info(f"Results saved to {output_dir}")


def process_flood_event_2025(
    csv_metadata: str = "docs/Sentinel1_Metadata_TinhTuc_2025_06_12.csv",
    output_dir: str = "outputs/events/20250928_1001"
) -> Dict:
    """
    Hàm chính xử lý sự kiện mưa lũ 28/09-01/10/2025.
    
    Parameters
    ----------
    csv_metadata : str
        Đường dẫn file metadata
    output_dir : str
        Thư mục đầu ra
        
    Returns
    -------
    Dict : Kết quả xử lý
    """
    processor = FloodEventProcessor(
        event_date_start="2025-09-28",
        event_date_end="2025-10-01",
        baseline_days=10
    )
    
    # Kiểm tra dữ liệu có sẵn
    available = processor.get_available_images(csv_metadata)
    
    if len(available) == 0:
        logger.error("No images found for event!")
        return {"error": "No data available"}
    
    logger.info(f"\n{'='*60}")
    logger.info("SỰ KIỆN MƯA LŨ 28/09 - 01/10/2025")
    logger.info(f"{'='*60}")
    logger.info(f"Tìm thấy {len(available)} ảnh Sentinel-1:")
    
    for _, row in available.iterrows():
        logger.info(
            f"  📡 {row['date'].strftime('%Y-%m-%d %H:%M')} | "
            f"Orbit {row['relativeOrbit']} | {row['orbit']}"
        )
    
    # Lưu thông tin
    available.to_csv(f"{output_dir}/available_images.csv", index=False)
    
    return {
        "processor": processor,
        "available_images": available,
        "message": "Ready for GEE processing"
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Xử lý sự kiện
    results = process_flood_event_2025()
    
    print("\n" + "="*60)
    print("HOÀN THÀNH KIỂM TRA DỮ LIỆU")
    print("="*60)
    print(f"Trạng thái: {results['message']}")
    print(f"Số ảnh: {len(results['available_images'])}")
