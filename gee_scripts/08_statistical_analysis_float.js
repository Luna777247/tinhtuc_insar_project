/**
 * GEE Script: Phân tích thống kê với S1_GRD_FLOAT (Linear Power)
 * ==============================================================
 * 
 * Sử dụng COPERNICUS/S1_GRD_FLOAT cho statistical analysis chính xác,
 * đặc biệt cho change detection và speckle statistics.
 * 
 * Lý do dùng S1_GRD_FLOAT:
 * - Giá trị linear power (không phải dB log scale)
 * - Phù hợp cho gamma distribution modeling
 * - ENL calculation chính xác hơn
 * - Statistical tests (ratio, likelihood ratio)
 * 
 * Quy đổi: dB = 10 * log10(linear)
 */

// ============================================================
// 1. CẤU HÌNH
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(ROI, 13);

var COLLECTION = "COPERNICUS/S1_GRD_FLOAT";  // Linear power, không phải dB

var START_DATE = "2025-01-01";
var END_DATE = "2025-06-01";

print("=== STATISTICAL ANALYSIS VỚI S1_GRD_FLOAT ===");
print("Collection:", COLLECTION);
print("Linear power values (not dB)");

// ============================================================
// 2. LẤY DỮ LIỆU S1_GRD_FLOAT
// ============================================================

var s1Float = ee.ImageCollection(COLLECTION)
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq("instrumentMode", "IW"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
  .select(["VV", "VH", "angle"]);

print("Số ảnh:", s1Float.size());

// ============================================================
// 3. TÍNH TOÁN THỐNG KÊ SPECKLE
// ============================================================

/**
 * Tính ENL (Equivalent Number of Looks) từ dữ liệu linear power.
 * ENL = mean² / variance (cho gamma distribution)
 */
var calculateENL = function(image) {
  var stats = image.select(["VV", "VH"]).reduceRegion({
    reducer: ee.Reducer.mean().combine(ee.Reducer.variance(), "", true),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var vvMean = ee.Number(stats.get("VV_mean"));
  var vvVar = ee.Number(stats.get("VV_variance"));
  var vhMean = ee.Number(stats.get("VH_mean"));
  var vhVar = ee.Number(stats.get("VH_variance"));
  
  // ENL = mean² / variance
  var enlVV = vvMean.pow(2).divide(vvVar);
  var enlVH = vhMean.pow(2).divide(vhVar);
  
  return image.set({
    "ENL_VV": enlVV,
    "ENL_VH": enlVH,
    "date": image.date().format("YYYY-MM-dd")
  });
};

var s1WithENL = s1Float.map(calculateENL);

// Hiển thị ENL
var enlList = s1WithENL.aggregate_array("ENL_VV");
var enlStats = enlList.reduce(ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true));
print("ENL VV trung bình:", enlStats.get("mean"));
print("ENL VV stdDev:", enlStats.get("stdDev"));

// ============================================================
// 4. CHANGE DETECTION VỚI RATIO TEST (Linear Power)
// ============================================================

// Chia thành 2 giai đoạn
var midDate = "2025-03-15";
var preCollection = s1Float.filterDate(START_DATE, midDate).median();
var postCollection = s1Float.filterDate(midDate, END_DATE).median();

// Ratio test: post / pre (trên linear power)
var ratioVV = postCollection.select("VV").divide(preCollection.select("VV"));
var ratioVH = postCollection.select("VH").divide(preCollection.select("VH"));

// Ngưỡng ratio cho change detection
// Ratio < 0.5 hoặc > 2.0 = significant change
var changeMaskVV = ratioVV.lt(0.5).or(ratioVV.gt(2.0));
var changeMaskVH = ratioVH.lt(0.5).or(ratioVH.gt(2.0));
var changeCombined = changeMaskVV.and(changeMaskVH);

// ============================================================
// 5. SPECKLE FILTERING (LEE FILTER)
// ============================================================

/**
 * LEE filter cho speckle reduction.
 * Sử dụng trên linear power để giữ tính thống kê đúng.
 */
var leeFilter = function(image) {
  var kernel = ee.Kernel.square(3);  // 3x3 window
  var mean = image.focal_mean({kernel: kernel, iterations: 1});
  var variance = image.focal_variance({kernel: kernel});
  
  // LEE filter coefficient
  var cv = variance.sqrt().divide(mean);  // Coefficient of variation
  var weight = mean.pow(2).divide(variance.add(mean.pow(2)));
  
  var filtered = image.multiply(weight).add(mean.multiply(ee.Image(1).subtract(weight)));
  return filtered.copyProperties(image, ["system:time_start"]);
};

var s1Filtered = s1Float.map(leeFilter);

// ============================================================
// 6. HIỂN THỊ BẢN ĐỒ
// ============================================================

// Original linear power
Map.addLayer(preCollection.select("VV"), {
  min: 0,
  max: 0.3,
  palette: ["#000000", "#FFFFFF"]
}, "VV Pre-Event (Linear)");

// Ratio map
Map.addLayer(ratioVV, {
  min: 0,
  max: 3,
  palette: ["#185FA5", "#FFFACD", "#A32D2D"]
}, "VV Ratio (Post/Pre)");

// Change detection
Map.addLayer(changeCombined.selfMask(), {
  palette: ["#FF0000"],
  opacity: 0.7
}, "🔄 Change Detection (Ratio Test)");

// ============================================================
// 7. SO SÁNH: LINEAR VS DB SCALE
// ============================================================

print("\n=== SO SÁNH LINEAR VS DB SCALE ===");

// Lấy 1 ảnh mẫu
var sampleImage = s1Float.first();
var sampleDB = ee.ImageCollection("COPERNICUS/S1_GRD")
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq("system:index", sampleImage.get("system:index")))
  .first();

// Thống kê linear
var linearStats = sampleImage.select("VV").reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true)
    .combine(ee.Reducer.minMax(), "", true),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

print("Linear Power Stats:");
print("  Mean:", linearStats.get("VV_mean"));
print("  StdDev:", linearStats.get("VV_stdDev"));
print("  Min:", linearStats.get("VV_min"));
print("  Max:", linearStats.get("VV_max"));

// Thống kê dB (nếu có)
if (sampleDB) {
  var dbStats = sampleDB.select("VV").reduceRegion({
    reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true)
      .combine(ee.Reducer.minMax(), "", true),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  print("\ndB Scale Stats:");
  print("  Mean:", dbStats.get("VV_mean"));
  print("  StdDev:", dbStats.get("VV_stdDev"));
  print("  Min:", dbStats.get("VV_min"));
  print("  Max:", dbStats.get("VV_max"));
}

// ============================================================
// 8. EXPORT KẾT QUẢ
// ============================================================

// Export ratio map
Export.image.toCloudStorage({
  image: ratioVV,
  description: "S1_FLOAT_Ratio_VV_" + START_DATE + "_" + END_DATE,
  folder: "TinhTuc_Statistical",
  region: ROI,
  scale: 10,
  crs: "EPSG:32648",
  maxPixels: 1e9
});

// Export change mask
Export.image.toCloudStorage({
  image: changeCombined,
  description: "S1_FLOAT_ChangeMask_" + START_DATE + "_" + END_DATE,
  folder: "TinhTuc_Statistical",
  region: ROI,
  scale: 10,
  crs: "EPSG:32648",
  maxPixels: 1e9
});

print("\n✅ Script hoàn thành. Export tasks đã tạo.");
print("Lưu ý: S1_GRD_FLOAT dùng cho statistical analysis, S1_GRD cho visualization.");
