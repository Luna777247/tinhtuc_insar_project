"""
GEE Result Processor - Download và xử lý kết quả từ GEE
========================================================

Script này:
1. Download kết quả từ Google Drive (nếu có API access)
2. Xử lý các file GeoTIFF từ GEE
3. Tạo visualization và thống kê
4. Tích hợp với Python pipeline

Usage:
    python run_processing_gee_result.py --input outputs/gee_results/
    python run_processing_gee_result.py --process-flood flood_map.tif
    python run_processing_gee_result.py --create-report

ROI: Sử dụng config/TinhTuc4326_200m.geojson cho spatial analysis
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import rasterio
from rasterio.plot import show
import matplotlib.pyplot as plt

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent
GEE_RESULTS_DIR = PROJECT_ROOT / "outputs" / "gee_results"
PROCESSED_DIR = PROJECT_ROOT / "outputs" / "processed"
REPORTS_DIR = PROJECT_ROOT / "outputs" / "reports"
GEOJSON_PATH = PROJECT_ROOT / "config" / "TinhTuc4326_200m.geojson"

# Load ROI từ GeoJSON
def load_roi_geojson(geojson_path: Path = GEOJSON_PATH) -> dict:
    """Load ROI từ GeoJSON file."""
    if not geojson_path.exists():
        logger.warning(f"GeoJSON không tìm thấy: {geojson_path}")
        return None
    
    with open(geojson_path, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    logger.info(f"✅ Đã load ROI GeoJSON: {geojson_path}")
    return geojson


class GEEResultProcessor:
    """Processor cho kết quả GEE."""
    
    def __init__(self):
        self.processed_dir = PROCESSED_DIR
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir = REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)
    
    def process_flood_result(
        self,
        flood_tif: Path,
        diff_tif: Optional[Path] = None,
        dem_tif: Optional[Path] = None
    ) -> Dict:
        """
        Xử lý kết quả flood detection.
        
        Returns:
            Dict với thông tin diện tích, thống kê, visualization paths
        """
        logger.info(f"🌊 Xử lý flood result: {flood_tif}")
        
        # Đọc flood mask
        with rasterio.open(flood_tif) as src:
            flood_mask = src.read(1)
            profile = src.profile
            transform = src.transform
            
            # Tính diện tích
            pixel_size = transform.a  # Resolution in meters
            pixel_area = pixel_size ** 2
            
            flooded_pixels = np.sum(flood_mask > 0)
            total_pixels = flood_mask.size
            area_m2 = flooded_pixels * pixel_area
            area_ha = area_m2 / 10000
            
            logger.info(f"   📊 Diện tích ngập: {area_ha:.2f} ha ({flooded_pixels} pixels)")
            logger.info(f"   📊 Phần trăm: {flooded_pixels/total_pixels*100:.2f}%")
        
        # Tạo visualization
        viz_path = self.processed_dir / f"{flood_tif.stem}_viz.png"
        self._create_flood_visualization(flood_mask, viz_path, area_ha)
        
        result = {
            'input_file': str(flood_tif),
            'flooded_pixels': int(flooded_pixels),
            'total_pixels': int(total_pixels),
            'area_m2': float(area_m2),
            'area_ha': float(area_ha),
            'percentage': float(flooded_pixels / total_pixels * 100),
            'pixel_size_m': pixel_size,
            'visualization': str(viz_path),
            'processing_timestamp': datetime.now().isoformat()
        }
        
        return result
    
    def process_stability_index(self, stability_tif: Path) -> Dict:
        """Xử lý stability index từ subsidence proxy analysis."""
        logger.info(f"📉 Xử lý stability index: {stability_tif}")
        
        with rasterio.open(stability_tif) as src:
            stability = src.read(1)
            
            # Thống kê
            mean_stability = np.mean(stability[stability > 0])
            std_stability = np.std(stability[stability > 0])
            
            # Phân loại vùng
            low_stability = np.sum(stability < 0.3)  # High variance = potential subsidence
            med_stability = np.sum((stability >= 0.3) & (stability < 0.7))
            high_stability = np.sum(stability >= 0.7)
            
            logger.info(f"   📊 Mean stability: {mean_stability:.3f}")
            logger.info(f"   📊 Low stability (potential subsidence): {low_stability} pixels")
        
        # Visualization
        viz_path = self.processed_dir / f"{stability_tif.stem}_viz.png"
        self._create_stability_visualization(stability, viz_path)
        
        return {
            'input_file': str(stability_tif),
            'mean_stability': float(mean_stability),
            'std_stability': float(std_stability),
            'low_stability_pixels': int(low_stability),
            'med_stability_pixels': int(med_stability),
            'high_stability_pixels': int(high_stability),
            'visualization': str(viz_path)
        }
    
    def process_orbit55_metadata(self, metadata_csv: Path) -> pd.DataFrame:
        """Xử lý metadata Orbit 55 từ GEE."""
        logger.info(f"🛰️ Xử lý Orbit 55 metadata: {metadata_csv}")
        
        df = pd.read_csv(metadata_csv)
        
        # Phân tích
        df['date'] = pd.to_datetime(df['date'])
        df['year'] = df['date'].dt.year
        df['month'] = df['date'].dt.month
        
        # Thống kê
        stats = {
            'total_images': len(df),
            'date_range': (df['date'].min().isoformat(), df['date'].max().isoformat()),
            'years': df['year'].nunique(),
            'images_per_year': df.groupby('year').size().to_dict(),
            'platforms': df['platform'].value_counts().to_dict()
        }
        
        logger.info(f"   📊 Tổng ảnh: {stats['total_images']}")
        logger.info(f"   📊 Phạm vi: {stats['date_range'][0]} → {stats['date_range'][1]}")
        logger.info(f"   📊 Platforms: {stats['platforms']}")
        
        # Lưu phân tích
        output_csv = self.processed_dir / f"{metadata_csv.stem}_analysis.csv"
        df.to_csv(output_csv, index=False)
        
        # Visualization
        viz_path = self.processed_dir / f"{metadata_csv.stem}_timeline.png"
        self._create_timeline_visualization(df, viz_path)
        
        return df, stats
    
    def _create_flood_visualization(
        self,
        flood_mask: np.ndarray,
        output_path: Path,
        area_ha: float
    ):
        """Tạo visualization cho flood result."""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # Hiển thị flood mask
        im = ax.imshow(flood_mask, cmap='Blues', interpolation='nearest')
        ax.set_title(f'Flood Detection - Area: {area_ha:.2f} ha', fontsize=14)
        ax.axis('off')
        
        # Colorbar
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Flood Mask')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"   🎨 Visualization saved: {output_path}")
    
    def _create_stability_visualization(self, stability: np.ndarray, output_path: Path):
        """Tạo visualization cho stability index."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        
        # Map
        im = ax1.imshow(stability, cmap='RdYlGn', vmin=0, vmax=1)
        ax1.set_title('Stability Index (Orbit 55)', fontsize=14)
        ax1.axis('off')
        plt.colorbar(im, ax=ax1, label='Stability (0=unstable, 1=stable)')
        
        # Histogram
        ax2.hist(stability.flatten(), bins=50, color='steelblue', edgecolor='black')
        ax2.set_xlabel('Stability Index')
        ax2.set_ylabel('Frequency')
        ax2.set_title('Distribution of Stability Index')
        ax2.axvline(0.3, color='red', linestyle='--', label='Low stability threshold')
        ax2.legend()
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"   🎨 Visualization saved: {output_path}")
    
    def _create_timeline_visualization(self, df: pd.DataFrame, output_path: Path):
        """Tạo timeline visualization cho metadata."""
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
        
        # Timeline
        df_sorted = df.sort_values('date')
        ax1.scatter(df_sorted['date'], [1]*len(df_sorted), c='steelblue', s=10)
        ax1.set_xlabel('Date')
        ax1.set_ylabel('Images')
        ax1.set_title('Orbit 55 Image Timeline')
        ax1.set_yticks([])
        
        # Images per year
        yearly = df.groupby('year').size()
        ax2.bar(yearly.index, yearly.values, color='steelblue', edgecolor='black')
        ax2.set_xlabel('Year')
        ax2.set_ylabel('Number of Images')
        ax2.set_title('Images per Year (Orbit 55)')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        logger.info(f"   🎨 Timeline saved: {output_path}")
    
    def create_comprehensive_report(self, results: List[Dict]) -> Path:
        """Tạo báo cáo tổng hợp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_path = self.reports_dir / f'gee_processing_report_{timestamp}.html'
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>GEE Processing Report - {timestamp}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        h1 {{ color: #2c3e50; }}
        h2 {{ color: #34495e; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        .metric {{ font-size: 24px; font-weight: bold; color: #2980b9; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
    </style>
</head>
<body>
    <h1>🛰️ Google Earth Engine Processing Report</h1>
    <p>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
    
    <h2>📊 Tổng Quan</h2>
    <table>
        <tr><th>Metric</th><th>Value</th></tr>
        <tr><td>Workflows Processed</td><td class="metric">{len(results)}</td></tr>
        <tr><td>Output Directory</td><td>{self.processed_dir}</td></tr>
    </table>
"""
        
        # Thêm chi tiết từng workflow
        for i, result in enumerate(results, 1):
            html_content += f"""
    <h2>Workflow {i}: {result.get('workflow', 'Unknown')}</h2>
    <table>
"""
            for key, value in result.items():
                if key != 'workflow':
                    html_content += f"        <tr><td>{key}</td><td>{value}</td></tr>\n"
            
            html_content += "    </table>\n"
        
        html_content += """
</body>
</html>
"""
        
        report_path.write_text(html_content, encoding='utf-8')
        logger.info(f"📄 Báo cáo HTML: {report_path}")
        
        return report_path


