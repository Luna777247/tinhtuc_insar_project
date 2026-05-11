#!/usr/bin/env python
"""
Kết nối GEE bằng Service Account (private key).
File: gee_scripts/gee-private-key.json
"""

import ee
from pathlib import Path

# Đường dẫn đến service account key
PRIVATE_KEY_PATH = Path("gee_scripts/gee-private-key.json")

def initialize_ee_with_service_account():
    """Khởi tạo GEE với service account."""
    
    if not PRIVATE_KEY_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy: {PRIVATE_KEY_PATH}")
    
    # Cách 1: Sử dụng service_account_file (đơn giản nhất)
    try:
        ee.Initialize(service_account_file=str(PRIVATE_KEY_PATH))
        print("✅ Kết nối GEE thành công (Service Account)")
        return True
    except Exception as e1:
        print(f"Cách 1 thất bại: {e1}")
        
        # Cách 2: Sử dụng credentials object
        try:
            from google.oauth2 import service_account
            
            credentials = service_account.Credentials.from_service_account_file(
                str(PRIVATE_KEY_PATH),
                scopes=['https://www.googleapis.com/auth/earthengine',
                        'https://www.googleapis.com/auth/drive']
            )
            ee.Initialize(credentials=credentials)
            print("✅ Kết nối GEE thành công (Credentials Object)")
            return True
        except Exception as e2:
            print(f"Cách 2 thất bại: {e2}")
            raise

def get_sentinel1_data():
    """Lấy dữ liệu Sentinel-1 cho sự kiện mưa lũ."""
    
    # Định nghĩa AOI Tĩnh Túc
    aoi = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80])
    
    print("\n📡 Truy vấn Sentinel-1...")
    
    # Ảnh baseline (trước mưa)
    # LƯU Ý: GEE cung cấp S1 GRD đã ở đơn vị dB (10*log10σ°)
    baseline = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(aoi) \
        .filterDate('2025-09-15', '2025-09-20') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
        .select('VH') \
        .median()
    
    # Ảnh event (ngập lụt 29/09)
    flood_event = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(aoi) \
        .filterDate('2025-09-28', '2025-09-30') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.eq('relativeOrbitNumber_start', 55)) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
        .select('VH') \
        .median()
    
    # Ảnh event (sạt lở 01/10)
    landslide_event = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(aoi) \
        .filterDate('2025-10-01', '2025-10-02') \
        .filter(ee.Filter.eq('instrumentMode', 'IW')) \
        .filter(ee.Filter.eq('relativeOrbitNumber_start', 91)) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH')) \
        .select('VH') \
        .median()
    
    # Kiểm tra dữ liệu
    print("  ✓ Baseline (15-20/09): Đã truy vấn")
    print("  ✓ Flood event (29/09, Orbit 55): Đã truy vấn")
    print("  ✓ Landslide event (01/10, Orbit 91): Đã truy vấn")
    
    return {
        'aoi': aoi,
        'baseline': baseline,
        'flood': flood_event,
        'landslide': landslide_event
    }

def download_directly(data, output_dir='outputs/events/20250928_1001'):
    """Tải dữ liệu trực tiếp về máy tính."""
    
    from pathlib import Path
    import urllib.request
    import time
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"\n💾 Tải dữ liệu trực tiếp về: {output_path.absolute()}")
    
    aoi = data['aoi']
    
    # Danh sách dữ liệu cần tải
    datasets = [
        ('baseline', data['baseline'], 'S1_VH_Baseline_20250919.tif'),
        ('flood', data['flood'], 'S1_VH_Flood_20250929.tif'),
        ('landslide', data['landslide'], 'S1_VH_Landslide_20251001.tif'),
    ]
    
    downloaded_files = []
    
    for name, image, filename in datasets:
        print(f"\n  📥 Đang tải {name}...")
        
        try:
            # Lấy download URL từ GEE
            url = image.getDownloadURL({
                'name': name,
                'region': aoi,
                'scale': 10,
                'crs': 'EPSG:4326',
                'format': 'GEO_TIFF',
                'maxPixels': 1e9
            })
            
            # Tải file
            filepath = output_path / filename
            print(f"     URL: {url[:80]}...")
            print(f"     Lưu: {filepath}")
            
            # Download với timeout và retry
            for attempt in range(3):
                try:
                    urllib.request.urlretrieve(url, str(filepath))
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"     Thử lại {attempt + 2}/3...")
                        time.sleep(5)
                    else:
                        raise
            
            # Kiểm tra file
            if filepath.exists():
                size_mb = filepath.stat().st_size / (1024 * 1024)
                print(f"     ✅ Hoàn thành: {size_mb:.2f} MB")
                downloaded_files.append(str(filepath))
            else:
                print(f"     ❌ File không tồn tại sau khi tải")
                
        except Exception as e:
            print(f"     ❌ Lỗi: {e}")
            # Fallback: Export ra Drive
            print(f"     → Fallback: Xuất ra Google Drive...")
            task = ee.batch.Export.image.toDrive(
                image=image,
                description=f'S1_VH_{name}_2025',
                folder='TinhTuc_Exports',
                region=aoi,
                scale=10,
                crs='EPSG:4326',
                maxPixels=1e9
            )
            task.start()
            print(f"     → Task ID: {task.id}")
    
    return downloaded_files

def export_to_drive(data, folder_name='TinhTuc_Exports'):
    """Xuất dữ liệu ra Google Drive (backup)."""
    
    print(f"\n☁️ Backup ra Google Drive (folder: {folder_name})...")
    
    aoi = data['aoi']
    
    tasks = []
    datasets = [
        ('Baseline', data['baseline'], 'S1_VH_Baseline_20250919'),
        ('Flood', data['flood'], 'S1_VH_Flood_20250929'),
        ('Landslide', data['landslide'], 'S1_VH_Landslide_20251001'),
    ]
    
    for name, image, desc in datasets:
        task = ee.batch.Export.image.toDrive(
            image=image,
            description=desc,
            folder=folder_name,
            region=aoi,
            scale=10,
            crs='EPSG:4326',
            maxPixels=1e9
        )
        task.start()
        tasks.append((name, task))
        print(f"  → {name}: {task.id}")
    
    return tasks

def main():
    """Main function."""
    try:
        # 1. Khởi tạo GEE
        initialize_ee_with_service_account()
        
        # 2. Lấy dữ liệu
        data = get_sentinel1_data()
        
        # 3. Tải trực tiếp về máy (ưu tiên)
        downloaded = download_directly(data, output_dir='outputs/events/20250928_1001')
        
        # 4. Backup ra Drive (không chờ)
        tasks = export_to_drive(data)
        
        print("\n" + "="*60)
        print("✅ HOÀN THÀNH!")
        print("="*60)
        
        if downloaded:
            print(f"\n📁 Đã tải {len(downloaded)} file về máy:")
            for f in downloaded:
                print(f"   • {f}")
        
        print(f"\n☁️ Đã tạo {len(tasks)} task trên Google Drive")
        print("   (Backup trong folder: TinhTuc_Exports)")
        
    except Exception as e:
        print(f"\n❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    main()
