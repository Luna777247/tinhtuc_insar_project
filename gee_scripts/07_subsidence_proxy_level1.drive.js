/**
 * ============================================================================
 * GEE SCRIPT: SUBSIDENCE PROXY DETECTION (CẤP 1)
 * ============================================================================
 * 
 * Phát hiện sụt lún gián tiếp (proxy) qua backscatter trend analysis.
 * 
 * Cấp độ: Level 1 - Proxy Detection
 * Độ chính xác: qualitative (visual change, hotspot screening)
 * Dữ liệu: Sentinel-1 GRD (GEE)
 * 
 * PHÂN TÍCH:
 * - Long-term VH/VV trend (linear regression)
 * - Temporal variance analysis
 * - Stability index (0-1, cao = bất ổn)
 * - Hotspot detection
 * 
 * ⚠️ LƯU Ý: Đây là phân tích PROXY, KHÔNG phải đo sụt lún chính xác mm-level.
 * Để đo chính xác: Dùng Cấp 3 SBAS-InSAR với SLC data (ASF HyP3 + MintPy)
 * 
 * Reference: Phần 0.6 tài liệu Sentinel1_TinhTuc_PhanTich_KichBan_ChiTiet.md
 * ============================================================================
 */

// ============================================================
// 1. THAM SỐ CẤU HÌNH
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);

// Thời gian phân tích dài hạn
var START_DATE = "2020-01-01";
var END_DATE = "2025-12-31";

// Ngưỡng phát hiện
var STABILITY_THRESHOLD = 0.7;  // Chỉ số bất ổn (0-1)
var TREND_THRESHOLD = -2.0;     // dB/năm (VH giảm)
var VARIANCE_THRESHOLD = 5.0;   // Phương sai VH

// Sentinel-1 collection
var S1_COLLECTION = "COPERNICUS/S1_GRD_FLOAT";

// ============================================================
// 2. HÀM TIỆN ÍCH
// ============================================================

/**
 * Tạo mask mây và shadow cho Sentinel-2
 */
function maskS2clouds(image) {
  var qa = image.select('QA60');
  var cloudBitMask = 1 << 10;
  var cirrusBitMask = 1 << 11;
  var mask = qa.bitwiseAnd(cloudBitMask).eq(0)
    .and(qa.bitwiseAnd(cirrusBitMask).eq(0));
  return image.updateMask(mask).divide(10000);
}

/**
 * Tính chỉ số bất ổn từ trend và variance
 */
function computeStabilityIndex(trend, variance) {
  // Normalize trend magnitude (0-1)
  var trendMag = trend.abs();
  var trendNorm = trendMag.divide(5.0).min(1.0);
  
  // Normalize variance (0-1)
  var varianceNorm = variance.divide(10.0).min(1.0);
  
  // Combined stability index (0 = ổn định, 1 = bất ổn)
  var stability = trendNorm.multiply(0.5)
    .add(varianceNorm.multiply(0.5));
  
  return stability.clamp(0, 1);
}

/**
 * Tính linear trend theo pixel
 */
function computeLinearTrend(collection, band) {
  // Thêm time band (năm)
  var timeCollection = collection.map(function(image) {
    var date = ee.Date(image.get('system:time_start'));
    var years = date.difference(ee.Date(START_DATE), 'year');
    return image
      .addBands(ee.Image(years).rename('time'))
      .set('time', years);
  });
  
  // Linear regression: y = a*time + b
  var linearFit = timeCollection.select(['time', band])
    .reduce(ee.Reducer.linearFit());
  
  // slope = độ dốc (dB/year)
  return linearFit.select('scale');
}

/**
 * Tính temporal variance
 */
function computeTemporalVariance(collection, band) {
  return collection.select(band).reduce(ee.Reducer.variance());
}

/**
 * Phát hiện change points (thay đổi đột ngột)
 */
function detectChangePoints(collection, band) {
  // Chuyển collection thành image với nhiều bands (mỗi band = 1 thời điểm)
  var timeSeries = collection.toBands();
  var nImages = collection.size();
  
  // Tính difference giữa các ảnh liên tiếp
  var diffs = [];
  for (var i = 0; i < 20; i++) {  // Giới hạn 20 differences
    var idx = i + 1;
    var prev = timeSeries.select(ee.String(".*_").cat(idx.toString()));
    var curr = timeSeries.select(ee.String(".*_").cat((idx + 1).toString()));
    var diff = curr.subtract(prev).abs();
    diffs.push(diff.gt(3.0));  // Change > 3 dB
  }
  
  // Tổng số lần thay đổi đột ngột
  var changeCount = ee.ImageCollection(diffs).sum();
  return changeCount;
}

// ============================================================
// 3. LẤY DỮ LIỆU SENTINEL-1
// ============================================================

print("=== Subsidence Proxy Detection (Cấp 1) ===");
print("Loading Sentinel-1 GRD data...");

// Lọc Sentinel-1
var s1Collection = ee.ImageCollection(S1_COLLECTION)
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'));

print("S1 Collection size:", s1Collection.size());

// Lấy collection theo orbit
var s1Orbit55 = s1Collection.filter(ee.Filter.eq('relativeOrbitNumber_start', 55));
var s1Orbit91 = s1Collection.filter(ee.Filter.eq('relativeOrbitNumber_start', 91));
var s1Orbit128 = s1Collection.filter(ee.Filter.eq('relativeOrbitNumber_start', 128));

