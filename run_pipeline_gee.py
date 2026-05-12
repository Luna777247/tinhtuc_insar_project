"""
GEE Workflow Runner - Tự động chạy GEE scripts và xử lý kết quả
===============================================================

Script này kết nối Google Earth Engine API qua Python, chạy các GEE workflows
đã được định nghĩa trong gee_scripts/, và tự động download kết quả về local.

Các workflow được hỗ trợ:
1. Flood Event Analysis (06_flood_event_20250929_1001.js)
2. Subsidence Proxy Level 1 (07_subsidence_proxy_level1.js)
3. Statistical Analysis S1_GRD_FLOAT (08_statistical_analysis_float.js)
4. Primary Orbit 55 Analysis (09_primary_orbit55_analysis.js)

Usage:
    python run_pipeline_gee.py --workflow flood --download
    python run_pipeline_gee.py --workflow subsidence --download
    python run_pipeline_gee.py --workflow orbit55 --download
    python run_pipeline_gee.py --all  # Chạy tất cả workflows

ROI: Sử dụng config/TinhTuc4326_200m.geojson
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ee
import pandas as pd

# Configuration
DEFAULT_KEY_PATH = Path(__file__).parent / "gee_scripts" / "gee-private-key.json"
PROJECT_ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "gee_results"
GEOJSON_PATH = PROJECT_ROOT / "config" / "TinhTuc4326_200m.geojson"

# Load AOI từ GeoJSON
def load_roi_from_geojson(geojson_path: Path = GEOJSON_PATH) -> ee.Geometry:
    """Load ROI từ GeoJSON file."""
    if not geojson_path.exists():
        logger.warning(f"GeoJSON không tìm thấy: {geojson_path}")
        logger.info("Sử dụng ROI mặc định (Rectangle)")
        return ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80])
    
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    # Lấy coordinates từ GeoJSON
    geometry_type = None
    
    if geojson['type'] == 'Polygon':
        coords = geojson['coordinates']
        geometry_type = 'Polygon'
    elif geojson['type'] == 'FeatureCollection':
        geom = geojson['features'][0]['geometry']
        coords = geom['coordinates']
        geometry_type = geom.get('type', 'Polygon')
    elif geojson['type'] == 'Feature':
        geom = geojson['geometry']
        coords = geom['coordinates']
        geometry_type = geom.get('type', 'Polygon')
    elif geojson['type'] == 'MultiPolygon':
        # Lấy polygon đầu tiên từ MultiPolygon
        coords = geojson['coordinates'][0]  # First polygon
        geometry_type = 'MultiPolygon'
        logger.info("   Converted MultiPolygon → Polygon (first part)")
    else:
        coords = geojson.get('coordinates', [])
        geometry_type = 'Unknown'
    
    # Xử lý MultiPolygon trong FeatureCollection/Feature
    if geometry_type == 'MultiPolygon':
        # MultiPolygon: [[[[lon,lat],...]]] → Polygon: [[[lon,lat],...]]]
        # Lấy polygon đầu tiên (thường là outer ring)
        if len(coords) > 0 and isinstance(coords[0], list):
            if len(coords[0]) > 0 and isinstance(coords[0][0], list):
                if len(coords[0][0]) > 0 and isinstance(coords[0][0][0], (int, float)):
                    # coords[0] là [[lon,lat],...] - đúng format Polygon
                    coords = coords[0]
                    logger.info("   Extracted first polygon from MultiPolygon")
    
    # Đảm bảo coords là list of lists (list of linear rings)
    # GEE expects: [[ [lon1, lat1], [lon2, lat2], ... ]] for a single ring polygon
    if not isinstance(coords, list) or len(coords) == 0:
        logger.error("Invalid coordinates format in GeoJSON")
        return ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80])
    
    # If coords is a single list of points (not wrapped in another list), wrap it
    if len(coords) > 0 and isinstance(coords[0], list) and len(coords[0]) == 2:
        # Check if coords[0] is a point [lon, lat] (numbers)
        if all(isinstance(c, (int, float)) for c in coords[0]):
            # It's a flat list of points, wrap it as a single ring
            coords = [coords]
    
    try:
        roi = ee.Geometry.Polygon(coords)
        logger.info(f"✅ Đã load ROI từ GeoJSON: {geojson_path}")
        logger.info(f"   Tọa độ: {len(coords[0]) if coords else 0} điểm")
        return roi
    except Exception as e:
        logger.error(f"❌ Lỗi tạo Polygon từ GeoJSON: {e}")
        logger.info("Fallback về ROI mặc định")
        return ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80])

# Global ROI - sẽ được khởi tạo sau
ROI = None

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def initialize_ee(key_path: Path = DEFAULT_KEY_PATH) -> None:
    """Khởi tạo Google Earth Engine với service account."""
    if not key_path.exists():
        raise FileNotFoundError(
            f"Service account key không tìm thấy: {key_path}\n"
            f"Vui lòng tạo file gee-private-key.json từ Google Cloud Console"
        )
    
    data = json.loads(key_path.read_text(encoding="utf-8"))
    service_account_email = data.get("client_email")
    
    if not service_account_email:
        raise ValueError(f"Thiếu 'client_email' trong {key_path}")
    
    credentials = ee.ServiceAccountCredentials(service_account_email, str(key_path))
    ee.Initialize(credentials)
    logger.info(f"✅ Đã kết nối GEE với account: {service_account_email}")


class GEEWorkflowRunner:
    """Runner cho các GEE workflows."""
    
    def __init__(self, output_dir: Path = OUTPUT_DIR):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.tasks: List[Dict] = []
    
    def run_flood_event_analysis(
        self,
        baseline_start: str = "2025-09-15",
        baseline_end: str = "2025-09-20",
        event_start: str = "2025-09-28",
        event_end: str = "2025-10-02"
    ) -> Dict:
        """
        Workflow 1: Phân tích sự kiện mưa lũ (Flood Event Analysis).
        
        Sử dụng Orbit 55 (ASCENDING) làm primary cho flood detection.
        """
        logger.info("=" * 60)
        logger.info("🌊 WORKFLOW 1: Flood Event Analysis")
        logger.info(f"   Baseline: {baseline_start} → {baseline_end}")
        logger.info(f"   Event: {event_start} → {event_end}")
        logger.info("   Primary Orbit: 55 (ASCENDING)")
        logger.info("=" * 60)
        
        # 1. Load Sentinel-1 chỉ Orbit 55
        s1_collection = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(ROI) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.eq('relativeOrbitNumber_start', 55)) \
            .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
        
        # 2. Baseline và Post-event
        baseline = s1_collection.filterDate(baseline_start, baseline_end).median()
        post_event = s1_collection.filterDate(event_start, event_end).median()
        
        # 3. Calculate difference
        diff_vv = post_event.select('VV').subtract(baseline.select('VV')).rename('VV_diff')
        
        # 4. Adaptive threshold (μ - 1.5σ)
        stats = diff_vv.reduceRegion(
            reducer=ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', True),
            geometry=ROI,
            scale=30,
            maxPixels=1e9
        )
        
        mu = ee.Number(stats.get('VV_diff_mean'))
        sigma = ee.Number(stats.get('VV_diff_stdDev'))
        threshold = mu.subtract(sigma.multiply(1.5))
        
        # 5. DEM và Slope
        dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation')
        slope = ee.Terrain.slope(dem)
        
        # 6. Flood detection: VV < threshold AND slope < 5°
        flood_mask = diff_vv.lt(threshold).And(slope.lt(5))
        
        # 7. Thống kê diện tích
        pixel_area = ee.Image.pixelArea()
        flood_area = flood_mask.multiply(pixel_area).reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=ROI,
            scale=10,
            maxPixels=1e9
        )
        
        # 8. Export task
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        task_flood = ee.batch.Export.image.toDrive(
            image=flood_mask.selfMask(),
            description=f'Flood_Orbit55_{timestamp}',
            folder='TinhTuc_GEE_Results',
            region=ROI,
            scale=10,
            crs='EPSG:32648',
            maxPixels=1e9
        )
        
        task_diff = ee.batch.Export.image.toDrive(
            image=diff_vv,
            description=f'Flood_Diff_VV_{timestamp}',
            folder='TinhTuc_GEE_Results',
            region=ROI,
            scale=10,
            crs='EPSG:32648',
            maxPixels=1e9
        )
        
        task_flood.start()
        task_diff.start()
        
        self.tasks.extend([
            {'name': 'Flood_Mask', 'task': task_flood, 'type': 'image'},
            {'name': 'Flood_Diff', 'task': task_diff, 'type': 'image'}
        ])
        
        # Thông tin
        result_info = {
            'workflow': 'flood_event',
            'baseline_period': (baseline_start, baseline_end),
            'event_period': (event_start, event_end),
            'orbit': 55,
            'pass': 'ASCENDING',
            'threshold_formula': 'μ - 1.5σ',
            'exports': [
                f'Flood_Orbit55_{timestamp}',
                f'Flood_Diff_VV_{timestamp}'
            ],
            'timestamp': timestamp
        }
        
        logger.info(f"✅ Đã tạo export tasks: {result_info['exports']}")
        logger.info("📤 Kết quả sẽ được lưu vào Google Drive: TinhTuc_GEE_Results/")
        
        return result_info
    
    def run_subsidence_proxy(self, start_date: str = '2020-01-01', end_date: str = '2025-12-31') -> Dict:
        """
        Workflow 2: Subsidence Proxy Detection (Cấp 1).
        
        Phân tích xu hướng backscatter dài hạn với Orbit 55.
        """
        logger.info("=" * 60)
        logger.info("📉 WORKFLOW 2: Subsidence Proxy Detection (Cấp 1)")
        logger.info(f"   Period: {start_date} → {end_date}")
        logger.info("   Orbit: 55 (ASC) - Primary")
        logger.info("=" * 60)
        
        # Load S1 chỉ Orbit 55
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(ROI) \
            .filterDate(start_date, end_date) \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.eq('relativeOrbitNumber_start', 55)) \
            .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')) \
            .select(['VV', 'VH'])
        
        # Tính temporal statistics
        vv_mean = s1.select('VV').mean()
        vv_std = s1.select('VV').reduce(ee.Reducer.stdDev())
        
        # Stability index (tương đối)
        stability = vv_mean.divide(vv_std.add(1)).rename('stability_index')
        
        # Export
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        task_stability = ee.batch.Export.image.toDrive(
            image=stability,
            description=f'Stability_Orbit55_{timestamp}',
            folder='TinhTuc_GEE_Results',
            region=ROI,
            scale=30,
            crs='EPSG:32648',
            maxPixels=1e9
        )
        
        task_stability.start()
        
        self.tasks.append({
            'name': 'Stability_Index', 
            'task': task_stability, 
            'type': 'image'
        })
        
        result_info = {
            'workflow': 'subsidence_proxy',
            'period': (start_date, end_date),
            'orbit': 55,
            'exports': [f'Stability_Orbit55_{timestamp}'],
            'timestamp': timestamp
        }
        
        logger.info(f"✅ Đã tạo export: {result_info['exports']}")
        
        return result_info
    
    def run_primary_orbit55_analysis(self) -> Dict:
        """
        Workflow 3: Phân tích chuyên sâu chỉ với Orbit 55.
        """
        logger.info("=" * 60)
        logger.info("🛰️  WORKFLOW 3: Primary Orbit 55 Analysis")
        logger.info("   Chỉ sử dụng Orbit 55 ASC - 544 ảnh (48%)")
        logger.info("=" * 60)
        
        # Full time series Orbit 55
        s1_orbit55 = ee.ImageCollection('COPERNICUS/S1_GRD') \
            .filterBounds(ROI) \
            .filterDate('2015-02-20', '2026-04-26') \
            .filter(ee.Filter.eq('instrumentMode', 'IW')) \
            .filter(ee.Filter.eq('relativeOrbitNumber_start', 55)) \
            .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
        
        # Metadata export
        metadata = s1_orbit55.map(lambda img: ee.Feature(None, {
            'id': img.id(),
            'date': img.date().format('YYYY-MM-dd HH:mm:ss'),
            'orbit': img.get('relativeOrbitNumber_start'),
            'pass': img.get('orbitProperties_pass'),
            'platform': img.get('platform_number')
        }))
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        task_metadata = ee.batch.Export.table.toDrive(
            collection=metadata,
            description=f'Orbit55_Metadata_{timestamp}',
            folder='TinhTuc_GEE_Results',
            fileFormat='CSV'
        )
        
        task_metadata.start()
        
        self.tasks.append({
            'name': 'Orbit55_Metadata',
            'task': task_metadata,
            'type': 'table'
        })
        
        # Thống kê
        total_images = s1_orbit55.size().getInfo()
        
        result_info = {
            'workflow': 'orbit55_analysis',
            'total_images': total_images,
            'orbit': 55,
            'period': ('2015-02-20', '2026-04-26'),
            'exports': [f'Orbit55_Metadata_{timestamp}'],
            'timestamp': timestamp
        }
        
        logger.info(f"✅ Tìm thấy {total_images} ảnh Orbit 55")
        logger.info(f"✅ Đã tạo export: {result_info['exports']}")
        
        return result_info
    
    def check_task_status(self, wait: bool = True, timeout: int = 300) -> List[Dict]:
        """Kiểm tra trạng thái các GEE export tasks."""
        logger.info("\n📊 Kiểm tra trạng thái export tasks...")
        
        results = []
        start_time = time.time()
        
        for task_info in self.tasks:
            task = task_info['task']
            task_id = task.id
            
            logger.info(f"\n📝 Task: {task_info['name']} ({task_id})")
            
            if not wait:
                # Chỉ hiển thị trạng thái hiện tại
                status = task.status()
                logger.info(f"   Status: {status.get('state', 'Unknown')}")
                results.append({
                    'name': task_info['name'],
                    'id': task_id,
                    'status': status.get('state'),
                    'type': task_info['type']
                })
            else:
                # Chờ task hoàn thành
                while True:
                    status = task.status()
                    state = status.get('state', 'Unknown')
                    
                    if state in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        logger.info(f"   ✅ Final status: {state}")
                        results.append({
                            'name': task_info['name'],
                            'id': task_id,
                            'status': state,
                            'type': task_info['type']
                        })
                        break
                    
                    elapsed = time.time() - start_time
                    if elapsed > timeout:
                        logger.warning(f"   ⏱️ Timeout sau {timeout}s")
                        results.append({
                            'name': task_info['name'],
                            'id': task_id,
                            'status': 'TIMEOUT',
                            'type': task_info['type']
                        })
                        break
                    
                    logger.info(f"   ⏳ {state}... ({int(elapsed)}s)")
                    time.sleep(10)
        
        return results
    
    def save_report(self, results: List[Dict]) -> Path:
        """Lưu báo cáo kết quả."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.output_dir / f'gee_run_report_{timestamp}.json'
        
        report = {
            'timestamp': timestamp,
            'workflows_run': len(results),
            'tasks': results,
            'output_directory': str(self.output_dir),
            'google_drive_folder': 'TinhTuc_GEE_Results'
        }
        
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding='utf-8')
        logger.info(f"\n📄 Báo cáo đã lưu: {report_path}")
        
        return report_path


