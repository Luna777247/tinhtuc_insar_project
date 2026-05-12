"""
Debug GeoJSON cho GEE - Kiểm tra chi tiết format
================================================

Chạy: python debug_geojson.py
"""

import json
from pathlib import Path

GEOJSON_PATH = Path("config/TinhTuc4326_200m.geojson")

def debug_geojson():
    print(f"🔍 Debug: {GEOJSON_PATH}")
    
    if not GEOJSON_PATH.exists():
        print(f"❌ Không tìm thấy file!")
        return
    
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    print(f"\n📋 Root type: {geojson.get('type', 'Unknown')}")
    
    # Xử lý theo type
    if geojson['type'] == 'FeatureCollection':
        print(f"   Số features: {len(geojson.get('features', []))}")
        if geojson['features']:
            feature = geojson['features'][0]
            print(f"   Feature[0] type: {feature.get('type')}")
            geom = feature.get('geometry', {})
            print(f"   Geometry type: {geom.get('type')}")
            coords = geom.get('coordinates', [])
    elif geojson['type'] == 'Feature':
        geom = geojson.get('geometry', {})
        print(f"   Geometry type: {geom.get('type')}")
        coords = geom.get('coordinates', [])
    elif geojson['type'] == 'Polygon':
        coords = geojson.get('coordinates', [])
    else:
        coords = geojson.get('coordinates', [])
    
    # Phân tích nesting
    print(f"\n🔍 Phân tích coordinates:")
    print(f"   Type: {type(coords)}")
    if isinstance(coords, list):
        print(f"   Len: {len(coords)}")
        if len(coords) > 0:
            print(f"   coords[0] type: {type(coords[0])}")
            if isinstance(coords[0], list):
                print(f"   coords[0] len: {len(coords[0])}")
                if len(coords[0]) > 0:
                    print(f"   coords[0][0] type: {type(coords[0][0])}")
                    print(f"   coords[0][0]: {coords[0][0]}")
    
    # Kiểm tra format GEE
    print(f"\n🎯 Format cho GEE:")
    print(f"   Cần: [[ [lon, lat], [lon, lat], ... ]] (Polygon with one ring)")
    print(f"   Hoặc: [[[ [lon, lat], ... ], [hole1], ... ]] (Polygon with holes)")
    
    # Kiểm tra lỗi phổ biến
    errors = []
    
    if not isinstance(coords, list):
        errors.append("❌ Không phải list")
    elif len(coords) == 0:
        errors.append("❌ Empty coordinates")
    elif not isinstance(coords[0], list):
        errors.append("❌ coords[0] không phải list (cần ít nhất 2 levels)")
    elif len(coords[0]) == 0:
        errors.append("❌ Ring rỗng")
    elif not isinstance(coords[0][0], list):
        errors.append("❌ coords[0][0] không phải [lon, lat] pair")
    elif len(coords[0][0]) != 2:
        errors.append(f"❌ coords[0][0] có {len(coords[0][0])} phần tử, cần 2 [lon, lat]")
    elif coords[0][0] == coords[0][-1]:
        print("   ✅ Polygon đóng vòng")
    else:
        errors.append("⚠️ Polygon không đóng vòng")
    
    if errors:
        print(f"\n❌ Lỗi phát hiện:")
        for e in errors:
            print(f"   {e}")
    else:
        print(f"\n✅ Cấu trúc cơ bản đúng!")
    
    # Đề xuất fix
    print(f"\n💡 Đề xuất:")
    
    # Trích xuất simple polygon
    if geojson['type'] == 'FeatureCollection' and geojson.get('features'):
        simple_polygon = {
            "type": "Polygon",
            "coordinates": geojson['features'][0]['geometry']['coordinates']
        }
        simple_path = GEOJSON_PATH.with_suffix('.simple.geojson')
        with open(simple_path, 'w', encoding='utf-8') as f:
            json.dump(simple_polygon, f, indent=2)
        print(f"   ✅ Đã tạo Simple Polygon: {simple_path}")
        print(f"   Thay thế file gốc bằng simple version:")
        print(f"   copy {simple_path} {GEOJSON_PATH}")

if __name__ == '__main__':
    debug_geojson()
