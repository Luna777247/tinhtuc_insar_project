"""
Fix GeoJSON cho GEE - Chuyển đổi sang format GEE chấp nhận
=======================================================

GEE cần format: {"type": "Polygon", "coordinates": [[ [lon,lat], ... ]]}

Chạy: python fix_geojson_gee.py
"""

import json
from pathlib import Path
import shutil

GEOJSON_PATH = Path("config/TinhTuc4326_200m.geojson")

def fix_for_gee():
    print(f"🔧 Fix GeoJSON cho GEE: {GEOJSON_PATH}")
    
    if not GEOJSON_PATH.exists():
        print(f"❌ Không tìm thấy file!")
        return False
    
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    # Trích xuất coordinates
    if geojson['type'] == 'FeatureCollection' and geojson.get('features'):
        geom = geojson['features'][0]['geometry']
        coords = geom['coordinates']
        print(f"   Trích từ FeatureCollection → Polygon")
    elif geojson['type'] == 'Feature':
        coords = geojson['geometry']['coordinates']
        print(f"   Trích từ Feature → Polygon")
    elif geojson['type'] == 'Polygon':
        coords = geojson['coordinates']
        print(f"   Đã là Polygon")
    else:
        print(f"❌ Không hỗ trợ type: {geojson['type']}")
        return False
    
    # Đảm bảo đúng nesting cho GEE
    # GEE cần: [[ [lon,lat], [lon,lat], ... ]]
    # Tức là list của list của [lon,lat] pairs
    
    if not isinstance(coords, list):
        print(f"❌ Không phải list")
        return False
    
    # Kiểm tra cấp nesting
    if len(coords) > 0:
        if isinstance(coords[0], list) and len(coords[0]) > 0:
            if isinstance(coords[0][0], (int, float)):
                # coords là [[lon,lat], [lon,lat]] - thiếu 1 level
                print(f"   Thêm 1 level nesting")
                coords = [coords]
            elif isinstance(coords[0][0], list) and len(coords[0][0]) == 2:
                # coords là [[[lon,lat], ...]] - đúng rồi
                print(f"   Đã đúng 3-level nesting")
    
    # Đảm bảo đóng vòng
    for ring in coords:
        if ring[0] != ring[-1]:
            print(f"   Đóng vòng cho ring")
            ring.append(ring[0])
    
    # Tạo simple Polygon
    simple = {
        "type": "Polygon",
        "coordinates": coords
    }
    
    # Backup và lưu
    backup_path = GEOJSON_PATH.with_suffix('.original.geojson')
    shutil.copy2(GEOJSON_PATH, backup_path)
    
    with open(GEOJSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(simple, f, indent=2)
    
    print(f"✅ Đã fix GeoJSON!")
    print(f"   Backup: {backup_path}")
    print(f"   Số rings: {len(coords)}")
    print(f"   Số điểm ring 1: {len(coords[0])}")
    print(f"   Đóng vòng: {coords[0][0] == coords[0][-1]}")
    
    return True

if __name__ == '__main__':
    success = fix_for_gee()
    if success:
        print(f"\n🎉 Chạy lại: python run_pipeline_gee.py --all")
    else:
        print(f"\n❌ Fix thất bại, dùng ROI mặc định")
