/**
 * ============================================================================
 * GEE SCRIPT: SUBSIDENCE PROXY DETECTION (CẤP 1) - UNIFIED
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
 * Export: Cả Drive và Cloud Storage
 * Reference: Phần 0.6 tài liệu Sentinel1_TinhTuc_PhanTich_KichBan_ChiTiet.md
 * ============================================================================
 */

// ============================================================
// 1. THAM SỐ CẤU HÌNH
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(ROI, 12);

// Thời gian phân tích dài hạn
var START_DATE = "2015-02-20";  // Bắt đầu dữ liệu Tĩnh Túc
var END_DATE = "2026-04-26";    // Kết thúc dữ liệu hiện tại

// Tham số phân tích
var MIN_OBSERVATIONS = 20;  // Số ảnh tối thiểu cho regression
var VARIANCE_THRESHOLD = 0.02;  // Ngưỡng variance cho instability
var HOTSPOT_PERCENTILE = 90;  // Percentile cho hotspot detection

print("=== SUBSIDENCE PROXY DETECTION (LEVEL 1) ===");
print("ROI:", ROI.bounds().getInfo());
print("Time range:", START_DATE, "to", END_DATE);
print("Min observations:", MIN_OBSERVATIONS);

// ============================================================
// 2. DỮ LIỆU HỖ TRỢ
// ============================================================

// DEM cho terrain correction
var dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation");
var slope = ee.Terrain.slope(dem);

// JRC Global Surface Water để loại vùng nước
var jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence");
var waterMask = jrc.lt(50); // Loại vùng nước thường xuyên

// ESA WorldCover cho land cover context
var worldcover = ee.Image("ESA/WorldCover/v200/2021").select("Map");
var urbanMask = worldcover.eq(50); // Khu dân cư
var forestMask = worldcover.eq(10).or(worldcover.eq(20)); // Rừng

// ============================================================
// 3. LOAD SENTINEL-1 DATA
// ============================================================

print("Loading Sentinel-1 data...");

// Load toàn bộ time series với Orbit 55 (primary)
var s1Collection = ee.ImageCollection("COPERNICUS/S1_GRD")
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq("instrumentMode", "IW"))
  .filter(ee.Filter.eq("relativeOrbitNumber_start", 55))
  .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
  .select(["VV", "VH"]);

print("Total images:", s1Collection.size());

// Kiểm tra số lượng ảnh
var imageCount = s1Collection.size().getInfo();
if (imageCount < MIN_OBSERVATIONS) {
  print("WARNING: Insufficient images for reliable trend analysis");
  print("Found:", imageCount, "Required:", MIN_OBSERVATIONS);
}

// ============================================================
// 4. TIME SERIES ANALYSIS
// ============================================================

/**
 * Tính linear regression cho time series
 * Output: slope, intercept, scale (std error)
 */
var computeLinearTrend = function(collection, bandName) {
  var trend = collection.select(bandName)
    .reduce(ee.Reducer.linearFit({
      numX: 1,
      numY: 1
    }));
  
  return trend.select({
    'scale': bandName + '_scale',
    'offset': bandName + '_offset'
  });
};

/**
 * Tính temporal variance
 */
var computeVariance = function(collection, bandName) {
  return collection.select(bandName)
    .reduce(ee.Reducer.variance())
    .rename(bandName + '_variance');
};

/**
 * Tính stability index (0 = stable, 1 = unstable)
 */
var computeStabilityIndex = function(varianceImg, threshold) {
  return varianceImg.divide(threshold)
    .clamp(0, 1)
    .rename('stability_index');
};

// Compute trends
print("Computing linear trends...");
var vvTrend = computeLinearTrend(s1Collection, "VV");
var vhTrend = computeLinearTrend(s1Collection, "VH");

// Compute variance
print("Computing temporal variance...");
var vvVariance = computeVariance(s1Collection, "VV");
var vhVariance = computeVariance(s1Collection, "VH");

// Compute stability index
var vvStability = computeStabilityIndex(vvVariance, VARIANCE_THRESHOLD);
var vhStability = computeStabilityIndex(vhVariance, VARIANCE_THRESHOLD);

