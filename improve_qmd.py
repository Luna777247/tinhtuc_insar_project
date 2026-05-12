"""
Cải thiện QGIS Metadata (.qmd) cho TinhTuc4326_200m
=================================================

Chạy: python improve_qmd.py
"""

import json
from pathlib import Path
from datetime import datetime

QMD_PATH = Path("config/TinhTuc4326_200m.qmd")
GEOJSON_PATH = Path("config/TinhTuc4326_200m.geojson")

def improve_qmd():
    print(f"🔧 Cải thiện QMD: {QMD_PATH}")
    
    if not GEOJSON_PATH.exists():
        print(f"❌ Không tìm thấy GeoJSON để tham khảo")
        return
    
    # Đọc GeoJSON để lấy thông tin
    with open(GEOJSON_PATH, 'r', encoding='utf-8') as f:
        geojson = json.load(f)
    
    # Lấy properties từ feature
    feature = geojson.get('features', [{}])[0]
    properties = feature.get('properties', {})
    
    # Tạo QMD mới với thông tin đầy đủ
    qmd_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.10-Prizren">
  <identifier>TinhTuc4326_200m</identifier>
  <parentidentifier></parentidentifier>
  <language>vi</language>
  <type>dataset</type>
  <title>Khu vực nghiên cứu Tĩnh Túc, Cao Bằng</title>
  <abstract>
    ROI (Region of Interest) cho dự án InSAR phân tích ngập lụt, 
    sạt lở và sụt lún tại thị trấn Tĩnh Túc, tỉnh Cao Bằng.
    Phạm vi: 200m buffer xung quanh khu vực trung tâm.
    CRS: WGS84 (EPSG:4326)
  </abstract>
  <links>
    <link name="Dự án" url="https://github.com/tinhtuc-insar"/>
  </links>
  <dates>
    <date type="Created" value="{datetime.now().strftime('%Y-%m-%d')}" />
  </dates>
  <fees>Free for research use</fees>
  <encoding>UTF-8</encoding>
  <crs>
    <spatialrefsys nativeFormat="Wkt">
      <wkt>GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]]</wkt>
      <proj4>+proj=longlat +datum=WGS84 +no_defs</proj4>
      <srsid>3452</srsid>
      <srid>4326</srid>
      <authid>EPSG:4326</authid>
      <description>WGS 84</description>
      <projectionacronym>longlat</projectionacronym>
      <ellipsoidacronym>WGS84</ellipsoidacronym>
      <geographicflag>true</geographicflag>
    </spatialrefsys>
  </crs>
  <extent>
    <spatial minx="105.83" miny="22.67" maxx="105.95" maxy="22.70" crs="EPSG:4326"/>
  </extent>
  <metadata>
    <properties>
      <property name="tenTinh">{properties.get('tenTinh', 'Tỉnh Cao Bằng')}</property>
      <property name="maTinh">{properties.get('maTinh', '203')}</property>
      <property name="tenXa">{properties.get('tenXa', 'Xã Tĩnh Túc')}</property>
      <property name="maXa">{properties.get('maXa', '20313020')}</property>
      <property name="danSo">{properties.get('danSo', '585')}</property>
      <property name="dienTich">{properties.get('dienTich', '86.79')}</property>
      <property name="ghiChu">{properties.get('ghiChu', 'Thị trấn Tĩnh Túc')}</property>
    </properties>
  </metadata>
</qgis>'''
    
    # Lưu QMD
    with open(QMD_PATH, 'w', encoding='utf-8') as f:
        f.write(qmd_content)
    
    print(f"✅ Đã cải thiện QMD:")
    print(f"   - Thêm CRS: EPSG:4326")
    print(f"   - Thêm title và abstract")
    print(f"   - Thêm metadata từ GeoJSON")
    print(f"   - Thêm spatial extent")

if __name__ == '__main__':
    improve_qmd()