def main():
    parser = argparse.ArgumentParser(
        description='GEE Workflow Runner - Tự động chạy GEE và xử lý kết quả',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python gee_runner.py --workflow flood              # Chạy flood detection
    python gee_runner.py --workflow subsidence        # Chạy subsidence proxy
    python gee_runner.py --workflow orbit55           # Chạy Orbit 55 analysis
    python gee_runner.py --all                        # Chạy tất cả workflows
    python gee_runner.py --workflow flood --wait      # Chạy và chờ kết quả
        """
    )
    
    parser.add_argument(
        '--workflow',
        choices=['flood', 'subsidence', 'orbit55'],
        help='Chọn workflow để chạy'
    )
    
    parser.add_argument(
        '--all',
        action='store_true',
        help='Chạy tất cả workflows'
    )
    
    parser.add_argument(
        '--wait',
        action='store_true',
        help='Chờ tasks hoàn thành (không chỉ submit)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=300,
        help='Timeout chờ tasks (giây, mặc định 300)'
    )
    
    parser.add_argument(
        '--key',
        type=Path,
        default=DEFAULT_KEY_PATH,
        help='Đường dẫn đến service account key'
    )
    
    args = parser.parse_args()
    
    if not args.workflow and not args.all:
        parser.print_help()
        sys.exit(1)
    
    # Khởi tạo GEE
    try:
        initialize_ee(args.key)
    except Exception as e:
        logger.error(f"❌ Không thể kết nối GEE: {e}")
        sys.exit(1)
    
    # Load ROI từ GeoJSON
    global ROI
    ROI = load_roi_from_geojson()
    
    # Chạy workflows
    runner = GEEWorkflowRunner()
    all_results = []
    
    try:
        if args.all or args.workflow == 'flood':
            result = runner.run_flood_event_analysis()
            all_results.append(result)
        
        if args.all or args.workflow == 'subsidence':
            result = runner.run_subsidence_proxy()
            all_results.append(result)
        
        if args.all or args.workflow == 'orbit55':
            result = runner.run_primary_orbit55_analysis()
            all_results.append(result)
        
        # Kiểm tra trạng thái
        if runner.tasks:
            task_results = runner.check_task_status(wait=args.wait, timeout=args.timeout)
            
            # Lưu báo cáo với cấu trúc mới (OutputManager)
            try:
                from src.utils.output_manager import OutputManager
                manager = OutputManager()
                
                # Dọn dẹp reports cũ trước khi lưu mới
                manager.cleanup_old_reports(max_gee_reports=5, max_age_days=30)
                
                # Lưu báo cáo với cấu trúc thời gian
                report_data = {
                    'workflows': all_results,
                    'tasks': task_results,
                    'google_drive_folder': 'TinhTuc_GEE_Results'
                }
                report_path = manager.save_gee_report(report_data, compress=False)
                
                # Backup tự động
                manager.backup_important_reports()
                
            except Exception as e:
                logger.warning(f"OutputManager failed, using legacy save: {e}")
                report_path = runner.save_report(all_results)
            
            # Tóm tắt
            logger.info("\n" + "=" * 60)
            logger.info("📊 TÓM TẮT")
            logger.info("=" * 60)
            logger.info(f"Workflows đã chạy: {len(all_results)}")
            logger.info(f"Export tasks: {len(runner.tasks)}")
            logger.info(f"Kết quả Google Drive: TinhTuc_GEE_Results/")
            logger.info(f"Báo cáo local: {report_path}")
            logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ Lỗi khi chạy workflow: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
