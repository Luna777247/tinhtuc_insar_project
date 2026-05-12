/**
 * GEE Script: Phân tích chuyên sâu với Orbit 55 (ASCENDING) - Primary Orbit
 * ==============================================================================
 * 
 * Orbit 55 là quỹ đạo phổ biến nhất tại Tĩnh Túc (544 ảnh, 48% tổng số).
 * Script này tập trung hoàn toàn vào Orbit 55 để có time-series đồng nhất,
 * giảm nhiễu do geometry khác nhau giữa các orbit.
 * 
 * Ưu điểm Orbit 55:
 * - Số lượng ảnh nhiều nhất (544 ảnh, 2015-2026)
 * - Hướng ASCENDING ổn định
 * - Revisit ~12 ngày (chỉ S1A)
 * - Góc nhìn phù hợp địa hình miền núi Tĩnh Túc
 */

// ============================================================
// 1. CẤU HÌNH PRIMARY ORBIT
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(ROI, 13);

// Primary Orbit Configuration
var CONFIG = {
  primaryOrbit: 55,
  orbitPass: 'ASCENDING',
  description: 'Primary Orbit - Best coverage for TinhTuc',
  totalImages: 544,  // Thực tế từ CSV
  coverage: '48% of all S1 data'
};

// Thời gian phân tích toàn thời kỳ
var START_DATE = '2015-02-20';  // Ngày ảnh đầu tiên Orbit 55
var END_DATE = '2026-04-26';    // Ngày ảnh mới nhất

print('=== PRIMARY ORBIT 55 (ASCENDING) ANALYSIS ===');
print('Orbit:', CONFIG.primaryOrbit);
print('Pass:', CONFIG.orbitPass);
print('Period:', START_DATE, '→', END_DATE);
print('Expected images:', CONFIG.totalImages);

// ============================================================
// 2. LOAD DỮ LIỆU CHỈ ORBIT 55
// ============================================================

var s1Orbit55 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', CONFIG.primaryOrbit))  // Chỉ Orbit 55!
  .filter(ee.Filter.eq('orbitProperties_pass', CONFIG.orbitPass))          // Chỉ ASCENDING!
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .select(['VV', 'VH', 'angle']);

print('Actual images in collection:', s1Orbit55.size());

// Kiểm tra phân bố theo năm
var yearlyCount = s1Orbit55.map(function(img) {
  return img.set('year', img.date().get('year'));
}).aggregate_histogram('year');
print('Images per year:', yearlyCount);

// ============================================================
// 3. TIME-SERIES ANALYSIS (Chỉ Orbit 55)
// ============================================================

/**
 * Tính median backscatter theo tháng cho Orbit 55.
 * Đảm bảo chỉ dùng cùng orbit để tránh nhiễu geometry.
 */
var createMonthlyComposite = function(year, month) {
  var start = ee.Date.fromYMD(year, month, 1);
  var end = start.advance(1, 'month');
  
  var monthly = s1Orbit55
    .filterDate(start, end)
    .median()
    .set('year', year)
    .set('month', month)
    .set('date', start.format('YYYY-MM'));
  
  return monthly;
};

// Tạo time-series cho 2024-2025
var months2024 = ee.List.sequence(1, 12).map(function(m) {
  return createMonthlyComposite(2024, m);
});
var months2025 = ee.List.sequence(1, 12).map(function(m) {
  return createMonthlyComposite(2025, m);
});

var timeSeries2024 = ee.ImageCollection.fromImages(months2024);
var timeSeries2025 = ee.ImageCollection.fromImages(months2025);

// ============================================================
// 4. CHANGE DETECTION VỚI CÙNG ORBIT
// ============================================================

// Lấy baseline và post-event từ cùng Orbit 55
var baseline55 = s1Orbit55
  .filterDate('2025-09-15', '2025-09-20')
  .median();

var postEvent55 = s1Orbit55
  .filterDate('2025-09-28', '2025-09-30')
  .median();

// Change detection (cùng orbit nên đáng tin cậy hơn)
var diff55 = postEvent55.select('VV').subtract(baseline55.select('VV')).rename('VV_diff');

// Ngưỡng adaptive (μ - 1.5σ)
var stats55 = diff55.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

var mu55 = ee.Number(stats55.get('VV_diff_mean'));
var sigma55 = ee.Number(stats55.get('VV_diff_stdDev'));
var threshold55 = mu55.subtract(sigma55.multiply(1.5));

print('\n=== CHANGE DETECTION (Same Orbit 55) ===');
print('Mean diff:', mu55);
print('StdDev:', sigma55);
print('Threshold (μ - 1.5σ):', threshold55);

// ============================================================
// 5. SUBSIDENCE PROXY ANALYSIS (Orbit 55 only)
// ============================================================

/**
 * Phân tích xu hướng dài hạn với chỉ Orbit 55.
 * Tính trend VH/VV theo thời gian.
 */
var calculateTrend = function(band) {
  // Stack tất cả ảnh Orbit 55
  var stacked = s1Orbit55.select(band).toArray();
  
  // Tính linear trend (đơn giản hóa)
  var mean = stacked.arrayReduce(ee.Reducer.mean(), [0]);
  var variance = stacked.arrayReduce(ee.Reducer.variance(), [0]);
  
  return ee.Image.cat(mean, variance).rename([band + '_mean', band + '_variance']);
};

