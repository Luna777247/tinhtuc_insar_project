# BÁO CÁO PHÂN TÍCH DỮ LIỆU SAR (GEE) — KHU VỰC TĨNH TÚC

**Dự án:** InSAR Tĩnh Túc, Cao Bằng  
**Tài liệu:** Cẩm nang kỹ thuật Sentinel-1 SAR  
**Cập nhật:** 2026-05-11 (dữ liệu Tĩnh Túc đến 2026-04-26)  
**Nguồn tham khảo:** ESA, Google Earth Engine Data Catalog, GEE Community Tutorials, Sentinel Hub  
**Dữ liệu thực tế:** `S1_Metadata_TinhTuc_2014_to_Now.csv` (1,133 ảnh)

---

## Mục Lục

1. [Tổng Quan Sentinel-1](#1-tổng-quan-sentinel-1)
2. [Bản Chất SAR và Backscatter](#2-bản-chất-sar-và-backscatter)
3. [Hệ Thống Quỹ Đạo](#3-hệ-thống-quỹ-đạo)
4. [Vệ Tinh Sentinel-1A/B/C/D](#4-vệ-tinh-sentinel-1abcd)
5. [Tương Tác Sóng Radar](#5-tương-tác-sóng-radar)
   - 5.5 Preprocessing Pipeline
   - 5.6 Backscatter Coefficients
   - 5.7 ENL (Equivalent Number of Looks)
   - 5.8 Speckle Filtering (LEE)
6. [Truy Vấn Dữ Liệu GEE](#6-truy-vấn-dữ-liệu-gee)
7. [Xuất Metadata và Phân Tích](#7-xuất-metadata-và-phân-tích)
   - 7.3 Thống Kê Thực Tế Tĩnh Túc (2015-2026)
   - 7.3.5 **Orbit 55 ASC làm Primary**
8. [Giới Hạn GEE cho Subsidence](#8-giới-hạn-gee-cho-subsidence)
9. [Phát Hiện Ngập Lụt và Sạt Lở](#9-phát-hiện-ngập-lụt-và-sạt-lở)
   - 9.7 Change Detection nâng cao
10. [Workflow Đề Xuất](#10-workflow-đề-xuất)
11. [Định Dạng Dữ Liệu Tối Ưu Cho Flood và Landslide Detection](#11-định-dạng-dữ-liệu-tối-ưu-cho-flood-va-landslide-detection)

---

## 1. Tổng Quan Sentinel-1

### 1.1. Sentinel-1 là gì?

Sentinel-1 là chương trình **Synthetic Aperture Radar (SAR)** của Liên minh Châu Âu thuộc chương trình **Copernicus**, vận hành bởi **ESA (European Space Agency)**.

| Đặc điểm | Giá trị |
|----------|---------|
| **Băng tần** | C-band (~5.405 GHz) |
| **Bước sóng** | ~5.6 cm |
| **Loại sensor** | Active Radar (chủ động phát sóng) |
| **Phân cực** | VV, VH, HH, HV |
| **Chế độ** | Interferometric Wide (IW) - 250km swath |
| **Độ phân giải** | ~10m (ground range) |

### 1.2. Ưu Điểm so với Optical

| Optical | Sentinel-1 SAR |
|---------|----------------|
| Cần ánh sáng mặt trời | Hoạt động **24/7** (ngày/đêm) |
| Bị mây che | **Xuyên mây** (all-weather) |
| Bị khói bụi | Không phụ thuộc khí quyển |
| Đo phản xạ ánh sáng | Đo **backscatter radar** |

### 1.3. Dữ Liệu Level-1

ESA cung cấp 2 định dạng chính:

| Định dạng | Nội dung | Ứng dụng |
|-----------|----------|----------|
| **GRD** (Ground Range Detected) | Chỉ có amplitude/intensity | Flood, landcover, change detection |
| **SLC** (Single Look Complex) | Có **phase + amplitude** | InSAR, SBAS, deformation |

**QUAN TRỌNG:** GEE chỉ lưu **GRD**, không có **SLC** → không làm InSAR/SBAS được!

---

## 2. Bản Chất SAR và Backscatter

### 2.1. Backscatter Là Gì?

**Backscatter (σ° - sigma naught)** là cường độ năng lượng radar phản xạ ngược về cảm biến SAR sau khi sóng vi ba tương tác với bề mặt Trái Đất.

**Công thức:** σ° = (Radar Cross Section) / (đơn vị diện tích)

### 2.2. Các Yếu Tố Ảnh Hưởng Backscatter

| Yếu tố | Ảnh hưởng |
|--------|-----------|
| **Độ nhám (Roughness)** | Bề mặt gồ ghề → backscatter cao |
| **Độ ẩm (Moisture)** | Nước tăng dielectric constant → backscatter tăng |
| **Góc tới (Incidence Angle)** | Góc khác nhau → backscatter khác nhau |
| **Phân cực (Polarization)** | VV vs VH phản ứng khác nhau |
| **Hình học (Geometry)** | Slope, aspect ảnh hưởng mạnh |

### 2.3. Đặc Tính Bề Mặt Theo Backscatter

| Bề mặt | Backscatter | Đơn vị (dB) |
|--------|-------------|-------------|
| Nước phẳng | Rất thấp (specular reflection) | ~-25 dB |
| Đất khô | Trung bình | ~-15 dB |
| Rừng/vệ sinh | Cao (volume scattering) | ~-10 dB |
| Đô thị | Rất cao (double bounce) | ~0 dB |

### 2.4. VV vs VH - Phân Biệt Quan Trọng

| Polarization | Cơ chế | Ứng dụng tốt nhất |
|--------------|--------|-------------------|
| **VV** | Surface scattering | Ngập lụt (open water), đất trống |
| **VH** | Volume scattering | Sạt lở, rừng, thảm thực vật |

**Insight:** Flood detection nên dùng **VV**, Landslide detection nên dùng **VH**.

---

## 3. Hệ Thống Quỹ Đạo

### 3.1. Cấu Trúc Orbit Sentinel-1

Sentinel-1 bay quỹ đạo **polar** (cực → xích đạo → cực):

- **175 orbits** trong chu kỳ 12 ngày
- Mỗi orbit cách nhau ~23° kinh độ
- Thời gian bay Bắc→Nam: ~98 phút

### 3.2. ASCENDING vs DESCENDING

| Orbit | Hướng bay | Góc nhìn |
|-------|-----------|----------|
| **ASCENDING** | Nam → Bắc | Tây → Đông (roughly) |
| **DESCENDING** | Bắc → Nam | Đông → Tây (roughly) |

**Sentinel-1 là right-looking** → nhìn nghiêng sang phía phải quỹ đạo bay.

### 3.3. Relative Orbit Number

**Relative Orbit Number** (1-175) là ID quỹ đạo lặp lại trong chu kỳ 12 ngày.

```
Orbit 55 (S1A) ngày 01/06 và Orbit 55 (S1A) ngày 13/06
→ Có geometry gần như giống nhau (12 ngày sau)
```

**Tại sao quan trọng?**

Change detection **PHẢI** dùng cùng relative orbit để tránh sai lệch do geometry khác nhau.

### 3.4. Incidence Angle

Góc giữa radar beam và mặt đất phẳng:

- **Near range** (gần vệ tinh): ~30°
- **Far range** (xa vệ tinh): ~45°
- Sentinel-1 IW: 30°-45° range

Cùng một vật thể, incidence angle khác → backscatter khác!

### 3.5. Scene Slicing (25 giây)

Sentinel-1 cắt dữ liệu thành các **slice** 25 giây (~185km):

- **Slice 8 + Slice 9** cùng ngày, cùng orbit → cần **mosaic()** để ghép
- Đây là lý do đôi khi thấy 2 ảnh cùng ngày trong GEE.

---

## 4. Vệ Tinh Sentinel-1A/B/C/D

### 4.1. Constellation Sentinel-1

| Vệ tinh | Phóng | Trạng thái | Vai trò |
|---------|-------|------------|---------|
| **S1A** | 2014 | Hoạt động | Vệ tinh chính |
| **S1B** | 2016 | Lỗi 2021 | Tăng revisit (trước khi lỗi) |
| **S1C** | 2024 | Hoạt động | Thay thế S1B |
| **S1D** | 04/11/2025 | Hoạt động | Backup + tăng revisit |

### 4.2. Tác Động đến Revisit Time

| Cấu hình | Revisit | Ghi chú |
|----------|---------|---------|
| Chỉ S1A | ~12 ngày | Thời kỳ 2022-2024 |
| S1A + S1B (trước 2021) | ~6 ngày | Tối ưu cho flood |
| S1A + S1C (2024+) | ~6 ngày | Khôi phục sau lỗi S1B |
| S1A + S1C + S1D (2025+) | ~3-4 ngày | Tối ưu với 3 vệ tinh |

### 4.3. Khác Biệt Dữ Liệu A/B/C

Về nguyên tắc: **gần như đồng nhất**

- ESA cố gắng cross-calibration để đảm bảo consistency
- Khác biệt nhỏ do: calibration drift, aging hardware
- **Khác biệt này nhỏ hơn nhiều so với terrain/environment effect**

### 4.4. Lọc Theo Platform trong GEE

```javascript
// Chỉ lấy S1A
.filter(ee.Filter.eq('platform_number', 'A'))

// Chỉ lấy S1B (trước 2021)
.filter(ee.Filter.eq('platform_number', 'B'))

// Lấy S1C hoặc S1D (mới từ 2024-2025)
.filter(ee.Filter.eq('platform_number', 'C'))
.filter(ee.Filter.eq('platform_number', 'D'))
```

### 4.5. Sentinel-1D Đặc Biệt

**Phóng:** 04/11/2025 từ Kourou, French Guiana (Ariane 6)

**Kỷ lục "First Light":**

- First images: **06/11/2025** (Antarctic Peninsula, Tierra del Fuego, Thwaites Glacier)
- Bremen, Germany: **07/11/2025**
- Downlink: Matera, Italy
- **Thời gian từ launch đến first light: ~50 giờ** (kỷ lục cho radar satellite)

**Tính năng đặc biệt:**

- SAR instrument: 12m antenna
- **AIS (Automatic Identification System)**: phát hiện tàu và ô nhiễm biển
- Multi-polarisation imaging (VV/VH)

---

## 5. Tương Tác Sóng Radar

### 5.1. Sóng Microwave C-band

| Đặc tính | Giá trị |
|----------|---------|
| **Tần số** | ~5.405 GHz |
| **Bước sóng** | ~5.6 cm |
| **Loại** | Coherent microwave |

### 5.2. Coherent Nghĩa Là Gì?

Radar phát sóng có:

- **Wavelength xác định**
- **Phase xác định**

→ Cho phép đo:

- Amplitude (backscatter)
- **Phase** (cho InSAR)
- Interference

> Nhưng cũng gây: **Speckle noise** (salt-and-pepper)

### 5.3. Tương Tác Với Khí Quyển

| Hiệu ứng | Mức độ ảnh hưởng |
|----------|------------------|
| **Attenuation** (suy hao) | Nhỏ với C-band |
| **Delay** (trễ pha) | Quan trọng cho InSAR |
| **Scattering** (tán xạ) | Ít hơn optical |
| **Refraction** (khúc xạ) | Nhỏ |

> **Dense rain cells** (mưa cực mạnh) vẫn ảnh hưởng!

### 5.4. So Sánh với Optical

| Hiện tượng | Optical | SAR C-band |
|------------|---------|------------|
| Mây | Bị che hoàn toàn | Xuyên qua |
| Mưa | Ảnh hưởng nặng | Ít ảnh hưởng |
| Ban đêm | Không quan sát được | Hoạt động tốt |
| Khí quyển | Cần correction | Gần như không cần |

### 5.5. Preprocessing Pipeline trong GEE

Earth Engine xử lý S1 GRD theo pipeline của **Sentinel-1 Toolbox** (6 bước):

| Bước | Mô tả | Ghi chú |
|------|-------|---------|
| **1. Apply Orbit File** | Cập nhật metadata quỹ đạo | Dùng tệp quỹ đạo restored hoặc precise |
| **2. GRD Border Noise Removal** | Xóa nhiễu cường độ thấp ở cạnh cảnh | Từ 12/01/2018 |
| **3. Thermal Noise Removal** | Loại bỏ tạp âm nhiệt giữa các sub-swath | Không áp dụng cho ảnh trước 07/2015 |
| **4. Radiometric Calibration** | Tính σ° (backscatter coefficient) | Dùng tham số calibration trong metadata |
| **5. Terrain Correction** | Orthorectification dùng SRTM 30m hoặc ASTER DEM | Chuyển sang UTM projection |
| **6. Log Scaling** | Chuyển linear → dB (10*log10) | Chỉ cho S1_GRD (không cho S1_GRD_FLOAT) |

**Lưu ý:** Radiometric terrain correction (Gamma0 terrain) **không được áp dụng** do hiện tượng giả trên sườn núi.

### 5.6. Backscatter Coefficients (σ°)

| Hệ số | Tên đầy đủ | Ứng dụng |
|-------|------------|----------|
| **β° (Beta0)** | Radar brightness | Trước khi hiệu chỉnh địa hình |
| **σ° (Sigma0)** | Normalized radar cross-section | Mặt phẳng ellipsoid |
| **γ°_ellipsoid** | Gamma ellipsoid | GEE default, so sánh vùng bằng phẳng |
| **γ°_terrain** | Gamma terrain corrected | Yêu cầu orthorectification |

### 5.7. Equivalent Number of Looks (ENL)

**ENL là gì?** Số look tương đương, đo lường mức độ giảm speckle sau multi-look processing.

**Công thức:**

```
ENL = mean² / variance
```

| Chế độ | ENL | Giải thích |
|--------|-----|------------|
| **IW mode (GEE)** | **4.4** | ESA average over all swaths |
| Single-look | 1 | Nhiều speckle nhất |
| Multi-look (5 looks) | ~5 | Giảm speckle |

**Ý nghĩa:** ENL càng cao → speckle càng giảm, nhưng độ phân giải càng thấp.

### 5.8. Speckle Filtering (LEE Filter)

GEE hỗ trợ **LEE speckle filter** cho post-processing:

```javascript
// LEE filter với window 5x5
var leeFilter = function(image) {
  return image.focal_mean({kernel: ee.Kernel.square(5), iterations: 1});
};

var filtered = collection.map(leeFilter);
```

| Tham số | Giá trị | Ghi chú |
|---------|---------|---------|
| Window size | 1-7 (nên dùng lẻ) | Càng lớn càng mờ |
| Processing time | Tăng nhanh theo window | Khuyến nghị dùng ở native resolution |

---

## 6. Truy Vấn Dữ Liệu GEE

**Dataset:** `COPERNICUS/S1_GRD` - C-band SAR Ground Range Detected (log scaled, dB)  
**Dataset (Linear):** `COPERNICUS/S1_GRD_FLOAT` - Linear power values  
**Provider:** EU/ESA/Copernicus  
**Coverage GEE:** 2014-10-03 đến 2026-05-11  
**Coverage Tĩnh Túc (thực tế):** 2015-02-20 đến 2026-04-26 (1,133 ảnh)  
**Revisit:** 6 ngày (với constellation đầy đủ S1A+S1C+S1D)  
**Tags:** backscatter, copernicus, esa, sar, polarization, radar

**Lưu ý quan trọng về 2 collections:**

| Collection | Đơn vị | Giá trị | Dùng khi nào |
|------------|--------|---------|--------------|
| `S1_GRD` | dB | -50 đến 1 | Visualization, mức độ thay đổi |
| `S1_GRD_FLOAT` | Linear power | 0-0.5+ | Statistical analysis, change detection |

**Quy đổi:** `dB = 10 * log10(linear)`

### 6.1. Code GEE Cơ Bản cho Tĩnh Túc

```javascript
// 1. Define ROI (Tĩnh Túc - Cao Bằng)
var roi = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);

// 2. Time range: Tháng 6 - 12/2025
var startDate = '2025-06-01';
var endDate = '2025-12-31';

// 3. Load Sentinel-1 VV + VH
var S1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(roi)
  .filterDate(startDate, endDate)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));

// 4. Tách ASC / DESC
var asc = S1.filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'));
var desc = S1.filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'));

// 5. Đếm số ảnh
print('Total images:', S1.size());
print('Ascending:', asc.size());
print('Descending:', desc.size());

// 6. Hiển thị
Map.centerObject(roi, 10);
Map.addLayer(roi, {}, 'ROI');
```

### 6.2. Các Filter Quan Trọng

| Filter | Mục đích | Bắt buộc? |
|--------|----------|-----------|
| `filterBounds(roi)` | Giới hạn khu vực | ✅ Có |
| `filterDate()` | Thời gian | ✅ Có |
| `filter(eq('instrumentMode', 'IW'))` | Chế độ IW | ✅ Có |
| `filter(eq('relativeOrbitNumber_start', 55))` | Cùng orbit | ⚠️ Nên có |
| `filter(eq('orbitProperties_pass', 'ASCENDING'))` | Hướng bay | Tùy mục đích |
| `filter(eq('platform_number', 'A'))` | Chọn vệ tinh | Hiếm khi cần |

### 6.3. Các Hàm Xử Lý Thường Dùng

```javascript
// Chuyển sang dB (nếu cần)
var toDb = function(img) {
  return img.log10().multiply(10);
};

// Mosaic các slice
var mosaic = collection.mosaic();

// Mean composite
var mean = collection.mean();

// Median (tốt hơn cho SAR - giảm noise)
var median = collection.median();
```

### 6.4. Các Thuộc Tính Metadata Có Sẵn (GEE Data Catalog)

**Dataset ID:** `COPERNICUS/S1_GRD`  
**Phạm vi:** 2014-10-03 đến hiện tại  
**Revisit:** 6 ngày (với constellation đầy đủ)

#### Thuộc tính Quỹ đạo & Thời gian

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `orbitProperties_pass` | STRING | ASCENDING hoặc DESCENDING |
| `orbitNumber_start/stop` | DOUBLE | Số quỹ đạo tuyệt đối |
| `relativeOrbitNumber_start/stop` | DOUBLE | Số quỹ đạo tương đối (1-175) |
| `orbitProperties_ascendingNodeTime` | DOUBLE | Thời gian UTC tại nút ascending |
| `startTimeANX/stopTimeANX` | DOUBLE | Thời gian so với ascending node [ms] |
| `cycleNumber` | DOUBLE | Số thứ tự chu kỳ nhiệm vụ |
| `phaseIdentifier` | DOUBLE | Mã giai đoạn nhiệm vụ |

#### Thuộc tính Nền tảng & Thiết bị

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `platform_number` | STRING | A, B, C, D |
| `familyName` | STRING | "SENTINEL-1" |
| `nssdcIdentifier` | STRING | Mã nhiệm vụ duy nhất |
| `platformHeading` | DOUBLE | Hướng vệ tinh so với Bắc [độ] |
| `instrumentMode` | STRING | IW, SM, EW |
| `instrumentSwath` | STRING | Danh sách swath (thường 1, TOPS có 3-5) |
| `instrumentConfigurationID` | DOUBLE | Mã cấu hình radar |
| `missionDataTakeID` | DOUBLE | Mã duy nhất của lần thu dữ liệu |
| `transmitterReceiverPolarisation` | STRING_LIST | ['VV'], ['VH'], ['VV', 'VH'], etc. |

#### Thuộc tính Sản phẩm & Xử lý

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `productType` | STRING | Loại sản phẩm, cấp hiệu chỉnh |
| `productClass` | STRING | "A" (Annotation) hoặc "S" (Standard) |
| `productComposition` | STRING | Individual, Slice, Assembled |
| `productTimelinessCategory` | STRING | NRT-10m, NRT-1h, NRT-3h, Fast-24h, Off-line, Reprocessing |
| `sliceProductFlag` | STRING | true/false - có phải slice không |
| `sliceNumber` | DOUBLE | Số thứ tự slice (nếu là slice) |
| `totalSlices` | DOUBLE | Tổng số slice (nếu là slice) |
| `segmentStartTime` | DOUBLE | Thời gian bắt đầu segment chứa slice |
| `resolution` | STRING | H (High) hoặc M (Medium) |
| `resolution_meters` | DOUBLE | Độ phân giải [m] |

#### Thuộc tính Xử lý & Hiệu chuẩn

| Thuộc tính | Kiểu | Mô tả |
|------------|------|-------|
| `SLC_Processing_*` | various | Thông tin xử lý SLC (facility, software, version, start/stop time) |
| `GRD_Post_Processing_*` | various | Thông tin xử lý GRD |
| `S1TBX_*_version` | STRING | Phiên bản Sentinel-1 Toolbox |
| `SNAP_Graph_Processing_Framework_GPF_version` | STRING | Phiên bản SNAP GPF |

---

## 7. Xuất Metadata và Phân Tích

### 7.1. Code Xuất CSV Metadata

```javascript
// Convert ImageCollection → FeatureCollection (metadata table)
var table = S1.map(function(img) {
  var centroid = img.geometry().centroid().coordinates();
  var props = img.propertyNames();
  
  return ee.Feature(null, {
    // Basic
    id: img.id(),
    date: img.date().format('YYYY-MM-dd HH:mm:ss'),
    timestamp: img.date().millis(),
    
    // Orbit (đầy đủ)
    orbit_pass: img.get('orbitProperties_pass'),
    relative_orbit_start: img.get('relativeOrbitNumber_start'),
    relative_orbit_stop: img.get('relativeOrbitNumber_stop'),
    orbit_number_start: img.get('orbitNumber_start'),
    orbit_number_stop: img.get('orbitNumber_stop'),
    ascending_node_time: img.get('orbitProperties_ascendingNodeTime'),
    cycle_number: img.get('cycleNumber'),
    
    // Platform & Mission
    family_name: img.get('familyName'),
    platform: img.get('platform_number'),
    platform_heading: img.get('platformHeading'),
    nssdc_id: img.get('nssdcIdentifier'),
    mission_data_take_id: img.get('missionDataTakeID'),
    
    // Instrument
    instrument_mode: img.get('instrumentMode'),
    instrument_swath: img.get('instrumentSwath'),
    instrument_config_id: img.get('instrumentConfigurationID'),
    resolution_meters: img.get('resolution_meters'),
    resolution_category: img.get('resolution'),
    
    // Polarization
    polarization: img.get('transmitterReceiverPolarisation'),
    
    // Product Info
    product_type: img.get('productType'),
    product_class: img.get('productClass'),
    product_composition: img.get('productComposition'),
    timeliness: img.get('productTimelinessCategory'),
    
    // Slice Info (nếu có)
    is_slice: img.get('sliceProductFlag'),
    slice_number: img.get('sliceNumber'),
    total_slices: img.get('totalSlices'),
    segment_start_time: img.get('segmentStartTime'),
    
    // Processing Info
    s1tbx_sar_version: img.get('S1TBX_SAR_Processing_version'),
    snap_gpf_version: img.get('SNAP_Graph_Processing_Framework_GPF_version'),
    grd_processing_start: img.get('GRD_Post_Processing_start'),
    
    // Location
    lon: centroid.get(0),
    lat: centroid.get(1)
  });
});

// Export CSV
Export.table.toDrive({
  collection: table,
  description: 'Sentinel1_Metadata_TinhTuc_2025_06_12',
  fileFormat: 'CSV'
});

// Hoặc xuất ra Console để xem trước
print('Sample metadata:', table.first());
```

### 7.2. Kết Quả CSV

| Cột | Ý nghĩa | Ví dụ |
|-----|---------|-------|
| `id` | ID ảnh | S1A_IW_GRDH_1SDV_20250812T105825 |
| `date` | Thời gian chụp | 2025-08-12 10:58:25 |
| `orbit_pass` | ASC/DESC | ASCENDING |
| `relative_orbit_start` | Quỹ đạo tương đối (start) | 55 |
| `relative_orbit_stop` | Quỹ đạo tương đối (stop) | 55 |
| `orbit_number_start` | Số quỹ đạo tuyệt đối | 52341 |
| `cycle_number` | Chu kỳ nhiệm vụ | 321 |
| `platform` | Vệ tinh A/B/C/D | A |
| `platform_heading` | Hướng vệ tinh [độ] | 192.5 |
| `instrument_mode` | Chế độ IW/SM/EW | IW |
| `instrument_swath` | Swath (IW = 3 sub-swaths) | IW1,IW2,IW3 |
| `resolution_meters` | Độ phân giải [m] | 10 |
| `polarization` | Phân cực | ["VV", "VH"] |
| `product_type` | Loại sản phẩm | GRD |
| `product_composition` | Individual/Slice/Assembled | Slice |
| `is_slice` | Có phải slice không | true |
| `slice_number` | Số thứ tự slice | 12 |
| `total_slices` | Tổng số slice | 25 |
| `timeliness` | NRT/Fast/Off-line | NRT-10m |
| `lon`, `lat` | Tọa độ centroid | 105.88, 22.69 |

### 7.3. Thống Kê Thực Tế - Dữ Liệu Tĩnh Túc (2015-2026)

Dữ liệu từ file `S1_Metadata_TinhTuc_2014_to_Now.csv` (xuất từ GEE):

#### 7.3.1. Tổng Quan

| Chỉ số | Giá trị |
|--------|---------|
| **Tổng số ảnh** | 1,133 |
| **Thời gian** | 2015-02-20 → 2026-04-26 |
| **Vệ tinh S1A** | 1,126 (99.4%) |
| **Vệ tinh S1B** | 4 (0.35%) |
| **Vệ tinh S1C** | 3 (0.26%) |
| **Chế độ IW** | 100% |
| **Phân cực VV+VH** | 100% |
| **Độ phân giải** | 10m (100%) |

#### 7.3.2. Phân Bố Quỹ Đạo

| Orbit | Số ảnh | Tỷ lệ | Hướng | Đặc điểm |
|-------|--------|-------|-------|----------|
| **55** | 544 | 48.0% | ASCENDING | Quỹ đạo chính |
| **91** | 320 | 28.2% | DESCENDING | Quỹ đạo phụ |
| **128** | 269 | 23.7% | ASCENDING | Quỹ đạo ít phổ biến |
| **Tổng ASC** | 813 | 71.7% | - | - |
| **Tổng DESC** | 320 | 28.2% | - | - |

#### 7.3.3. Phân Bố Theo Năm (ảnh/năm)

| Năm | Số ảnh | Ghi chú |
|-----|--------|---------|
| 2015 | 22 | Khởi đầu (chỉ S1A) |
| 2016 | 54 | Tăng dần |
| 2017 | 107 | Ổn định |
| 2018 | 119 | - |
| 2019 | 121 | - |
| 2020 | 123 | - |
| 2021 | 119 | S1B lỗi 12/2021 |
| 2022 | 114 | Chỉ S1A |
| 2023 | 105 | - |
| 2024 | 111 | S1C phóng |
| 2025 | 108 | - |
| 2026 | 30 | Đến 04/2026 |

**Trung bình:** ~100-120 ảnh/năm (~9-10 ảnh/tháng với 3 orbits)

#### 7.3.4. Kết Luận từ Dữ Liệu Thực Tế

1. **S1A thống trị:** 99.4% dữ liệu là từ S1A
2. **S1B rất ít:** Chỉ 4 ảnh (thời kỳ ngắn trước khi lỗi 12/2021)
3. **S1C mới:** Chỉ 3 ảnh gần đây (phóng 2024)
4. **Orbit 55 phổ biến nhất:** 48% tổng số ảnh
5. **ASCENDING nhiều hơn:** Gấp 2.5 lần DESCENDING
6. **Revisit thực tế:** ~12 ngày cho cùng orbit (chỉ S1A)

#### 7.3.5. Lựa Chọn Orbit 55 ASCENDING Làm Dữ Liệu Phân Tích Chính

Dựa trên phân tích dữ liệu thực tế, **Orbit 55 (ASCENDING)** được chọn làm quỹ đạo phân tích chính cho dự án Tĩnh Túc:

| Lý do | Giải thích | Lợi ích |
|-------|------------|---------|
| **Số lượng ảnh nhiều nhất** | 544 ảnh (48% tổng số) | Time-series dài, phân tích trend chính xác |
| **Hướng ASCENDING** | Cùng hướng bay, góc nhìn ổn định | Giảm nhiễu do geometry khác nhau |
| **Revisit ~12 ngày** | Chu kỳ ổn định với S1A | Đủ để phát hiện thay đổi, không quá thưa |
| **Phù hợp địa hình** | Góc nhìn từ hướng Bắc-Nam | Tốt cho miền núi Tĩnh Túc |
| **Dễ so sánh** | Cùng orbit giữa các lần chụp | Change detection đáng tin cậy |

**Cấu hình khuyến nghị cho GEE:**

```javascript
// Primary orbit: 55 (ASCENDING)
var PRIMARY_ORBIT = 55;
var PRIMARY_PASS = 'ASCENDING';

var s1Collection = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', PRIMARY_ORBIT))  // Chỉ Orbit 55
  .filter(ee.Filter.eq('orbitProperties_pass', PRIMARY_PASS))         // Chỉ ASCENDING
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));
```

**Khi nào dùng Orbit 91 hoặc 128?**

- **Orbit 91 (DESC):** Khi cần cross-validation hoặc phân tích sự kiện ngắn (có 320 ảnh)
- **Orbit 128 (ASC):** Khi cần bổ sung dữ liệu, nhưng ít ảnh hơn (269 ảnh)

> **Quy tắc vàng:** Luôn dùng cùng một orbit cho change detection để tránh nhiễu do geometry khác nhau!

### 7.4. Thống Kê Diện Tích

```javascript
// Tính diện tích flood
var floodArea = floodMask.multiply(ee.Image.pixelArea())
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: roi,
    scale: 10,
    maxPixels: 1e9
  });

print('Flood area (m2):', floodArea);
print('Flood area (ha):', ee.Number(floodArea.get('constant')).divide(10000));
```

---

## 8. Giới Hạn GEE cho Subsidence

### 8.1. 3 Cấp Độ "Sụt Lún"

| Cấp | Phương pháp | Độ chính xác | GEE làm được? |
|-----|-------------|--------------|---------------|
| **1. Visual Change** | Backscatter trend | Qualitative | ✅ Có |
| **2. Relative Deformation** | Offset tracking | ~0.5m | ⚠️ Hạn chế |
| **3. True Subsidence** | InSAR/SBAS/PSI | 3-10 mm/năm | ❌ **KHÔNG** |

### 8.2. Vì Sao GEE Không Làm Được True Subsidence?

```
GEE có: COPERNICUS/S1_GRD_FLOAT
              ↓
        Chỉ có intensity (amplitude)
        Không có phase
        → Không tính được interferogram
        → Không đo được displacement mm

SBAS cần: S1 SLC (Single Look Complex)
              ↓
        Có cả amplitude + phase
        → Tính interferogram
        → Đo path length difference
        → Độ chính xác mm
```

### 8.3. Physics Của Phase

Radar Sentinel-1:

- **λ ~ 5.6 cm (C-band)**
- Phase cực kỳ nhạy:
  - Chỉ cần dịch chuyển **vài mm** → phase đã đổi
  - Cho phép đo **mm-level deformation**

> Nhưng GEE **không có phase** → không thể tính!

### 8.4. GEE Có Thể Làm Gì Cho Subsidence?

✅ **Có thể:**

- Phát hiện vùng biến động mạnh (hotspot detection)
- Theo dõi backscatter trend theo thời gian
- Phát hiện instability proxy
- Giám sát khu vực mỏ, đất yếu
- Change point detection

❌ **Không thể:**

- Dịch chuyển phase chính xác mm-level
- Tính interferogram
- Atmospheric correction đầy đủ
- SBAS, PSI, DInSAR chuẩn

### 8.5. Workflow Đúng Cho Tĩnh Túc

**Cấp 1-2 (GEE GRD):**

```
Sentinel-1 GRD → Backscatter trend → Hotspot screening
```

**Cấp 3 (External SBAS):**

```
Sentinel-1 SLC → SNAP/ISCE → Interferogram → SBAS → mm-level velocity
```

> "Google Earth Engine với Sentinel-1 GRD phù hợp cho **phát hiện vùng biến động** và **giám sát bất ổn bề mặt** quy mô lớn, nhưng **không hỗ trợ đo sụt lún chính xác** bằng các kỹ thuật interferometric do **thiếu dữ liệu phase SLC**."

> "Các biến động backscatter trong GEE chỉ phản ánh **thay đổi đặc tính tán xạ radar** của bề mặt, không trực tiếp biểu diễn **dịch chuyển hình học tuyệt đối** như trong SBAS/PSI InSAR."

---

## 9. Phát Hiện Ngập Lụt và Sạt Lở

### 9.1. Ngập Lụt - Cơ Chế Radar

**A. Open Water Flood (dễ detect)**

- Nước phẳng → specular reflection
- Radar phản xạ đi hướng khác
- Ít sóng quay lại → **backscatter thấp (tối)**

**B. Vegetated Flood (phức tạp)**

- Ngập dưới cây/rừng/lúa
- Radar phản xạ giữa thân cây + nước
- Tạo **double bounce** → backscatter có thể tăng!

### 9.2. Ngưỡng Phát Hiện Ngập Lụt

| Phương pháp | Ngưỡng | Ghi chú |
|-------------|--------|---------|
| **Global threshold** | -1.5 dB | Đơn giản |
| **Adaptive (μ - 1.5σ)** | Tự động | Tốt hơn |
| **Ratio (post/pre)** | < 0.5 | Chuẩn nhất |

```javascript
// Adaptive threshold
var stats = diff.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: roi, scale: 30, bestEffort: true
});
var mu = ee.Number(stats.get('diff_mean'));
var sigma = ee.Number(stats.get('diff_stdDev'));
var thresh = mu.subtract(sigma.multiply(1.5));
```

### 9.3. Sạt Lở - Cơ Chế Radar

Sạt lở làm thay đổi:

| Yếu tố | Hiệu ứng |
|--------|----------|
| **Roughness change** | Địa hình bị phá vỡ |
| **Moisture change** | Đất ẩm hơn sau sạt |
| **Vegetation removal** | Cây bị mất → VH giảm |
| **Geometry change** | Slope đổi → radar response đổi |

> **Sạt lở khó detect hơn flood** vì signature không ổn định!

### 9.4. Ngưỡng Phát Hiện Sạt Lở

```javascript
// Landslide detection
var landslide = diff.abs().gt(3.0)  // Thay đổi > 3 dB
  .and(slope.gt(20))               // Độ dốc > 20°
  .and(slope.lt(55));              // Độ dốc < 55°
```

### 9.5. Lọc Nhiễu (Bỏ Vùng Nước Thường Xuyên)

```javascript
// Loại vùng nước thường xuyên (JRC Global Surface Water)
var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence');
var floodFinal = floodMask.and(jrc.lt(80));  // < 80% occurrence
```

### 9.6. Giới Hạn Phương Pháp

| Giới hạn | Mô tả |
|----------|-------|
| **Độ phân giải** | 10m → không detect ngập nhỏ, sạt lở nhỏ |
| **Orbit geometry** | ASC vs DESC khác nhau → cần same orbit |
| **Terrain effect** | Miền núi Cao Bằng → shadow, layover |
| **Speckle noise** | Salt-and-pepper cần filter |
| **False positive** | Đất ẩm, shadow, đường phẳng dễ nhầm flood |

### 9.7. Phát Hiện Thay Đổi Nâng Cao (Change Detection)

Dựa trên GEE Community Tutorial về SAR change detection.

#### 9.7.1. S1_GRD_FLOAT cho Statistical Analysis

```javascript
// Dùng S1_GRD_FLOAT (linear power) cho change detection
var s1Float = ee.ImageCollection('COPERNICUS/S1_GRD_FLOAT')
  .filterBounds(roi)
  .filterDate('2020-06-01', '2020-10-01')
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .select('VV', 'VH');
```

#### 9.7.2. Gamma Distribution & Speckle Statistics

SAR multi-look intensity tuân theo **gamma distribution**:

```
p(x) = (1/β^α Γ(α)) * x^(α-1) * e^(-x/β)
```

| Tham số | Ý nghĩa |
|---------|---------|
| α (shape) | Số looks (ENL) |
| β (scale) | Mean/α |
| mean(x) | αβ |
| var(x) | αβ² |

#### 9.7.3. Change Detection Algorithms

**A. Ratio Test (2 images)**

```javascript
// Ratio of post-event to pre-event
var ratio = post.divide(pre);
var change = ratio.lt(0.5).or(ratio.gt(2.0));
```

**B. Statistical Test (Chi-square)**

```javascript
// Likelihood ratio test for change detection
var lrTest = function(img1, img2) {
  var mean1 = img1.reduceRegion(ee.Reducer.mean(), roi, 30);
  var mean2 = img2.reduceRegion(ee.Reducer.mean(), roi, 30);
  var var1 = img1.reduceRegion(ee.Reducer.variance(), roi, 30);
  var var2 = img2.reduceRegion(ee.Reducer.variance(), roi, 30);
  
  // Test statistic
  var n = 4.4; // ENL
  var lr = var1.divide(var2).log().multiply(n);
  return lr;
};
```

**C. Multi-temporal Change Detection**

```javascript
// Spring vs Summer vs Fall
var spring = s1Float.filterDate('2020-03-01', '2020-04-20').mean();
var lateSpring = s1Float.filterDate('2020-04-21', '2020-06-10').mean();
var summer = s1Float.filterDate('2020-06-11', '2020-08-31').mean();

// Concatenate for multi-temporal visualization
var seasonal = ee.Image.cat(spring, lateSpring, summer);
```

---

## 10. Workflow Đề Xuất

### 10.1. Tổng Quan Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                   SENTINEL-1 PIPELINE                      │
│                      Tĩnh Túc, Cao Bằng                    │
└─────────────────────────────────────────────────────────────┘

PHASE 1: DATA COLLECTION (GEE)
├── ROI: [105.85, 22.62, 106.05, 22.80]
├── Time: 2015-02-20 → 2026-04-26 (1,133 ảnh)
├── Platforms: S1A (99.4%), S1B (0.35%), S1C (0.26%)
├── **Primary Orbit: 55 (ASCENDING)** - 544 ảnh (48%)
├── Secondary: Orbit 91 (DESC) - 320 ảnh, Orbit 128 (ASC) - 269 ảnh
├── Filter: IW mode, VV+VH, **Orbit 55 ASC**
└── Export: Metadata CSV → `S1_Metadata_TinhTuc_2014_to_Now.csv`

PHASE 2: CHANGE DETECTION (GEE)
├── Pre-event: Same orbit baseline
├── Post-event: Same orbit event
├── Diff: Post - Pre
├── Threshold: Adaptive (μ - 1.5σ)
├── Mask: Slope < 5° (flood), 20-55° (landslide)
└── Export: Flood map, Landslide map (GeoTIFF)

PHASE 3: SUBSIDENCE PROXY (GEE)
├── Backscatter trend analysis
├── Temporal variance
├── Hotspot detection
└── Export: Stability index, Hotspot mask

PHASE 4: TRUE SUBSIDENCE (External)
├── Data: SLC from ASF/ESA
├── Tool: SNAP/ISCE + MintPy
├── Method: SBAS-InSAR
├── Accuracy: 3-10 mm/year
└── Output: Deformation velocity map

PHASE 5: VALIDATION
├── UAV field survey
├── GPS measurements
└── Cross-validation
```

### 10.2. Code Tổng Hợp Hoàn Chỉnh

```javascript
// =========================================================
// SENTINEL-1 COMPLETE WORKFLOW - Tĩnh Túc, Cao Bằng
// =========================================================

// 1. CONFIGURATION
var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
var START_DATE = '2025-06-01';
var END_DATE = '2025-12-31';
var ORBIT = 55;  // Hoặc 91, 128

// 2. LOAD SENTINEL-1
var S1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', ORBIT))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));

// 3. SPLIT ASC/DESC
var ASC = S1.filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'));
var DESC = S1.filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'));

// 4. MOSAIC FUNCTION (for multi-slice)
var mosaicByDate = function(collection, date) {
  var d = ee.Date(date);
  return collection
    .filterDate(d, d.advance(1, 'day'))
    .select('VV', 'VH')
    .mosaic()
    .clip(ROI);
};

// 5. PRE/POST EVENT IMAGES
var pre = mosaicByDate(ASC, '2025-07-07');
var post = mosaicByDate(ASC, '2025-08-12');

// 6. CHANGE DETECTION
var diffVV = post.select('VV').subtract(pre.select('VV')).rename('diffVV');
var diffVH = post.select('VH').subtract(pre.select('VH')).rename('diffVH');

// 7. DEM & SLOPE
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem);

// 8. ADAPTIVE THRESHOLD
var stats = diffVV.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI, scale: 30, bestEffort: true
});
var mu = ee.Number(stats.get('diffVV_mean'));
var sigma = ee.Number(stats.get('diffVV_stdDev'));
var thresh = mu.subtract(sigma.multiply(1.5));

// 9. FLOOD DETECTION (VV < threshold, slope < 5°)
var flood = diffVV.lt(thresh).and(slope.lt(5));

// 10. LANDSLIDE DETECTION (VH change > 3dB, slope 20-55°)
var landslide = diffVH.abs().gt(3.0)
  .and(slope.gt(20)).and(slope.lt(55));

// 11. REMOVE PERMANENT WATER
var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence');
flood = flood.and(jrc.lt(80));

// 12. STATISTICS
var floodArea = flood.multiply(ee.Image.pixelArea())
  .reduceRegion({reducer: ee.Reducer.sum(), geometry: ROI, scale: 10});
var landslideArea = landslide.multiply(ee.Image.pixelArea())
  .reduceRegion({reducer: ee.Reducer.sum(), geometry: ROI, scale: 10});

print('Flood area (ha):', ee.Number(floodArea.get('constant')).divide(10000));
print('Landslide area (ha):', ee.Number(landslideArea.get('constant')).divide(10000));

// 13. EXPORT METADATA TABLE
var table = S1.map(function(img) {
  return ee.Feature(null, {
    id: img.id(),
    date: img.date().format('YYYY-MM-dd HH:mm:ss'),
    orbit_pass: img.get('orbitProperties_pass'),
    relative_orbit: img.get('relativeOrbitNumber_start'),
    platform: img.get('platform_number'),
    polarization: img.get('transmitterReceiverPolarisation')
  });
});

Export.table.toDrive({
  collection: table,
  description: 'S1_Metadata_TinhTuc_2025',
  fileFormat: 'CSV'
});

// 14. EXPORT RASTER
Export.image.toDrive({
  image: flood.selfMask(),
  description: 'Flood_Map',
  region: ROI, scale: 10, maxPixels: 1e13
});

Export.image.toDrive({
  image: landslide.selfMask(),
  description: 'Landslide_Map',
  region: ROI, scale: 10, maxPixels: 1e13
});

// 15. VISUALIZATION
Map.centerObject(ROI, 12);
Map.addLayer(ROI, {}, 'ROI');
Map.addLayer(flood.selfMask(), {palette: ['blue']}, 'Flood');
Map.addLayer(landslide.selfMask(), {palette: ['red']}, 'Landslide');
Map.addLayer(diffVV, {min: -5, max: 5, palette: ['red', 'white', 'blue']}, 'Diff VV');
```

---

## 11. Định Dạng Dữ Liệu Tối Ưu Cho Flood và Landslide Detection

Với bài toán khoanh vùng:

- ngập lụt
- sạt lở
- instability
- Sentinel-1 + Google Earth Engine

thì:

```text id="fmt1"
không có 1 định dạng tốt nhất cho mọi mục đích
```

### 11.1. Thực tế nên lưu

#### nhiều định dạng cùng lúc

| Dữ liệu           | Format tốt        |
| ----------------- | ----------------- |
| Flood mask raster | GeoTIFF           |
| Landslide raster  | GeoTIFF           |
| Polygon kết quả   | GeoJSON/Shapefile |
| Metadata ảnh      | CSV               |
| Statistics        | CSV/JSON          |
| Time-series       | CSV/Parquet       |
| Visualization web | PNG/Tile          |

### 11.2. Quan trọng nhất

#### Raster hay Vector?

#### Flood/SAR bản chất là raster

Sentinel-1:

```text id="fmt2"
pixel-based measurement
```

Nên:

```text id="fmt3"
GeoTIFF là format gốc phù hợp nhất
```

### 11.3. Vì sao GeoTIFF tốt nhất cho flood map?

#### A. Giữ nguyên pixel

Ví dụ:

- 10m Sentinel-1
- giá trị mask
- backscatter

#### B. Có georeference

Lưu:

- projection
- CRS
- transform

#### C. GIS support cực mạnh

Mở được bằng:

- QGIS
- ArcGIS
- rasterio
- GDAL

#### D. Phù hợp ML

Dùng tiếp cho:

- segmentation
- CNN
- change detection

### 11.4. Flood mask nên lưu thế nào?

Ví dụ:

```text id="fmt4"
0 = non-flood
1 = flood
```

→ raster nhị phân.

#### Đây là chuẩn nhất

### 11.5. Landslide susceptibility cũng vậy

Do:

- slope
- SAR texture
- roughness

→ spatial continuous.

Nên:

```text id="fmt5"
raster phù hợp hơn vector
```

### 11.6. Khi nào cần vector?

Khi:

- báo cáo
- dashboard
- webGIS
- thống kê hành chính

Ví dụ:

```text id="fmt6"
polygon vùng ngập
```

### 11.7. Nhưng vector hóa flood có vấn đề

SAR:

```text id="fmt7"
rất noisy
```

→ polygon:

- răng cưa
- fragmented
- rất nhiều vertex

#### Đây là lý do

```text id="fmt8"
không nên coi vector là dữ liệu gốc
```

### 11.8. Workflow chuẩn

```text id="fmt9"
Raster = source of truth
Vector = reporting product
```

### 11.9. GeoJSON hay Shapefile?

#### GeoJSON

Ưu:

- hiện đại
- web-friendly
- dễ đọc

Nhược:

- file lớn
- chậm với polygon lớn

#### Shapefile

Ưu:

- legacy GIS support

Nhược:

- nhiều file
- giới hạn field name
- encoding khó chịu

### 11.10. Hiện nay nên ưu tiên

```text id="fmt10"
GeoPackage hoặc GeoJSON
```

### 11.11. CSV dùng cho gì?

CSV:

```text id="fmt11"
không lưu raster geometry tốt
```

Nó phù hợp:

- metadata
- statistics
- image catalog
- time-series

Ví dụ:

- orbit
- acquisition time
- flood area
- threshold

### 11.12. JSON dùng cho gì?

JSON tốt cho:

- config
- processing log
- API
- web dashboard

Ví dụ:

```json id="fmt12"
{
  "threshold": -3.7,
  "flood_area_m2": 123456
}
```

### 11.13. Nếu muốn scientific reproducibility

Nên lưu:

| Thành phần        | Format  |
| ----------------- | ------- |
| Raw SAR metadata  | CSV     |
| Processing config | JSON    |
| Final raster      | GeoTIFF |
| Final polygons    | GeoJSON |

### 11.14. Với dự án của bạn

Tĩnh Túc:

- nhiều địa hình
- SAR noisy
- landslide fragmented

Khuyến nghị:

#### A. Flood map

```text id="fmt13"
GeoTIFF uint8
```

#### B. Landslide hotspot

```text id="fmt14"
GeoTIFF float32
```

#### C. Reporting polygon

```text id="fmt15"
GeoJSON
```

#### D. Metadata

```text id="fmt16"
CSV
```

### 11.15. Tại sao GeoTIFF quan trọng nhất?

Vì:

```text id="fmt17"
mọi thứ cuối cùng đều quay về pixel
```

SAR:

```text id="fmt18"
không sinh ra polygon tự nhiên
```

### 11.16. Một sai lầm phổ biến

Nhiều người:

```text id="fmt19"
convert ngay sang shapefile
```

→ mất:

- precision
- raster continuity
- uncertainty

### 11.17. Với ML sau này

GeoTIFF:

```text id="fmt20"
gần như bắt buộc
```

CNN:

- đọc raster
- không đọc shapefile trực tiếp

### 11.18. Với webGIS

Nên:

- GeoJSON
- vector tiles
- COG GeoTIFF

### 11.19. Nếu dữ liệu lớn

Nên dùng:

```text id="fmt21"
Cloud Optimized GeoTIFF (COG)
```

Rất tốt cho:

- streaming
- web map
- cloud

### 11.20. Nếu cần lưu "uncertainty"

Có thể lưu:

- confidence raster
- probability raster

Ví dụ:

```text id="fmt22"
0–1 flood probability
```

### 11.21. Đây là lựa chọn chuyên nghiệp nhất

| Product                  | Format          |
| ------------------------ | --------------- |
| Backscatter              | GeoTIFF float32 |
| Flood mask               | GeoTIFF uint8   |
| Landslide susceptibility | GeoTIFF float32 |
| Polygon summary          | GeoJSON         |
| Metadata                 | CSV             |
| Config                   | JSON            |

### 11.22. Câu rất tốt cho báo cáo

```text id="fmt23"
GeoTIFF là định dạng phù hợp nhất để lưu kết quả flood và landslide detection từ Sentinel-1 do bảo toàn cấu trúc raster, thông tin không gian và giá trị pixel radar gốc.
```

### 11.23. Và câu chuyên sâu hơn

```text id="fmt24"
Các định dạng vector như GeoJSON/Shapefile chỉ nên được xem là sản phẩm dẫn xuất phục vụ trực quan hóa và thống kê, không nên thay thế raster SAR gốc trong phân tích khoa học.
```

---

## Tài Liệu Tham Khảo

1. **ESA Sentinel-1 User Guide**: <https://sentinel.esa.int/web/sentinel/user-guides/sentinel-1-sar>
2. **GEE SAR Basics Tutorial**: <https://developers.google.com/earth-engine/tutorials/community/sar-basics>
3. **SNAP Toolbox**: <https://step.esa.int/main/download/snap-download/>
4. **MintPy SBAS**: <https://github.com/insarlab/MintPy>
5. **ASF HyP3**: <https://hyp3-docs.asf.alaska.edu/>

---

## Tóm Tắt Quan Trọng

| Câu hỏi | Trả lời ngắn |
|---------|--------------|
| GEE có làm InSAR được không? | ❌ Không - chỉ có GRD, không có phase |
| Flood dùng VV hay VH? | ✅ VV (surface scattering) |
| Landslide dùng VV hay VH? | ✅ VH (volume scattering) |
| S1A và S1B khác nhau không? | ⚠️ Gần như giống, khác revisit |
| Cùng orbit quan trọng không? | ✅ Rất quan trọng cho change detection |
| GEE phù hợp gì? | ✅ Screening, hotspot, time-series |
| GEE không phù hợp gì? | ❌ mm-level subsidence, true InSAR |
