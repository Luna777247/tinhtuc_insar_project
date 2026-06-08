/**
 * export_harmonic_baseline.js
 * ===========================
 * Script chạy trên Google Earth Engine (Code Editor)
 * Mục tiêu: Tính toán Đường cơ sở (Harmonic Baseline) cho thuật toán Z-Score ngập lụt.
 * 
 * BẢN CẢI TIẾN: 
 * 1. Khắc phục Seasonal Bias: Chỉ tính Baseline cho ĐÚNG THÁNG xảy ra sự kiện (VD: Tháng 9)
 * 2. Hỗ trợ Phân cực Kép: Xuất cả VV (cho Flooded Veg) và VH (cho Open Water)
 */

// 1. Định nghĩa khu vực nghiên cứu (AOI Tĩnh Túc)
var roi = ee.Geometry.Rectangle([105.85, 22.65, 105.95, 22.75]);
Map.centerObject(roi, 13);
Map.addLayer(roi, {color: 'red'}, 'Tĩnh Túc AOI', false);

// 2. Tham số thời gian và quỹ đạo
var TARGET_MONTH = 9; // <--- CẬP NHẬT: Chọn tháng xảy ra sự kiện lũ lụt (VD: Tháng 9)
var START_YEAR = 2021;
var END_YEAR = 2025;
var RELATIVE_ORBIT = 55; // Quỹ đạo chính (ASCENDING)

// 3. Tải bộ sưu tập Sentinel-1 GRD
var s1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(roi)
  .filter(ee.Filter.calendarRange(START_YEAR, END_YEAR, 'year'))
  .filter(ee.Filter.calendarRange(TARGET_MONTH, TARGET_MONTH, 'month')) // Chỉ lấy ảnh của tháng này
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', RELATIVE_ORBIT));

print('Số lượng ảnh lịch sử của Tháng ' + TARGET_MONTH + ' tìm thấy:', s1.size());

// 4. Lọc nhiễu Speckle cho cả 2 phân cực
var smoothed_collection = s1.select(['VH', 'VV']).map(function(image) {
  var smoothed = image.focal_median(30, 'circle', 'meters');
  return smoothed.copyProperties(image, image.propertyNames());
});

// 5. Tính toán Baseline (Mean và Standard Deviation) cho VH và VV
var mean_img = smoothed_collection.reduce(ee.Reducer.mean()).rename(['mean_vh', 'mean_vv']);
var std_img = smoothed_collection.reduce(ee.Reducer.stdDev()).rename(['std_vh', 'std_vv']);

// Gộp thành 1 ảnh có 4 băng tần (mean_vh, mean_vv, std_vh, std_vv)
var harmonic_baseline = ee.Image.cat([mean_img, std_img]).clip(roi);

// 6. Hiển thị thử lên bản đồ 
Map.addLayer(harmonic_baseline.select('mean_vh'), {min: -25, max: -5}, 'Mean VH (Tháng ' + TARGET_MONTH + ')', false);
Map.addLayer(harmonic_baseline.select('mean_vv'), {min: -15, max: 0}, 'Mean VV (Tháng ' + TARGET_MONTH + ')');

// 7. Lệnh Xuất kết quả ra Google Drive
Export.image.toDrive({
  image: harmonic_baseline,
  description: 'TinhTuc_S1_Harmonic_Baseline_Month' + TARGET_MONTH + '_Orbit55',
  folder: 'InSAR_TinhTuc_Exports', 
  fileNamePrefix: 'harmonic_baseline_orbit55_m' + TARGET_MONTH + '_vh_vv',
  region: roi,
  scale: 10, // Độ phân giải 10m của Sentinel-1
  crs: 'EPSG:32648', // Hệ tọa độ UTM 48N cho Cao Bằng
  maxPixels: 1e9,
  fileFormat: 'GeoTIFF'
});

print('Vui lòng qua tab Tasks để bấm nút RUN và tải file GeoTIFF về máy.');
