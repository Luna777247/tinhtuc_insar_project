/**
 * GEE Script: Phân tích sự kiện mưa lũ 28/09 - 01/10/2025
 * ========================================================
 * 
 * Dữ liệu có:
 * - 29/09/2025: Orbit 55 (ASC) - 10:58
 * - 01/10/2025: Orbit 91 (DESC) - 22:50
 * 
 * Kịch bản:
 * 1. Ngập lụt: Change detection 29/09 vs baseline
 * 2. Sạt lở: Change detection 01/10 vs baseline
 * 3. Tích hợp: Consensus 2 track
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
  // Lấy incidence angle từ S1 metadata (band "angle")
  var incidenceAngle = sarImage.select("angle");
  
  // Tính slope và aspect từ DEM
  var slopeRad = slope.multiply(Math.PI / 180);
  var aspectRad = aspect.multiply(Math.PI / 180);
  
  // Giả định: S1 là right-looking, hướng nhìn vuông góc với flight path
  // Local incidence angle ≈ incidenceAngle - slope (nếu slope hướng về sensor)
  var localIncidence = incidenceAngle.subtract(
    slope.multiply(ee.Image.constant(Math.PI / 180).cos())
  );
  
  return localIncidence.rename("local_incidence_angle");
};

/**
 * Tạo mask cho foreshortening và shadowing.
 * - Foreshortening: slope > incidenceAngle (hướng về sensor)
 * - Shadowing: slope > incidenceAngle (hướng ra xa sensor)
 */
var createTerrainMasks = function(sarImage) {
  var incidenceAngle = sarImage.select("angle");
  
  // Foreshortening: độ dốc > góc incidence (phía trước)
  var foreshorteningMask = slope.gt(incidenceAngle.subtract(5)).and(
    aspect.gt(0).and(aspect.lt(180))  // Hướng Đông (giả định)
  );
  
  // Shadowing: độ dốc > góc incidence (phía sau)
  var shadowMask = slope.gt(incidenceAngle.add(5)).and(
    aspect.gt(180).and(aspect.lt(360))  // Hướng Tây
  );
  
  return {
    foreshortening: foreshorteningMask,
    shadow: shadowMask,
    valid: foreshorteningMask.not().and(shadowMask.not())
  };
};

/**
 * Hiệu chỉnh backscatter theo local incidence angle.
 * Sử dụng cosine correction cơ bản.
 */
var correctBackscatter = function(sarImage, localIncidence) {
  var vh = sarImage.select("VH");
  var incidence = sarImage.select("angle");
  
  // Hiệu chỉnh: σ°_corrected = σ° * cos(θ_local) / cos(θ_incidence)
  var correction = localIncidence.multiply(Math.PI / 180).cos()
    .divide(incidence.multiply(Math.PI / 180).cos());
  
  var vhCorrected = vh.subtract(correction.multiply(10).log10());  // Chuyển sang dB
  
  return vhCorrected.rename("VH_corrected");
};

// ============================================================
// 3. HÀM TIỆN ÍCH
// ============================================================

// LƯU Ý: GEE cung cấp Sentinel-1 GRD đã ở đơn vị dB (10*log10σ°)
// Không cần chuyển đổi thêm!

var mosaicOrbit55 = function(dateStr) {
  var d = ee.Date(dateStr);
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterDate(d, d.advance(1, "day"))
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 55))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(AOI)
    .select(["VH", "VV", "angle"])  // Thêm angle band cho incidence angle
    .mosaic()
    .clip(AOI);
};

var getOrbit91 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 91))
    .filterDate(startDate, endDate)
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(AOI)
    .select(["VH", "VV", "angle"]);  // Thêm angle band
};

var getOrbit128 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 128))
    .filterDate(startDate, endDate)
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(AOI)
    .select(["VH", "VV", "angle"]);  // Thêm angle band
};

// ============================================================
// 4. DỮ LIỆU SENTINEL-1 CHO SỰ KIỆN
// ============================================================

// ----- BASELINE (trước mưa lũ) -----
print("\n1. Tải baseline...");

var pre55 = ee.ImageCollection([
  mosaicOrbit55("2025-09-17")  // 17/09/2025
]).select("VH").mean();  // Đã ở dB, không cần toDb

var pre91 = getOrbit91("2025-09-19", "2025-09-20")  // 19/09/2025
  .select("VH").median().clip(AOI);  // Đã ở dB, không cần toDb

// ----- POST-EVENT (trong/sau mưa lũ) -----
print("2. Tải post-event...");

