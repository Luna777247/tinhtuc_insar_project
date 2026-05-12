"""
Kiểm tra và sửa GeoJSON cho GEE
==============================

Chạy: python check_geojson.py
"""

import json
from pathlib import Path

GEOJSON_PATH = Path("config/TinhTuc4326_200m.geojson")

def check_and_fix_geojson():
    print(f"🔍 Kiểm tra: {GEOJSON_PATH}")
    
    if not GEOJSON_PATH.exists():
        print(f"❌ Không tìm thấy file!")
        return
    
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    print(f"📋 Type: {geojson.get('type', 'Unknown')}")
    
    # Lấy coordinates
    if geojson['type'] == 'Polygon':
        coords = geojson['coordinates']
    elif geojson['type'] == 'FeatureCollection':
        coords = geojson['features'][0]['geometry']['coordinates']
        print(f"   Feature type: {geojson['features'][0]['geometry']['type']}")
    elif geojson['type'] == 'Feature':
        coords = geojson['geometry']['coordinates']
        print(f"   Geometry type: {geojson['geometry']['type']}")
    else:
        coords = geojson.get('coordinates', [])
    
    # Kiểm tra nesting
    print(f"\n🔍 Phân tích coordinates:")
    if isinstance(coords, list):
        print(f"   Top level: list với {len(coords)} phần tử")
        if len(coords) > 0:
            print(f"   Level 1[0]: {type(coords[0])}")
            if isinstance(coords[0], list):
                print(f"   Level 1[0] length: {len(coords[0])}")
                if len(coords[0]) > 0:
                    print(f"   Level 2[0]: {type(coords[0][0])} = {coords[0][0]}")
    
    # Kiểm tra đóng vòng
    if coords and isinstance(coords[0], list):
        ring = coords[0] if isinstance(coords[0][0], list) else coords
        first = ring[0] if len(ring) > 0 else None
        last = ring[-1] if len(ring) > 0 else None
        
        print(f"\n📍 Kiểm tra polygon:")
        print(f"   Tổng số điểm: {len(ring)}")
        print(f"   Điểm đầu: {first}")
        print(f"   Điểm cuối: {last}")
        print(f"   Đóng vòng: {first == last}")
        
        if first != last:
            print(f"\n⚠️  Polygon KHÔNG đóng vòng! Cần thêm điểm đầu vào cuối.")
            
            # Sửa GeoJSON
            ring.append(first)
            print(f"   ✅ Đã thêm điểm đầu vào cuối. Tổng điểm mới: {len(ring)}")
            
            # Lưu file mới
            fixed_path = GEOJSON_PATH.with_suffix('.fixed.geojson')
            with open(fixed_path, 'w', encoding='utf-8') as f:
                json.dump(geojson, f, indent=2)
            print(f"   💾 Đã lưu file sửa: {fixed_path}")
            
            # Thay thế file gốc
            backup_path = GEOJSON_PATH.with_suffix('.backup.geojson')
            GEOJSON_PATH.rename(backup_path)
            fixed_path.rename(GEOJSON_PATH)
            print(f"   ✅ Đã thay thế file gốc (backup: {backup_path})")
        else:
            print(f"\n✅ Polygon đã đóng vòng đúng!")

if __name__ == '__main__':
    check_and_fix_geojson()
