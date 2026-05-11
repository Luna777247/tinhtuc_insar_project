"""
subsidence_integrator.py
==========================
Tích hợp Cấp 1 + 2 + 3 cho phân tích sụt lún toàn diện.

Pipeline:
- Cấp 1: Proxy detection (hotspot screening) - GEE
- Cấp 2: Offset tracking (~0.5m) - GEE/Local
- Cấp 3: SBAS-InSAR (mm) - ASF HyP3 + MintPy

Output: Bản đồ rủi ro sụt lún tổng hợp
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Union
from datetime import datetime
from pathlib import Path
import json

from .level1_proxy import ProxySubsidenceDetector, ProxyDetectionResult
from .level2_offset import OffsetTrackingDetector, OffsetTrackingResult

logger = logging.getLogger(__name__)


class SubsidenceIntegrator:
    """
    Tích hợp đa cấp phân tích sụt lún.
    
    Parameters
    ----------
    enable_level1 : bool
        Bật Cấp 1 - Proxy detection
    enable_level2 : bool
        Bật Cấp 2 - Offset tracking
    output_dir : str
        Thư mục lưu kết quả
    """
    
    def __init__(
        self,
        enable_level1: bool = True,
        enable_level2: bool = True,
        output_dir: str = "outputs/subsidence"
    ):
        self.enable_level1 = enable_level1
        self.enable_level2 = enable_level2
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Khởi tạo detectors
        if enable_level1:
            self.proxy_detector = ProxySubsidenceDetector()
            logger.info("Level 1 - Proxy Detection: ENABLED")
        
        if enable_level2:
            self.offset_detector = OffsetTrackingDetector()
            logger.info("Level 2 - Offset Tracking: ENABLED")
        
        logger.info("Level 3 - SBAS-InSAR: EXTERNAL (ASF HyP3 + MintPy)")
    
    def analyze_subsidence(
        self,
        vh_timeseries: np.ndarray,
        vv_timeseries: np.ndarray,
        dates: List[datetime],
        image_pairs: Optional[List[Tuple[np.ndarray, np.ndarray, datetime, datetime]]] = None,
        mask: Optional[np.ndarray] = None,
        aoi_name: str = "TinhTuc"
    ) -> Dict:
        """
        Phân tích sụt lún đa cấp.
        
        Parameters
        ----------
        vh_timeseries : np.ndarray
            Chuỗi thời gian VH (n_time, H, W)
        vv_timeseries : np.ndarray
            Chuỗi thời gian VV
        dates : List[datetime]
            Danh sách ngày
        image_pairs : List, optional
            Cặp ảnh cho offset tracking [(pre, post, date_pre, date_post), ...]
        mask : np.ndarray, optional
            Mask ROI
        aoi_name : str
            Tên vùng phân tích
            
        Returns
        -------
        Dict
            Kết quả tổng hợp từ cả 3 cấp
        """
        results = {
            "aoi_name": aoi_name,
            "date_range": (dates[0].isoformat(), dates[-1].isoformat()),
            "n_images": len(dates),
            "levels": {}
        }
        
        # ========== CẤP 1: PROXY DETECTION ==========
        if self.enable_level1 and len(dates) >= 10:
            logger.info("=" * 50)
            logger.info("CẤP 1: PROXY DETECTION (GEE GRD)")
            logger.info("=" * 50)
            
            try:
                proxy_result = self.proxy_detector.analyze_backscatter_trend(
                    vh_timeseries, vv_timeseries, dates, mask
                )
                results["levels"]["level1_proxy"] = {
                    "status": "success",
                    "n_hotspots": int(proxy_result.hotspot_mask.sum()),
                    "mean_stability": float(np.mean(proxy_result.stability_index)),
                    "mean_trend": float(np.mean(proxy_result.trend_slope)),
                    "report": self.proxy_detector.generate_report(proxy_result)
                }
                
                # Lưu hotspot mask
                np.save(
                    self.output_dir / f"{aoi_name}_L1_hotspots.npy",
                    proxy_result.hotspot_mask
                )
                
                logger.info(f"Cấp 1: {results['levels']['level1_proxy']['n_hotspots']} hotspots")
                
            except Exception as e:
                logger.error(f"Cấp 1 failed: {e}")
                results["levels"]["level1_proxy"] = {"status": "failed", "error": str(e)}
        else:
            results["levels"]["level1_proxy"] = {"status": "skipped"}
        
        # ========== CẤP 2: OFFSET TRACKING ==========
        if self.enable_level2 and image_pairs is not None:
            logger.info("=" * 50)
            logger.info("CẤP 2: OFFSET TRACKING (GEE GRD)")
            logger.info("=" * 50)
            
            try:
                offset_results = []
                for pre, post, date_pre, date_post in image_pairs:
                    offset_result = self.offset_detector.compute_offset_tracking(
                        pre, post, date_pre, date_post, mask
                    )
                    offset_results.append(offset_result)
                
                # Tính velocity
                velocity = self.offset_detector.compute_velocity(offset_results)
                
                results["levels"]["level2_offset"] = {
                    "status": "success",
                    "n_pairs": len(offset_results),
                    "mean_velocity_m_year": float(np.mean(velocity)) if velocity.size > 0 else 0.0,
                    "reports": [self.offset_detector.generate_report(r) for r in offset_results[:3]]
                }
                
                # Lưu velocity map
                if velocity.size > 0:
                    np.save(
                        self.output_dir / f"{aoi_name}_L2_velocity.npy",
                        velocity
                    )
                
                logger.info(f"Cấp 2: {len(offset_results)} pairs, velocity computed")
                
            except Exception as e:
                logger.error(f"Cấp 2 failed: {e}")
                results["levels"]["level2_offset"] = {"status": "failed", "error": str(e)}
        else:
            results["levels"]["level2_offset"] = {"status": "skipped"}
        
        # ========== CẤP 3: SBAS-InSAR (External) ==========
        results["levels"]["level3_sbas"] = {
            "status": "external",
            "workflow": "ASF HyP3 → MintPy",
            "data_source": "SLC from ASF",
            "expected_accuracy": "3-10 mm/year",
            "note": "Run separately using scripts in scripts/sbas_workflow/"
        }
        
        # Lưu tổng hợp
        self._save_summary(results, aoi_name)
        
        return results
    
    def _save_summary(self, results: Dict, aoi_name: str):
        """Lưu tổng hợp kết quả"""
        summary_file = self.output_dir / f"{aoi_name}_subsidence_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Summary saved: {summary_file}")
    
    def generate_final_report(self, results: Dict) -> str:
        """Tạo báo cáo tổng hợp cuối cùng"""
        
        report = f"""