var post55 = mosaicOrbit55("2025-09-29").select("VH");  // 29/09/2025 - Đã ở dB
var post91 = getOrbit91("2025-10-01", "2025-10-02")  // 01/10/2025
  .select("VH").first().clip(AOI);  // Đã ở dB, không cần toDb

// ============================================================
// 5. PHÂN TÍCH NGẬP LỤT (29/09/2025)
// ============================================================

print("\n3. Phân tích ngập lụt...");

var diff55 = post55.subtract(pre55).rename("VH_diff");

// Ngưỡng thích nghi
var stats55 = diff55.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
  geometry: AOI,
  scale: 30,
  bestEffort: true
});
var mu55 = ee.Number(stats55.get("VH_diff_mean"));
var sigma55 = ee.Number(stats55.get("VH_diff_stdDev"));
var thr55 = mu55.subtract(sigma55.multiply(1.5));

print("Ngưỡng Orbit 55 (dB):", thr55);

// Mask ngập
var flood55 = diff55.lt(thr55).and(slope.lt(5)).and(permanentWater.not());

// ============================================================
// 6. PHÂN TÍCH SẠT LỞ (01/10/2025)
// ============================================================

print("\n4. Phân tích sạt lở...");

var diff91 = post91.subtract(pre91).rename("VH_diff");

// Ngưỡng sạt lở: thay đổi > 3 dB, độ dốc 20-55°
var landslide91 = diff91.abs().gt(3.0)
  .and(slope.gt(20)).and(slope.lt(55))
  .and(flood55.not());  // Loại trùng với ngập

// ============================================================
// 7. TÍCH HỢP KẾT QUẢ
// ============================================================

print("\n5. Tích hợp kết quả...");

// Tổng hợp
var riskScore = ee.Image(0)
  .where(flood55, 1)
  .where(landslide91, 2);

var multiRisk = flood55.add(landslide91);
var extremeRisk = multiRisk.eq(2);  // Cả ngập và sạt lở

// ============================================================
// 8. HIỂN THỊ BẢN ĐỒ
// ============================================================

Map.addLayer(pre55, {min: -20, max: 0, palette: ["#000000", "#FFFFFF"]}, "Baseline 55 (17/09)");
Map.addLayer(post55, {min: -20, max: 0, palette: ["#000000", "#FFFFFF"]}, "Post-Event 55 (29/09)");
Map.addLayer(diff55, {min: -10, max: 5, palette: ["#185FA5", "#FFFACD", "#A32D2D"]}, "Diff 55 (dB)");

Map.addLayer(flood55.selfMask(), {
  palette: ["#185FA5"],
  opacity: 0.7
}, "🌊 Ngập lụt (29/09)");

Map.addLayer(landslide91.selfMask(), {
  palette: ["#A32D2D"],
  opacity: 0.8
}, "⛰️ Sạt lở (01/10)");

Map.addLayer(extremeRisk.selfMask(), {
  palette: ["#8B0000"],
  opacity: 0.9
}, "⚠️ Rủi ro cực cao (cả 2)");

// ============================================================
// 9. THỐNG KÊ
// ============================================================

print("\n6. Thống kê...");

var pixelArea = ee.Image.pixelArea();

var floodArea = flood55.multiply(pixelArea)
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: AOI,
    scale: 10,
    maxPixels: 1e9
  });

var landslideArea = landslide91.multiply(pixelArea)
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: AOI,
    scale: 10,
    maxPixels: 1e9
  });

print("Diện tích ngập (ha):", ee.Number(floodArea.get("constant")).divide(10000));
print("Diện tích sạt lở (ha):", ee.Number(landslideArea.get("constant")).divide(10000));

// ============================================================
// 10. XUẤT KẾT QUẢ
// ============================================================

print("\n7. Xuất kết quả...");

Export.image.toDrive({
  image: flood55.unmask(0).byte(),
  description: "Flood_20250929_TinhTuc",
  folder: "InSAR_Events_2025",
  region: AOI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

Export.image.toDrive({
  image: landslide91.unmask(0).byte(),
  description: "Landslide_20251001_TinhTuc",
  folder: "InSAR_Events_2025",
  region: AOI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

Export.image.toDrive({
  image: riskScore.uint8(),
  description: "RiskMap_20250929_1001_TinhTuc",
  folder: "InSAR_Events_2025",
  region: AOI,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

// Xuất vector
var floodVectors = flood55.reduceToVectors({
  geometry: AOI,
  scale: 10,
  eightConnected: true,
  maxPixels: 1e9
});

Export.table.toDrive({
  collection: floodVectors,
  description: "FloodVectors_20250929",
  folder: "InSAR_Events_2025",
  fileFormat: "GeoJSON"
});

print("\n✅ Hoàn thành! Kiểm tra Tasks panel để xuất.");