// Combined stability (max of VV and VH)
var combinedStability = vvStability.max(vhStability);

// ============================================================
// 5. HOTSPOT DETECTION
// ============================================================

/**
 * Phát hiện hotspot dựa trên high instability
 */
var detectHotspots = function(stabilityImg, percentile) {
  var threshold = stabilityImg.reduceRegion({
    reducer: ee.Reducer.percentile([percentile]),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var thresh = ee.Number(threshold.get('stability_index_p' + percentile));
  return stabilityImg.gt(thresh).rename('hotspot');
};

print("Detecting instability hotspots...");
var instabilityHotspots = detectHotspots(combinedStability, HOTSPOT_PERCENTILE);

// ============================================================
// 6. TERRAIN-MASKED ANALYSIS
// ============================================================

// Áp dụng masks
var vvTrendMasked = vvTrend.updateMask(waterMask.not());
var vhTrendMasked = vhTrend.updateMask(waterMask.not());
var stabilityMasked = combinedStability.updateMask(waterMask.not());
var hotspotsMasked = instabilityHotspots.updateMask(waterMask.not());

// Slope-based analysis (chỉ cho slope < 30°)
var slopeMask = slope.lt(30);
var vvTrendSlope = vvTrendMasked.updateMask(slopeMask);
var vhTrendSlope = vhTrendMasked.updateMask(slopeMask);

// ============================================================
// 7. STATISTICS
// ============================================================

print("Computing statistics...");

var pixelArea = ee.Image.pixelArea();

// Stability statistics
var stableArea = stabilityMasked.lt(0.3).multiply(pixelArea).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

var unstableArea = stabilityMasked.gt(0.7).multiply(pixelArea).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

// Hotspot statistics
var hotspotArea = hotspotsMasked.multiply(pixelArea).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

// Trend statistics
var vvTrendStats = vvTrendSlope.select('VV_scale').reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

var vhTrendStats = vhTrendSlope.select('VH_scale').reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI,
  scale: 30,
  maxPixels: 1e9
});

print("=== STATISTICS ===");
print("Stable area (ha):", ee.Number(stableArea.get('stability_index')).divide(10000));
print("Unstable area (ha):", ee.Number(unstableArea.get('stability_index')).divide(10000));
print("Hotspot area (ha):", ee.Number(hotspotArea.get('hotspot')).divide(10000));
print("VV trend mean:", vvTrendStats.get('VV_scale_mean'));
print("VH trend mean:", vhTrendStats.get('VH_scale_mean'));

// ============================================================
// 8. VISUALIZATION
// ============================================================

// Trend visualization (dB/year)
Map.addLayer(vvTrendSlope.select('VV_scale'), {
  min: -0.5,
  max: 0.5,
  palette: ["blue", "white", "red"]
}, "VV Trend (dB/year)");

Map.addLayer(vhTrendSlope.select('VH_scale'), {
  min: -0.5,
  max: 0.5,
  palette: ["blue", "white", "red"]
}, "VH Trend (dB/year)");

// Stability index
Map.addLayer(stabilityMasked, {
  min: 0,
  max: 1,
  palette: ["green", "yellow", "red"]
}, "Stability Index");

// Hotspots
Map.addLayer(hotspotsMasked.selfMask(), {
  palette: ["red"],
  opacity: 0.8
}, "Instability Hotspots");

// Land cover context
Map.addLayer(urbanMask.selfMask(), {
  palette: ["gray"]
}, "Urban Areas");

