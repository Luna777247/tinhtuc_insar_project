/**
 * ============================================================================
 * GEE SCRIPT: PRIMARY ORBIT 55 ANALYSIS - UNIFIED
 * ============================================================================
 * 
 * Phân tích chi tiết Orbit 55 (ASC) - quỹ đạo chính cho Tĩnh Túc
 * 
 * PHÂN TÍCH:
 * - Data availability analysis
 * - Temporal coverage assessment
 * - Quality metrics for Orbit 55
 * - Comparison with other orbits
 * - Time series visualization
 * 
 * Export: Cả Drive và Cloud Storage
 * ============================================================================
 */

// ============================================================
// 1. CẤU HÌNH
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(ROI, 12);

// Thời gian phân tích toàn bộ dữ liệu
var START_DATE = "2015-02-20";  // Bắt đầu dữ liệu Tĩnh Túc
var END_DATE = "2026-04-26";    // Kết thúc dữ liệu hiện tại

// Tham số phân tích
var PRIMARY_ORBIT = 55;
var COMPARISON_ORBITS = [91, 128];
var MIN_IMAGES_FOR_TREND = 20;

print("=== PRIMARY ORBIT 55 ANALYSIS ===");
print("ROI:", ROI.bounds().getInfo());
print("Time range:", START_DATE, "to", END_DATE);
print("Primary Orbit:", PRIMARY_ORBIT);

// ============================================================
// 2. LOAD ORBIT 55 DATA
// ============================================================

print("Loading Orbit 55 data...");

var orbit55Collection = ee.ImageCollection("COPERNICUS/S1_GRD")
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq("instrumentMode", "IW"))
  .filter(ee.Filter.eq("relativeOrbitNumber_start", PRIMARY_ORBIT))
  .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
  .select(["VV", "VH", "angle"]);

print("Orbit 55 total images:", orbit55Collection.size());

// ============================================================
// 3. COMPARISON WITH OTHER ORBITS
// ============================================================

print("Loading comparison orbits...");

var loadOrbit = function(orbitNumber) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterBounds(ROI)
    .filterDate(START_DATE, END_DATE)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .filter(ee.Filter.eq("relativeOrbitNumber_start", orbitNumber))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .select(["VV", "VH"]);
};

var orbit91Collection = loadOrbit(91);
var orbit128Collection = loadOrbit(128);

print("Orbit 91 images:", orbit91Collection.size());
print("Orbit 128 images:", orbit128Collection.size());

// ============================================================
// 4. TEMPORAL ANALYSIS
// ============================================================

/**
 * Tính temporal coverage statistics
 */
var analyzeTemporalCoverage = function(collection, orbitName) {
  var dates = collection.aggregate_array('system:time_start');
  var dateObjects = dates.map(function(date) {
    return ee.Date(date);
  });
  
  var firstDate = dateObjects.reduce(ee.Reducer.min());
  var lastDate = dateObjects.reduce(ee.Reducer.max());
  var totalDays = lastDate.difference(firstDate, 'day');
  var imageCount = dates.size();
  var revisitTime = totalDays.divide(imageCount.subtract(1));
  
  return {
    orbit: orbitName,
    first_date: firstDate,
    last_date: lastDate,
    total_days: totalDays,
    image_count: imageCount,
    revisit_time_days: revisitTime,
    coverage_ratio: imageCount.divide(totalDays.divide(12)) // 12-day baseline
  };
};

var orbit55Temporal = analyzeTemporalCoverage(orbit55Collection, "Orbit 55");
var orbit91Temporal = analyzeTemporalCoverage(orbit91Collection, "Orbit 91");
var orbit128Temporal = analyzeTemporalCoverage(orbit128Collection, "Orbit 128");

print("=== TEMPORAL COVERAGE ===");
print("Orbit 55:", orbit55Temporal);
print("Orbit 91:", orbit91Temporal);
print("Orbit 128:", orbit128Temporal);

// ============================================================
// 5. QUALITY ANALYSIS
// ============================================================

/**
 * Tính quality metrics cho collection
 */