def scan_gee_results(directory: Path = GEE_RESULTS_DIR) -> List[Path]:
    """Quét thư mục tìm kết quả GEE."""
    if not directory.exists():
        logger.warning(f"Thư mục không tồn tại: {directory}")
        return []
    
    tif_files = list(directory.glob('*.tif'))
    csv_files = list(directory.glob('*.csv'))
    
    logger.info(f"🔍 Tìm thấy {len(tif_files)} GeoTIFF, {len(csv_files)} CSV")
    
    return tif_files + csv_files


def main():
    parser = argparse.ArgumentParser(
        description='GEE Result Processor - Xử lý kết quả từ GEE'
    )
    
    parser.add_argument(
        '--input-dir',
        type=Path,
        default=GEE_RESULTS_DIR,
        help='Thư mục chứa kết quả GEE'
    )
    
    parser.add_argument(
        '--process-flood',
        type=Path,
        help='Xử lý file flood detection GeoTIFF'
    )
    
    parser.add_argument(
        '--process-stability',
        type=Path,
        help='Xử lý file stability index GeoTIFF'
    )
    
    parser.add_argument(
        '--process-metadata',
        type=Path,
        help='Xử lý file metadata CSV'
    )
    
    parser.add_argument(
        '--scan-and-process',
        action='store_true',
        help='Tự động quét và xử lý tất cả files'
    )
    
    parser.add_argument(
        '--create-report',
        action='store_true',
        help='Tạo báo cáo tổng hợp'
    )
    
    args = parser.parse_args()
    
    processor = GEEResultProcessor()
    all_results = []
    
    if args.scan_and_process:
        files = scan_gee_results(args.input_dir)
        
        for file_path in files:
            try:
                if 'flood' in file_path.name.lower() and file_path.suffix == '.tif':
                    result = processor.process_flood_result(file_path)
                    all_results.append(result)
                elif 'stability' in file_path.name.lower() and file_path.suffix == '.tif':
                    result = processor.process_stability_index(file_path)
                    all_results.append(result)
                elif 'metadata' in file_path.name.lower() and file_path.suffix == '.csv':
                    df, stats = processor.process_orbit55_metadata(file_path)
                    all_results.append({'workflow': 'metadata', **stats})
            except Exception as e:
                logger.error(f"❌ Lỗi xử lý {file_path}: {e}")
    
    if args.process_flood:
        result = processor.process_flood_result(args.process_flood)
        all_results.append(result)
    
    if args.process_stability:
        result = processor.process_stability_index(args.process_stability)
        all_results.append(result)
    
    if args.process_metadata:
        df, stats = processor.process_orbit55_metadata(args.process_metadata)
        all_results.append({'workflow': 'metadata', **stats})
    
    if args.create_report and all_results:
        report_path = processor.create_comprehensive_report(all_results)
        logger.info(f"\n✅ Hoàn thành! Báo cáo: {report_path}")
    
    if not all_results:
        logger.info("ℹ️ Không có kết quả nào được xử lý. Sử dụng --scan-and-process hoặc chỉ định file cụ thể.")
        parser.print_help()


if __name__ == '__main__':
    main()