Map.addLayer(forestMask.selfMask(), {
  palette: ["darkgreen"]
}, "Forest Areas");

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
  
  // VV trend
  Export.image.toDrive({
    image: vvTrendSlope.select('VV_scale').float(),
    description: "VV_Trend_SubsidenceProxy_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // VH trend
  Export.image.toDrive({
    image: vhTrendSlope.select('VH_scale').float(),
    description: "VH_Trend_SubsidenceProxy_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Stability index
  Export.image.toDrive({
    image: stabilityMasked.float(),
    description: "StabilityIndex_SubsidenceProxy_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Hotspots
  Export.image.toDrive({
    image: hotspotsMasked.unmask(0).byte(),
    description: "Hotspots_SubsidenceProxy_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Hotspot vectors
  var hotspotVectors = hotspotsMasked.reduceToVectors({
    geometry: ROI,
    scale: 30,
    eightConnected: true,
    maxPixels: 1e9
  });

  Export.table.toDrive({
    collection: hotspotVectors,
    description: "HotspotVectors_SubsidenceProxy_Drive",
    folder: exportConfig.folder,
    fileFormat: "GeoJSON"
  });
};

/**
 * Export ra Google Cloud Storage
 */
var exportToCloudStorage = function() {
  print("=== EXPORT TO GOOGLE CLOUD STORAGE ===");
  
  // VV trend
  Export.image.toCloudStorage({
    image: vvTrendSlope.select('VV_scale').float(),
    description: "VV_Trend_SubsidenceProxy_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // VH trend
  Export.image.toCloudStorage({
    image: vhTrendSlope.select('VH_scale').float(),
    description: "VH_Trend_SubsidenceProxy_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Stability index
  Export.image.toCloudStorage({
    image: stabilityMasked.float(),
    description: "StabilityIndex_SubsidenceProxy_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Hotspots
  Export.image.toCloudStorage({
    image: hotspotsMasked.unmask(0).byte(),
    description: "Hotspots_SubsidenceProxy_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Hotspot vectors
  var hotspotVectors = hotspotsMasked.reduceToVectors({
    geometry: ROI,
    scale: 30,
    eightConnected: true,
    maxPixels: 1e9
  });

  Export.table.toCloudStorage({
    collection: hotspotVectors,
    description: "HotspotVectors_SubsidenceProxy_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    fileFormat: "GeoJSON"
  });
};

// ============================================================
// 10. CHẠY EXPORT - CHỌN PHƯƠNG ÁN
// ============================================================

// CHỌN MỘT TRONG HAI:
// 1. exportToDrive();     // Xuất ra Google Drive
// 2. exportToCloudStorage(); // Xuất ra Google Cloud Storage

// Mặc định: Uncomment dòng muốn chạy
exportToDrive();
// exportToCloudStorage();

// ============================================================
// 11. METADATA EXPORT
// ============================================================

// Export processing metadata
var metadata = ee.Feature(null, {
  'processing_date': ee.Date(Date.now()).format('YYYY-MM-dd HH:mm:ss'),
  'start_date': START_DATE,
  'end_date': END_DATE,
  'total_images': imageCount,
  'min_observations': MIN_OBSERVATIONS,
  'variance_threshold': VARIANCE_THRESHOLD,
  'hotspot_percentile': HOTSPOT_PERCENTILE,
  'stable_area_ha': ee.Number(stableArea.get('stability_index')).divide(10000),
  'unstable_area_ha': ee.Number(unstableArea.get('stability_index')).divide(10000),
  'hotspot_area_ha': ee.Number(hotspotArea.get('hotspot')).divide(10000),
  'vv_trend_mean': vvTrendStats.get('VV_scale_mean'),
  'vh_trend_mean': vhTrendStats.get('VH_scale_mean'),
  'analysis_level': 'Level_1_Proxy',
  'data_source': 'Sentinel1_GRD_GEE'
});

Export.table.toDrive({
  collection: ee.FeatureCollection([metadata]),
  description: "SubsidenceProxy_Metadata_Drive",
  folder: exportConfig.folder,
  fileFormat: "CSV"
});

// ============================================================
// HOÀN THÀNH
// ============================================================
print("=== SUBSIDENCE PROXY ANALYSIS (UNIFIED) COMPLETED ===");
print("Analysis Level: Level 1 (Proxy Detection)");
print("Time Period:", START_DATE, "to", END_DATE);
print("Total Images:", imageCount);
print("Choose export method: exportToDrive() or exportToCloudStorage()");
print("⚠️  REMINDER: This is PROXY analysis, not mm-level subsidence measurement");