var computeQualityMetrics = function(collection, orbitName) {
  // Sample images for quality analysis
  var sampleSize = ee.Number(collection.size()).min(10);
  var sampleCollection = collection.limit(sampleSize);
  
  // Compute statistics
  var vvStats = sampleCollection.select("VV").reduceRegion({
    reducer: ee.Reducer.mean()
      .combine(ee.Reducer.stdDev(), '', true)
      .combine(ee.Reducer.minMax(), '', true),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var vhStats = sampleCollection.select("VH").reduceRegion({
    reducer: ee.Reducer.mean()
      .combine(ee.Reducer.stdDev(), '', true)
      .combine(ee.Reducer.minMax(), '', true),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  return {
    orbit: orbitName,
    total_images: collection.size(),
    vv_mean: vvStats.get("VV_mean"),
    vv_std: vvStats.get("VV_stdDev"),
    vv_min: vvStats.get("VV_min"),
    vv_max: vvStats.get("VV_max"),
    vh_mean: vhStats.get("VH_mean"),
    vh_std: vhStats.get("VH_stdDev"),
    vh_min: vhStats.get("VH_min"),
    vh_max: vhStats.get("VH_max"),
    vv_range: ee.Number(vvStats.get("VV_max")).subtract(vvStats.get("VV_min")),
    vh_range: ee.Number(vhStats.get("VH_max")).subtract(vhStats.get("VH_min"))
  };
};

var orbit55Quality = computeQualityMetrics(orbit55Collection, "Orbit 55");
var orbit91Quality = computeQualityMetrics(orbit91Collection, "Orbit 91");
var orbit128Quality = computeQualityMetrics(orbit128Collection, "Orbit 128");

print("=== QUALITY METRICS ===");
print("Orbit 55:", orbit55Quality);
print("Orbit 91:", orbit91Quality);
print("Orbit 128:", orbit128Quality);

// ============================================================
// 6. TIME SERIES ANALYSIS
// ============================================================

/**
 * Tạo time series chart cho Orbit 55
 */
var createTimeSeries = function(collection, bandName) {
  var timeSeries = collection.map(function(image) {
    var mean = image.select(bandName).reduceRegion({
      reducer: ee.Reducer.mean(),
      geometry: ROI,
      scale: 30,
      maxPixels: 1e9
    });
    
    return ee.Feature(null, {
      'date': image.date(),
      'value': mean.get(bandName + '_mean'),
      'orbit': PRIMARY_ORBIT
    });
  });
  
  return timeSeries;
};

var vvTimeSeries = createTimeSeries(orbit55Collection, "VV");
var vhTimeSeries = createTimeSeries(orbit55Collection, "VH");

// Compute trend lines
var vvTrend = vvTimeSeries.reduceColumns({
  selectors: ['value'],
  reducer: ee.Reducer.linearFit()
});

var vhTrend = vhTimeSeries.reduceColumns({
  selectors: ['value'],
  reducer: ee.Reducer.linearFit()
});

print("=== TIME SERIES TRENDS ===");
print("VV Trend (slope/year):", vvTrend.get('scale'));
print("VH Trend (slope/year):", vhTrend.get('scale'));

// ============================================================
// 7. SEASONAL ANALYSIS
// ============================================================

/**
 * Phân tích theo mùa cho Orbit 55
 */
var analyzeSeasonalPatterns = function(collection) {
  // Add month property
  var withMonth = collection.map(function(image) {
    return image.set('month', image.date().get('month'));
  });
  
  // Group by month and compute statistics
  var monthlyStats = withMonth.reduceColumns({
    selectors: ['VV', 'VH'],
    reducer: ee.Reducer.mean().repeat(2),
    groupField: 'month'
  });
  
  return monthlyStats;
};

var seasonalPatterns = analyzeSeasonalPatterns(orbit55Collection);
print("=== SEASONAL PATTERNS ===");
print("Monthly statistics computed");

// ============================================================
// 8. VISUALIZATION
// ============================================================

// Mean composite for visualization
var orbit55Mean = orbit55Collection.mean();
var orbit91Mean = orbit91Collection.mean();
var orbit128Mean = orbit128Collection.mean();

Map.addLayer(orbit55Mean.select("VV"), {
  min: -25,
  max: 0,
  palette: ["blue", "white", "red"]
}, "Orbit 55 VV Mean");

Map.addLayer(orbit91Mean.select("VV"), {
  min: -25,
  max: 0,
  palette: ["blue", "white", "red"]
}, "Orbit 91 VV Mean");

Map.addLayer(orbit128Mean.select("VV"), {
  min: -25,
  max: 0,
  palette: ["blue", "white", "red"]
}, "Orbit 128 VV Mean");

// Difference between orbits
var diff55vs91 = orbit55Mean.select("VV").subtract(orbit91Mean.select("VV"));
var diff55vs128 = orbit55Mean.select("VV").subtract(orbit128Mean.select("VV"));

Map.addLayer(diff55vs91, {
  min: -5,
  max: 5,
  palette: ["blue", "white", "red"]
}, "Orbit 55 vs 91 Difference");

Map.addLayer(diff55vs128, {
  min: -5,
  max: 5,
  palette: ["blue", "white", "red"]
}, "Orbit 55 vs 128 Difference");

// ============================================================
// 9. EXPORT - CẢ HAI LỰA CHỌN
// ============================================================

var exportConfig = {
  folder: "InSAR_TinhTuc",
  region: ROI,
  scale: 30,
  crs: "EPSG:4326",
  maxPixels: 1e13
};

/**
 * Export ra Google Drive
 */
var exportToDrive = function() {
  print("=== EXPORT TO GOOGLE DRIVE ===");
  
  // Orbit 55 mean
  Export.image.toDrive({
    image: orbit55Mean.select("VV").float(),
    description: "Orbit55_VV_Mean_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toDrive({
    image: orbit55Mean.select("VH").float(),
    description: "Orbit55_VH_Mean_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Orbit comparison
  Export.image.toDrive({
    image: diff55vs91.float(),
    description: "Orbit55_vs_91_Difference_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toDrive({
    image: diff55vs128.float(),
    description: "Orbit55_vs_128_Difference_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Time series data
  Export.table.toDrive({
    collection: vvTimeSeries,
    description: "Orbit55_VV_TimeSeries_Drive",
    folder: exportConfig.folder,
    fileFormat: "CSV"
  });

  Export.table.toDrive({
    collection: vhTimeSeries,
    description: "Orbit55_VH_TimeSeries_Drive",
    folder: exportConfig.folder,
    fileFormat: "CSV"
  });
};

/**
 * Export ra Google Cloud Storage
 */
var exportToCloudStorage = function() {
  print("=== EXPORT TO GOOGLE CLOUD STORAGE ===");
  
  // Orbit 55 mean
  Export.image.toCloudStorage({
    image: orbit55Mean.select("VV").float(),
    description: "Orbit55_VV_Mean_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toCloudStorage({
    image: orbit55Mean.select("VH").float(),
    description: "Orbit55_VH_Mean_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Orbit comparison
  Export.image.toCloudStorage({
    image: diff55vs91.float(),
    description: "Orbit55_vs_91_Difference_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toCloudStorage({
    image: diff55vs128.float(),
    description: "Orbit55_vs_128_Difference_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Time series data
  Export.table.toCloudStorage({
    collection: vvTimeSeries,
    description: "Orbit55_VV_TimeSeries_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    fileFormat: "CSV"
  });

  Export.table.toCloudStorage({
    collection: vhTimeSeries,
    description: "Orbit55_VH_TimeSeries_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    fileFormat: "CSV"
  });
};

// ============================================================
// 10. METADATA EXPORT
// ============================================================

var metadata = ee.Feature(null, {
  'processing_date': ee.Date(Date.now()).format('YYYY-MM-dd HH:mm:ss'),
  'start_date': START_DATE,
  'end_date': END_DATE,
  'primary_orbit': PRIMARY_ORBIT,
  'orbit55_images': orbit55Collection.size(),
  'orbit91_images': orbit91Collection.size(),
  'orbit128_images': orbit128Collection.size(),
  'orbit55_coverage_ratio': orbit55Temporal.coverage_ratio,
  'vv_trend_slope': vvTrend.get('scale'),
  'vh_trend_slope': vhTrend.get('scale'),
  'vv_mean': orbit55Quality.vv_mean,
  'vh_mean': orbit55Quality.vh_mean,
  'analysis_type': 'Primary_Orbit_Analysis',
  'data_source': 'Sentinel1_GRD'
});

Export.table.toDrive({
  collection: ee.FeatureCollection([metadata]),
  description: "Orbit55_Analysis_Metadata_Drive",
  folder: exportConfig.folder,
  fileFormat: "CSV"
});

// ============================================================
// 11. CHẠY EXPORT - CHỌN PHƯƠNG ÁN
// ============================================================

// CHỌN MỘT TRONG HAI:
// 1. exportToDrive();     // Xuất ra Google Drive
// 2. exportToCloudStorage(); // Xuất ra Google Cloud Storage

// Mặc định: Uncomment dòng muốn chạy
exportToDrive();
// exportToCloudStorage();

// ============================================================
// HOÀN THÀNH
// ============================================================
print("=== PRIMARY ORBIT 55 ANALYSIS COMPLETED ===");
print("Primary Orbit:", PRIMARY_ORBIT);
print("Total Images:", orbit55Collection.size());
print("Coverage Period:", START_DATE, "to", END_DATE);
print("Choose export method: exportToDrive() or exportToCloudStorage()");