// Tính trend cho VV và VH
var trendVV = calculateTrend('VV');
var trendVH = calculateTrend('VH');

// Phát hiện vùng biến động mạnh (high variance = potential subsidence)
var stabilityIndex = trendVV.select('VV_variance').multiply(-1).add(1)
  .rename('stability_index');

// ============================================================
// 6. HIỂN THỊ BẢN ĐỒ
// ============================================================

// Time-series sample (tháng 9/2024 vs 9/2025)
var sep2024 = timeSeries2024.filter(ee.Filter.eq('month', 9)).first();
var sep2025 = timeSeries2025.filter(ee.Filter.eq('month', 9)).first();

Map.addLayer(baseline55.select('VV'), {min: -20, max: 0, palette: ['black', 'white']}, 
  'Orbit 55: Baseline (15-20/09/2025)');
Map.addLayer(postEvent55.select('VV'), {min: -20, max: 0, palette: ['black', 'white']}, 
  'Orbit 55: Post-Event (28-30/09/2025)');

// Change map
Map.addLayer(diff55, {min: -10, max: 5, palette: ['blue', 'white', 'red']}, 
  'Orbit 55: VV Difference');

// Flood detection (cùng orbit - đáng tin cậy hơn)
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem);

var flood55 = diff55.lt(threshold55)
  .and(slope.lt(5))
  .selfMask();

Map.addLayer(flood55, {palette: ['#185FA5'], opacity: 0.7}, 
  '🌊 Flood - Orbit 55 Only (Reliable)');

// Stability map
Map.addLayer(stabilityIndex, {min: 0, max: 1, palette: ['red', 'yellow', 'green']}, 
  '📊 Stability Index (Orbit 55 trend)');

// ============================================================
// 7. THỐNG KÊ SO SÁNH: ORBIT 55 VS ALL ORBITS
// ============================================================

print('\n=== SO SÁNH ĐỘ TIN CẬY ===');

// Đếm số ảnh trước và sau sự kiện cho Orbit 55
var preCount55 = s1Orbit55.filterDate('2025-09-15', '2025-09-20').size();
var postCount55 = s1Orbit55.filterDate('2025-09-28', '2025-09-30').size();

print('Orbit 55 - Pre-event images:', preCount55);
print('Orbit 55 - Post-event images:', postCount55);

// So sánh với tất cả orbits
var s1All = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(ROI)
  .filterDate('2025-09-15', '2025-09-30')
  .filter(ee.Filter.eq('instrumentMode', 'IW'));

var preCountAll = s1All.filterDate('2025-09-15', '2025-09-20').size();
var postCountAll = s1All.filterDate('2025-09-28', '2025-09-30').size();

print('All Orbits - Pre-event images:', preCountAll);
print('All Orbits - Post-event images:', postCountAll);

print('\n✅ Orbit 55 đảm bảo cùng geometry → change detection đáng tin cậy hơn!');
print('⚠️  Mixing orbits có thể tạo false changes do góc nhìn khác nhau');

// ============================================================
// 8. EXPORT KẾT QUẢ
// ============================================================

// Export flood map (Orbit 55 only - đáng tin cậy nhất)
Export.image.toCloudStorage({
  image: flood55,
  description: 'Flood_Orbit55_ONLY_Reliable_' + START_DATE + '_to_' + END_DATE,
  folder: 'TinhTuc_Orbit55_Primary',
  region: ROI,
  scale: 10,
  crs: 'EPSG:32648',
  maxPixels: 1e9
});

// Export stability index
Export.image.toCloudStorage({
  image: stabilityIndex,
  description: 'StabilityIndex_Orbit55_' + START_DATE + '_to_' + END_DATE,
  folder: 'TinhTuc_Orbit55_Primary',
  region: ROI,
  scale: 30,
  crs: 'EPSG:32648',
  maxPixels: 1e9
});

// Export time-series metadata
var metadata = s1Orbit55.map(function(img) {
  return ee.Feature(null, {
    'id': img.id(),
    'date': img.date().format('YYYY-MM-dd HH:mm:ss'),
    'orbit': img.get('relativeOrbitNumber_start'),
    'pass': img.get('orbitProperties_pass'),
    'platform': img.get('platform_number')
  });
});

Export.table.toCloudStorage({
  collection: metadata,
  description: 'Orbit55_Metadata_' + START_DATE + '_to_' + END_DATE,
  folder: 'TinhTuc_Orbit55_Primary',
  fileFormat: 'CSV'
});

print('\n✅ Exports created:');
print('   1. Flood map (Orbit 55 only)');
print('   2. Stability index (long-term trend)');
print('   3. Metadata CSV (all Orbit 55 images)');
print('\n📊 Tóm tắt:');
print('   - Chỉ sử dụng Orbit 55 ASCENDING');
print('   - Đảm bảo consistency trong change detection');
print('   - Time-series dài nhất (544 ảnh)');
print('   - Phù hợp cho phân tích subsidence proxy');
