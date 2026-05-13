/**
 * GEE Script: Phân tích sự kiện mưa lũ 28/09 - 01/10/2025 (UNIFIED)
 * ========================================================================
 * 
 * Dữ liệu có:
 * - 29/09/2025: Orbit 55 (ASC) - 10:58
 * - 01/10/2025: Orbit 91 (DESC) - 22:50
 * 
 * Kịch bản:
 * 1. Ngập lụt: Change detection 29/09 vs baseline
 * 2. Sạt lở: Change detection 01/10 vs baseline
 * 3. Tích hợp: Consensus 2 track
 * 
 * Export: Cả Drive và Cloud Storage
 */

// ============================================================
// 1. CẤU HÌNH
// ============================================================

var AOI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(AOI, 13);

// Thời gian
var BASELINE_START = "2025-09-15";
var BASELINE_END = "2025-09-20";  // Trước mưa lũ
var FLOOD_START = "2025-09-28";
var FLOOD_END = "2025-10-02";     // Trong/ sau mưa lũ

print("=== SỰ KIỆN MƯA LŨ 28/09 - 01/10/2025 ===");
print("Baseline:", BASELINE_START, "to", BASELINE_END);
print("Event:", FLOOD_START, "to", FLOOD_END);

// ============================================================
// 2. DỮ LIỆU HỖ TRỢ
// ============================================================

var dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation");
var slope = ee.Terrain.slope(dem);
var aspect = ee.Terrain.aspect(dem);  // Aspect cần cho local incidence angle
var jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence");
var permanentWater = jrc.gt(80);

// ============================================================
// 2b. XỬ LÝ SAR TERRAIN RELIEF (Nâng cao)
// ============================================================

/**
 * Tính local incidence angle từ DEM và SAR angle.
 * S1: near range ~30°, far range ~45°
 */
var computeLocalIncidenceAngle = function(sarImage) {
  var incidenceAngle = sarImage.select("angle");
  var localIncidence = ee.Terrain.slope(dem)
    .multiply(ee.Image.cos(aspect.subtract(incidenceAngle.multiply(Math.PI/180))))
    .atan();
  return localIncidence;
};

// ============================================================
// 3. HÀM TẢI DỮ LIỆU ORBIT 55 & 91
// ============================================================

/**
 * Load Orbit 55 (ASC) - primary cho Tĩnh Túc
 */
var loadOrbit55 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterDate(startDate, endDate)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 55))
    .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(AOI)
    .select(["VV", "VH", "angle"]);
};

/**
 * Load Orbit 91 (DESC) - secondary
 */
var loadOrbit91 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterDate(startDate, endDate)
    .filter(ee.Filter.eq("instrumentMode", "IW"))
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 91))
    .filter(ee.Filter.eq("orbitProperties_pass", "DESCENDING"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(AOI)
    .select(["VV", "VH", "angle"]);
};

// ============================================================
// 4. TẢI DỮ LIỆU
// ============================================================

print("Loading baseline data...");
var baseline55 = loadOrbit55(BASELINE_START, BASELINE_END).median().clip(AOI);
var baseline91 = loadOrbit91(BASELINE_START, BASELINE_END).median().clip(AOI);

print("Loading event data...");
var event55 = loadOrbit55("2025-09-29", "2025-09-29").mosaic().clip(AOI);
var event91 = loadOrbit91("2025-10-01", "2025-10-01").mosaic().clip(AOI);

// ============================================================
// 5. CHANGE DETECTION
// ============================================================

// Change detection cho từng orbit
var diff55_VV = event55.select("VV").subtract(baseline55.select("VV"));
var diff55_VH = event55.select("VH").subtract(baseline55.select("VH"));
var diff91_VV = event91.select("VV").subtract(baseline91.select("VV"));
var diff91_VH = event91.select("VH").subtract(baseline91.select("VH"));

print("Computing adaptive thresholds...");

// Ngưỡng thích nghi cho flood (giảm VV)
var floodThresh55 = diff55_VV.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
  geometry: AOI,
  scale: 30,
  maxPixels: 1e9
});
var floodThresh91 = diff91_VV.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
  geometry: AOI,
  scale: 30,
  maxPixels: 1e9
});

var mu55 = ee.Number(floodThresh55.get("VV_mean"));
var sigma55 = ee.Number(floodThresh55.get("VV_stdDev"));
var mu91 = ee.Number(floodThresh91.get("VV_mean"));
var sigma91 = ee.Number(floodThresh91.get("VV_stdDev"));

var floodThreshold55 = mu55.subtract(sigma55.multiply(1.5));
var floodThreshold91 = mu91.subtract(sigma91.multiply(1.5));

// Ngưỡng thích nghi cho landslide (tăng VH)
var landslideThresh55 = diff55_VH.abs().reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
  geometry: AOI,
  scale: 30,
  maxPixels: 1e9
});
var landslideThresh91 = diff91_VH.abs().reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
  geometry: AOI,
  scale: 30,
  maxPixels: 1e9
});

var landslideThreshold55 = ee.Number(landslideThresh55.get("VH_mean")).add(
  ee.Number(landslideThresh55.get("VH_stdDev")).multiply(2.0)
);
var landslideThreshold91 = ee.Number(landslideThresh91.get("VH_mean")).add(
  ee.Number(landslideThresh91.get("VH_stdDev")).multiply(2.0)
);

print("Thresholds calculated:");
print("Flood 55:", floodThreshold55.getInfo(), "dB");
print("Flood 91:", floodThreshold91.getInfo(), "dB");
print("Landslide 55:", landslideThreshold55.getInfo(), "dB");
print("Landslide 91:", landslideThreshold91.getInfo(), "dB");

