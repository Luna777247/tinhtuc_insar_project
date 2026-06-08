import os
import sys
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import asf_search as asf

# Thêm đường dẫn gốc để import config
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import AOI

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def perform_s1_audit(output_csv: Path):
    """
    Truy vấn thư viện ASF để lấy danh sách ảnh Sentinel-1 SLC tại AOI Tĩnh Túc
    và xuất kết quả kiểm kê (audit) ra file CSV.
    """
    logger.info(f"Bắt đầu Data Audit cho khu vực: {AOI['name']}")
    
    # 1. Định nghĩa WKT Polygon từ Bounding Box của AOI
    lon_min, lat_min = AOI['lon_min'], AOI['lat_min']
    lon_max, lat_max = AOI['lon_max'], AOI['lat_max']
    
    wkt = f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, {lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
    logger.info(f"AOI WKT: {wkt}")

    # 2. Truy vấn ASF Search
    logger.info("Đang truy vấn metadata từ hệ thống ASF (Alaska Satellite Facility)...")
    try:
        results = asf.geo_search(
            platform=[asf.PLATFORM.SENTINEL1],
            processingLevel=asf.PRODUCT_TYPE.SLC,
            beamMode=asf.BEAMMODE.IW,
            start="2014-01-01",
            end=datetime.now().strftime("%Y-%m-%d"),
            intersectsWith=wkt
        )
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn ASF: {e}")
        return

    logger.info(f"Tìm thấy {len(results)} cảnh (scenes) Sentinel-1 SLC.")

    if len(results) == 0:
        logger.warning("Không tìm thấy dữ liệu. Vui lòng kiểm tra lại cấu hình AOI.")
        return

    # 3. Chuyển đổi kết quả sang Pandas DataFrame
    records = []
    for r in results:
        props = r.properties
        records.append({
            "scene_id": props.get("sceneName"),
            "platform": props.get("platform"),
            "acquisition_date": props.get("startTime"),
            "orbit_pass": props.get("flightDirection"),
            "relative_orbit": props.get("pathNumber"),
            "absolute_orbit": props.get("orbit"),
            "polarization": props.get("polarization"),
            "size_mb": round(props.get("bytes", 0) / (1024 * 1024), 1)
        })

    df = pd.DataFrame(records)
    
    # Chuyển đổi ngày tháng và sắp xếp
    df['acquisition_date'] = pd.to_datetime(df['acquisition_date'])
    df = df.sort_values(by=['orbit_pass', 'relative_orbit', 'acquisition_date']).reset_index(drop=True)

    # 4. Tính toán khoảng cách ngày (Gap Days) cho từng chuỗi (pass + relative_orbit)
    df['gap_days'] = None
    for (opass, orbit), group in df.groupby(['orbit_pass', 'relative_orbit']):
        diffs = group['acquisition_date'].diff().dt.days
        df.loc[group.index, 'gap_days'] = diffs

    # 5. Xuất ra CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_csv, index=False)
    logger.info(f"Đã lưu kết quả Audit tại: {output_csv}")

    # 6. In Báo cáo Tổng quan (Summary)
    print("\n" + "="*60)
    print("BÁO CÁO KIỂM KÊ DỮ LIỆU SENTINEL-1 (DATA AUDIT SUMMARY)")
    print("="*60)
    print(f"Tổng số ảnh SLC tìm thấy: {len(df)}")
    
    print("\n[Phân bố theo nền tảng (Platform)]")
    print(df['platform'].value_counts().to_string())
    
    print("\n[Phân bố theo Hướng bay (Orbit Pass)]")
    print(df['orbit_pass'].value_counts().to_string())

    print("\n[Chi tiết theo Quỹ đạo tương đối (Relative Orbit)]")
    orbit_summary = df.groupby(['orbit_pass', 'relative_orbit']).agg(
        total_images=('scene_id', 'count'),
        start_date=('acquisition_date', 'min'),
        end_date=('acquisition_date', 'max'),
        max_gap_days=('gap_days', 'max')
    ).reset_index()
    
    # Format dates
    orbit_summary['start_date'] = orbit_summary['start_date'].dt.strftime('%Y-%m-%d')
    orbit_summary['end_date'] = orbit_summary['end_date'].dt.strftime('%Y-%m-%d')
    print(orbit_summary.to_string(index=False))

    print("="*60)
    print("Kết luận: Nên chọn Relative Orbit có 'total_images' cao nhất và 'max_gap_days' thấp nhất để làm Stack chính cho quá trình P-SBAS.")

if __name__ == "__main__":
    out_path = ROOT / "outputs" / "reports" / "S1_Data_Audit_TinhTuc.csv"
    perform_s1_audit(out_path)