print("Orbit 55:", s1Orbit55.size());
print("Orbit 91:", s1Orbit91.size());
print("Orbit 128:", s1Orbit128.size());

// Chọn orbit chính (ví dụ: 55)
var mainCollection = s1Orbit55;

// ============================================================
// 4. PHÂN TÍCH TREND (CẤP 1)
// ============================================================

print("Computing backscatter trends...");

// Tính trend VH (dB/year)
var trendVH = computeLinearTrend(mainCollection, 'VH');

// Tính trend VV (dB/year)  
var trendVV = computeLinearTrend(mainCollection, 'VV');

// Tính temporal variance
var varianceVH = computeTemporalVariance(mainCollection, 'VH');
var varianceVV = computeTemporalVariance(mainCollection, 'VV');

// Tính stability index
var stabilityIndex = computeStabilityIndex(trendVH, varianceVH);

// ============================================================
// 5. PHÁT HIỆN HOTSPOT
// ============================================================

print("Detecting instability hotspots...");

// Điều kiện hotspot:
// - Stability index cao (> 0.7)
// - Trend VH giảm mạnh (< -2 dB/year)
// - Variance cao (> 5)

var hotspotMask = stabilityIndex.gt(STABILITY_THRESHOLD)
  .or(trendVH.lt(TREND_THRESHOLD))
  .or(varianceVH.gt(VARIANCE_THRESHOLD));

// Morphological filtering (opening + closing)
var hotspotClean = hotspotMask
  .focalMin(1)  // Erosion (opening)
  .focalMax(2); // Dilation (closing)

// ============================================================
// 6. HIỂN THỊ KẾT QUẢ
// ============================================================

Map.centerObject(ROI, 12);

// Base map
Map.addLayer(ROI, {color: 'red'}, "AOI");

// Trend VH
Map.addLayer(trendVH, {
  min: -5,
  max: 5,
  palette: ['blue', 'white', 'red']
}, "01_VH Trend (dB/year)");

// Trend VV
Map.addLayer(trendVV, {
  min: -5,
  max: 5,
  palette: ['blue', 'white', 'red']
}, "02_VV Trend (dB/year)");

// Stability Index
Map.addLayer(stabilityIndex, {
  min: 0,
  max: 1,
  palette: ['green', 'yellow', 'red']
}, "03_Stability Index (0=stable, 1=unstable)");

// Hotspots
Map.addLayer(hotspotClean.updateMask(hotspotClean), {
  palette: ['red'],
  opacity: 0.7
}, "04_Instability Hotspots");

// ============================================================
// 7. THỐNG KÊ
// ============================================================

// Tính diện tích hotspot
var pixelArea = ee.Image.pixelArea();
var hotspotArea = hotspotClean.multiply(pixelArea)
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: ROI,
    scale: 10,
    maxPixels: 1e9
  });

print("Diện tích vùng nghi ngờ (m²):", hotspotArea);
print("Diện tích vùng nghi ngờ (ha):", 
  ee.Number(hotspotArea.get('constant')).divide(10000));

// Thống kê trend
var trendStats = trendVH.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI,
  scale: 10,
  maxPixels: 1e9
});

print("Trend VH mean:", trendStats.get('scale_mean'), "dB/year");
print("Trend VH stdDev:", trendStats.get('scale_stdDev'), "dB/year");

// ============================================================
// 8. EXPORT KẾT QUẢ
// ============================================================

// Export stability index
Export.image.toDrive({
  image: stabilityIndex,
  description: "TinhTuc_StabilityIndex_Level1_2020_2025",
  folder: "InSAR_TinhTuc",
  region: ROI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

// Export trend VH
Export.image.toDrive({
  image: trendVH,
  description: "TinhTuc_VHTrend_Level1_2020_2025",
  folder: "InSAR_TinhTuc",
  region: ROI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

// Export hotspot mask
Export.image.toDrive({
  image: hotspotClean.unmask(0).byte(),
  description: "TinhTuc_Hotspots_Level1_2020_2025",
  folder: "InSAR_TinhTuc",
  region: ROI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

// Export vector hotspots
var hotspotVectors = hotspotClean.reduceToVectors({
  geometry: ROI,
  scale: 10,
  eightConnected: true,
  maxPixels: 1e9
});

Export.table.toDrive({
  collection: hotspotVectors,
  description: "TinhTuc_HotspotsVector_Level1",
  folder: "InSAR_TinhTuc",
  fileFormat: "GeoJSON"
});

// ============================================================
// 9. THÔNG BÁO HOÀN THÀNH
// ============================================================

print("=== Hoàn thành phân tích Proxy (Cấp 1) ===");
print("");
print("⚠️ LƯU Ý QUAN TRỌNG:");
print("Đây là phân tích PROXY (gián tiếp) qua backscatter trend.");
print("KHÔNG phải đo sụt lún chính xác mm-level.");
print("");
print("Để đo chính xác (3-10 mm/năm):");
print("→ Dùng Cấp 3: SBAS-InSAR với SLC data (ASF HyP3 + MintPy)");
print("");
print("Workflow đề xuất:");
print("1. GEE Level 1 (script này) → Hotspot screening");
print("2. ASF HyP3 + MintPy → True subsidence measurement");