// ============================================================
// 6. PHÁT HIỆN NGẬP LỤT
// ============================================================

// Flood detection: VV giảm > ngưỡng, slope < 5°, không phải nước thường xuyên
var flood55 = diff55_VV.lt(floodThreshold55)
  .and(slope.lt(5))
  .and(permanentWater.not());
var flood91 = diff91_VV.lt(floodThreshold91)
  .and(slope.lt(5))
  .and(permanentWater.not());

// Consensus: cần cả 2 orbit phát hiện
var floodConsensus = flood55.and(flood91);
var floodSuspect = flood55.xor(flood91); // Chỉ 1 orbit phát hiện

// ============================================================
// 7. PHÁT HIỆN SẠT LỞ
// ============================================================

// Landslide detection: VH tăng > ngưỡng, slope 20-55°, không phải flood
var landslide55 = diff55_VH.gt(landslideThreshold55)
  .and(slope.gt(20))
  .and(slope.lt(55))
  .and(floodConsensus.not());
var landslide91 = diff91_VH.gt(landslideThreshold91)
  .and(slope.gt(20))
  .and(slope.lt(55))
  .and(floodConsensus.not());

// Consensus: cần cả 2 orbit phát hiện
var landslideConsensus = landslide55.and(landslide91);

// ============================================================
// 8. TÍCH HỢP KẾT QUẢ
// ============================================================

// Tạo bản đồ tổng hợp
var riskMap = ee.Image(0)
  .where(floodConsensus, 1)        // Flood confirmed
  .where(floodSuspect, 2)         // Flood suspect
  .where(landslideConsensus, 3)    // Landslide confirmed
  .rename("risk_level");

// ============================================================
// 9. HIỂN THỊ
// ============================================================

Map.addLayer(diff55_VV, {min: -8, max: 8, palette: ["blue", "white", "red"]}, "Diff55 VV");
Map.addLayer(diff91_VV, {min: -8, max: 8, palette: ["blue", "white", "red"]}, "Diff91 VV");

Map.addLayer(floodConsensus.selfMask(), {palette: ["#0066CC"]}, "Flood Confirmed");
Map.addLayer(floodSuspect.selfMask(), {palette: ["#66B2FF"]}, "Flood Suspect");
Map.addLayer(landslideConsensus.selfMask(), {palette: ["#FF6600"]}, "Landslide Confirmed");

Map.addLayer(riskMap, {
  min: 0,
  max: 3,
  palette: ["#FFFFFF", "#0066CC", "#66B2FF", "#FF6600"]
}, "Risk Map");

// ============================================================
// 10. THỐNG KÊ
// ============================================================

var pixelArea = ee.Image.pixelArea();

// Flood statistics
var floodArea = floodConsensus.multiply(pixelArea).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: AOI,
  scale: 10,
  maxPixels: 1e9
});

// Landslide statistics
var landslideArea = landslideConsensus.multiply(pixelArea).reduceRegion({
  reducer: ee.Reducer.sum(),
  geometry: AOI,
  scale: 10,
  maxPixels: 1e9
});

print("=== STATISTICS ===");
print("Flood Area (ha):", ee.Number(floodArea.get("constant")).divide(10000));
print("Landslide Area (ha):", ee.Number(landslideArea.get("constant")).divide(10000));

// ============================================================
// 11. EXPORT - CẢ HAI LỰA CHỌN
// ============================================================

var exportConfig = {
  folder: "InSAR_TinhTuc",
  region: AOI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
};

/**
 * Export ra Google Drive
 */
var exportToDrive = function() {
  print("=== EXPORT TO GOOGLE DRIVE ===");
  
  // Flood map
  Export.image.toDrive({
    image: floodConsensus.unmask(0).byte(),
    description: "Flood_Event_20250929_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Landslide map
  Export.image.toDrive({
    image: landslideConsensus.unmask(0).byte(),
    description: "Landslide_Event_20250929_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Risk map
  Export.image.toDrive({
    image: riskMap.uint8(),
    description: "RiskMap_Event_20250929_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Flood vectors
  var floodVectors = floodConsensus.reduceToVectors({
    geometry: AOI,
    scale: 10,
    eightConnected: true,
    maxPixels: 1e9
  });

  Export.table.toDrive({
    collection: floodVectors,
    description: "FloodVectors_Event_20250929_Drive",
    folder: exportConfig.folder,
    fileFormat: "GeoJSON"
  });
};

/**
 * Export ra Google Cloud Storage
 */
var exportToCloudStorage = function() {
  print("=== EXPORT TO GOOGLE CLOUD STORAGE ===");
  
  // Flood map
  Export.image.toCloudStorage({
    image: floodConsensus.unmask(0).byte(),
    description: "Flood_Event_20250929_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Landslide map
  Export.image.toCloudStorage({
    image: landslideConsensus.unmask(0).byte(),
    description: "Landslide_Event_20250929_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Risk map
  Export.image.toCloudStorage({
    image: riskMap.uint8(),
    description: "RiskMap_Event_20250929_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Flood vectors
  var floodVectors = floodConsensus.reduceToVectors({
    geometry: AOI,
    scale: 10,
    eightConnected: true,
    maxPixels: 1e9
  });

  Export.table.toCloudStorage({
    collection: floodVectors,
    description: "FloodVectors_Event_20250929_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    fileFormat: "GeoJSON"
  });
};

// ============================================================
// 12. CHẠY EXPORT - CHỌN PHƯƠNG ÁN
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
print("=== Flood Event Analysis Script (UNIFIED) Loaded ===");
print("Event: 28/09 - 01/10/2025");
print("Choose export method: exportToDrive() or exportToCloudStorage()");
