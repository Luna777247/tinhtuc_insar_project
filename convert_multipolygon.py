"""
Chuyển đổi MultiPolygon → Simple Polygon cho GEE
===============================================

GEE không hỗ trợ MultiPolygon phức tạp, cần chuyển sang Polygon đơn giản
hoặc dùng ee.Geometry.MultiPolygon thay vì ee.Geometry.Polygon

Chạy: python convert_multipolygon.py
"""

import json
import shutil
from pathlib import Path

GEOJSON_PATH = Path("config/TinhTuc4326_200m.geojson")

def convert_to_simple_polygon():
    print(f"🔧 Chuyển đổi: {GEOJSON_PATH}")
    
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    # Trích xuất từ FeatureCollection
    if geojson['type'] == 'FeatureCollection' and geojson.get('features'):
        feature = geojson['features'][0]
        geom = feature['geometry']
        properties = feature.get('properties', {})
    elif geojson['type'] == 'Feature':
        geom = geojson['geometry']
        properties = geojson.get('properties', {})
    elif geojson['type'] == 'Polygon':
        print("✅ Đã là Polygon, không cần chuyển")
        return
    elif geojson['type'] == 'MultiPolygon':
        geom = {'type': 'MultiPolygon', 'coordinates': geojson['coordinates']}
        properties = {}
    else:
        print(f"❌ Không hỗ trợ: {geojson['type']}")
        return
    
    print(f"   Geometry type: {geom['type']}")
    
    if geom['type'] == 'MultiPolygon':
        # MultiPolygon: [[[[lon,lat],...]]] 
        # → Lấy outer ring của polygon đầu tiên
        multipolygon_coords = geom['coordinates']
        print(f"   Số polygons: {len(multipolygon_coords)}")
        
        # Lấy polygon đầu tiên (có thể có holes)
        first_polygon = multipolygon_coords[0]
        print(f"   Polygon 1 có {len(first_polygon)} ring(s)")
        
        # Lấy outer ring (ring 0)
        outer_ring = first_polygon[0]
        print(f"   Outer ring: {len(outer_ring)} điểm")
        
        # Đảm bảo đóng vòng
        if outer_ring[0] != outer_ring[-1]:
            outer_ring.append(outer_ring[0])
            print("   Đã đóng vòng")
        
        # Tạo simple Polygon
        simple = {
            "type": "Polygon",
            "coordinates": [outer_ring]  # Chỉ outer ring, không holes
        }
        
    elif geom['type'] == 'Polygon':
        simple = geom
        # Đảm bảo đóng vòng
        for ring in simple['coordinates']:
            if ring[0] != ring[-1]:
                ring.append(ring[0])
    else:
        print(f"❌ Không hỗ trợ geometry: {geom['type']}")
        return
    
    # Backup và lưu
    backup = GEOJSON_PATH.with_suffix('.multipolygon.geojson')
    shutil.copy2(GEOJSON_PATH, backup)
    
    with open(GEOJSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(simple, f, indent=2)
    
    print(f"✅ Đã chuyển đổi:")
    print(f"   Backup: {backup}")
    print(f"   Type mới: {simple['type']}")
    print(f"   Rings: {len(simple['coordinates'])}")
    print(f"   Điểm ring 1: {len(simple['coordinates'][0])}")
    print(f"   Đóng vòng: {simple['coordinates'][0][0] == simple['coordinates'][0][-1]}")
    
    # Lưu cả version có properties
    feature_version = {
        "type": "Feature",
        "properties": properties,
        "geometry": simple
    }
    feature_path = Path("config/TinhTuc4326_200m.feature.geojson")
    with open(feature_path, 'w', encoding='utf-8') as f:
        json.dump(feature_version, f, indent=2)
    print(f"   Feature version: {feature_path}")

if __name__ == '__main__':
    convert_to_simple_polygon()