╔══════════════════════════════════════════════════════════════════╗
║           BÁO CÁO PHÂN TÍCH SỤT LÚN ĐA CẤP - {results['aoi_name']}          ║
╚══════════════════════════════════════════════════════════════════╝

Thông tin chung:
- Vùng phân tích: {results['aoi_name']}
- Khoảng thời gian: {results['date_range'][0][:10]} → {results['date_range'][1][:10]}
- Số ảnh Sentinel-1: {results['n_images']}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 KẾT QUẢ THEO CẤP ĐỘ

┌─────────────────────────────────────────────────────────────────┐
│ CẤP 1 - PROXY DETECTION (GEE GRD)                              │
├─────────────────────────────────────────────────────────────────┤
│ Status: {results['levels'].get('level1_proxy', {}).get('status', 'N/A'):<15}                                           │
│ Số vùng nghi ngờ: {results['levels'].get('level1_proxy', {}).get('n_hotspots', 'N/A'):<10} pixels                           │
│ Chỉ số bất ổn TB: {results['levels'].get('level1_proxy', {}).get('mean_stability', 'N/A'):<10.3f}                           │
│ Xu hướng VH TB: {results['levels'].get('level1_proxy', {}).get('mean_trend', 'N/A'):<10.2f} dB/year                       │
│ Độ chính xác: qualitative (visual change)                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CẤP 2 - OFFSET TRACKING (GEE GRD)                              │
├─────────────────────────────────────────────────────────────────┤
│ Status: {results['levels'].get('level2_offset', {}).get('status', 'N/A'):<15}                                           │
│ Số cặp ảnh: {results['levels'].get('level2_offset', {}).get('n_pairs', 'N/A'):<10} pairs                                  │
│ Vận tốc TB: {results['levels'].get('level2_offset', {}).get('mean_velocity_m_year', 'N/A'):<10.2f} m/year                   │
│ Độ chính xác: ~0.5m (relative deformation)                     │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ CẤP 3 - SBAS-InSAR (External)                                  │
├─────────────────────────────────────────────────────────────────┤
│ Status: EXTERNAL - Chạy riêng                                  │
│ Workflow: ASF HyP3 → MintPy                                     │
│ Dữ liệu: SLC từ ASF                                            │
│ Độ chính xác: 3-10 mm/year (chuẩn InSAR)                        │
│ Script: scripts/sbas_workflow/                                 │
└─────────────────────────────────────────────────────────────────┘

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  LƯU Ý QUAN TRỌNG

1. Cấp 1 + 2 chỉ là PHÁT HIỆN GIÁN TIẾP qua backscatter
   → Không đo được sụt lún chính xác mm-level

2. Cấp 3 (SBAS-InSAR) là phương pháp CHUẨN
   → Cần chạy riêng với SLC data

3. Workflow đề xuất cho Tĩnh Túc:
   
   GEE (Cấp 1) → Hotspot Screening
        ↓
   ASF HyP3 → Cấp 3 SBAS → Đo chính xác

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Được tạo: {datetime.now().isoformat()}
"""
        return report
