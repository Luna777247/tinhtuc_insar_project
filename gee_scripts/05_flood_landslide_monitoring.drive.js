/**
 * GEE Script: Flood Mapping & Landslide Detection
 * ================================================
 * Kịch bản 1: Phát hiện ngập lụt (Flood Mapping)
 * Kịch bản 2: Phát hiện sạt lở (Landslide Detection)
 * 
 * Vùng: Tĩnh Túc, Cao Bằng
 * Dữ liệu: Sentinel-1 GRD (VV, VH)
 * Thời gian: Mùa mưa 2025-2026
 * 
 * Tham chiếu: Twele et al. 2016; Bovenga et al. 2021
 */

// ============================================================
// 1. CẤU HÌNH VÙNG NGHIÊN CỨU
// ============================================================

// Load AOI từ GeoJSON (đã cấu hình trong settings)
var AOI_GEOJSON_PATH = 'projects/ee-your-project/assets/TinhTuc_AOI';

// Fallback: bbox mặc định nếu không có asset
var roi = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);

// Thử load từ asset (nếu đã upload)
try {
  roi = ee.FeatureCollection(AOI_GEOJSON_PATH).geometry();
  print('Loaded AOI from GeoJSON asset');
} catch(e) {
  print('Using default bbox, please upload GeoJSON to assets');
}

Map.centerObject(roi, 13);

// ============================================================
// 2. DỮ LIỆU HỖ TRỢ
// ============================================================

// DEM NASADEM 30m
var dem = ee.Image("NASA/NASADEM_HGT/001").select("elevation");
var slope = ee.Terrain.slope(dem);
var aspect = ee.Terrain.aspect(dem);

// JRC Global Surface Water (nước thường xuyên)
var jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select("occurrence");
var permanentWater = jrc.gt(80); // Vùng nước >80% thời gian

// ESA WorldCover (lớp phủ đất)
var worldcover = ee.Image("ESA/WorldCover/v200/2021").select("Map");
var builtUp = worldcover.eq(50); // Khu dân cư
var forest = worldcover.eq(10).or(worldcover.eq(20)); // Rừng

// ============================================================
// 2b. XỬ LÝ SAR TERRAIN RELIEF
// ============================================================

/**
 * Tạo mask cho foreshortening và shadowing.
 */
var createTerrainMasks = function(sarImage) {
  var incidenceAngle = sarImage.select("angle");
  
  // Foreshortening: độ dốc > góc incidence (phía trước)
  var foreshorteningMask = slope.gt(incidenceAngle.subtract(5)).and(
    aspect.gt(0).and(aspect.lt(180))
  );
  
  // Shadowing: độ dốc > góc incidence (phía sau)
  var shadowMask = slope.gt(incidenceAngle.add(5)).and(
    aspect.gt(180).and(aspect.lt(360))
  );
  
  return {
    foreshortening: foreshorteningMask,
    shadow: shadowMask,
    valid: foreshorteningMask.not().and(shadowMask.not())
  };
};

// ============================================================
// 3. HÀM TIỆN ÍCH
// ============================================================

/**
 * Lọc speckle bằng focal mean
 */
var speckleFilter = function(img, kernelSize) {
  var kernel = ee.Kernel.square(kernelSize / 2, 'pixels');
  var filtered = img.reduceNeighborhood({
    reducer: ee.Reducer.mean(),
    kernel: kernel
  });
  return filtered.copyProperties(img, img.propertyNames());
};

/**
 * Tạo mosaic cho Orbit 55 (slice 8+9)
 */
var mosaicOrbit55 = function(dateStr, platform) {
  var d = ee.Date(dateStr);
  var col = ee.ImageCollection("COPERNICUS/S1_GRD")
    .filterDate(d, d.advance(1, "day"))
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 55))
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(roi);
  
  if (platform) {
    col = col.filter(ee.Filter.eq("platform_number", platform));
  }
  
  return col.select(["VH", "VV", "angle"]).mosaic().clip(roi);  // Thêm angle band
};

/**
 * Lấy ảnh Orbit 91
 */
var getOrbit91 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 91))
    .filterDate(startDate, endDate)
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(roi)
    .select(["VH", "VV", "angle"]);  // Thêm angle band
};

/**
 * Lấy ảnh Orbit 128
 */
var getOrbit128 = function(startDate, endDate) {
  return ee.ImageCollection("COPERNICUS/S1_GRD")
    .filter(ee.Filter.eq("instrumentMode", "IW"))  // Interferometric Wide
    .filter(ee.Filter.eq("relativeOrbitNumber_start", 128))
    .filterDate(startDate, endDate)
    .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
    .filterBounds(roi)
    .select(["VH", "VV", "angle"]);  // Thêm angle band
};

/**
 * Tính ngưỡng thích nghi
 */
var adaptiveThreshold = function(diffImage, bandName) {
  var stats = diffImage.reduceRegion({
    reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), "", true),
    geometry: roi,
    scale: 30,
    bestEffort: true,
    maxPixels: 1e9
  });
  
  var mu = ee.Number(stats.get(bandName + "_mean"));
  var sigma = ee.Number(stats.get(bandName + "_stdDev"));
  
  // Ngưỡng = mean - 1.5 * stdDev
  return mu.subtract(sigma.multiply(1.5));
};

// ============================================================
// 4. KỊCH BẢN 1: PHÁT HIỆN NGẬP LỤT (FLOOD MAPPING)
// ============================================================

/**
 * Phát hiện ngập lụt từ Sentinel-1
 * Nguyên lý: Nước làm giảm backscatter (giá trị âm lớn)
 */

// Tham số thời gian (có thể điều chỉnh)
var PRE_START = "2025-06-01";
var PRE_END = "2025-07-01";
var POST_START = "2025-08-01";
var POST_END = "2025-08-31";

print("Flood Detection Period:", PRE_START, "to", POST_END);

// ----- BASELINE (trước sự kiện) -----
var pre55 = ee.ImageCollection([
  mosaicOrbit55("2025-06-01", "A"),
  mosaicOrbit55("2025-07-07", "A")
]).select("VH").mean();  // Đã ở dB

var pre91 = getOrbit91(PRE_START, PRE_END)
  .select("VH").median().clip(roi);  // Đã ở dB

var pre128 = getOrbit128("2025-07-12", "2025-07-13")
  .select("VH").first().clip(roi);  // Đã ở dB

// ----- POST-EVENT (sau sự kiện) -----
var post55 = mosaicOrbit55("2025-08-12", "A").select("VH");  // Đã ở dB
var post91 = getOrbit91("2025-08-14", "2025-08-15")
  .select("VH").first().clip(roi);  // Đã ở dB
var post128 = getOrbit128("2025-08-17", "2025-08-18")
  .select("VH").first().clip(roi);  // Đã ở dB

// ----- TÍNH SAI BIỆT -----
var diff55 = post55.subtract(pre55).rename("VH_diff");
var diff91 = post91.subtract(pre91).rename("VH_diff");
var diff128 = post128.subtract(pre128).rename("VH_diff");

// ----- NGƯỠNG THÍCH NGHI -----
var thr55 = adaptiveThreshold(diff55, "VH_diff");
var thr91 = adaptiveThreshold(diff91, "VH_diff");
var thr128 = adaptiveThreshold(diff128, "VH_diff");

print("Adaptive Thresholds (dB):", {
  orbit55: thr55,
  orbit91: thr91,
  orbit128: thr128
});

// ----- MASK NGẬP -----
// Điều kiện: giảm VH > ngưỡng, độ dốc < 5°, không phải nước thường xuyên
var flood55 = diff55.lt(thr55).and(slope.lt(5)).and(permanentWater.not());
var flood91 = diff91.lt(thr91).and(slope.lt(5)).and(permanentWater.not());
var flood128 = diff128.lt(thr128).and(slope.lt(5)).and(permanentWater.not());

// ----- CONSENSUS 3 TRACK -----
// Pixel được xác nhận ngập khi ≥ 2/3 track phát hiện
var consensus = flood55.add(flood91).add(flood128);
var floodConfirmed = consensus.gte(2);
var floodSuspect = consensus.eq(1);
var floodFinal = floodConfirmed.and(builtUp.not()); // Loại khu dân cư

// ----- HIỂN THỊ -----
Map.addLayer(floodFinal.selfMask(), {
  palette: ["#185FA5"],
  opacity: 0.7
}, "01_Flood Confirmed");

Map.addLayer(floodSuspect.selfMask(), {
  palette: ["#85B7EB"],
  opacity: 0.5
}, "02_Flood Suspect");

// ============================================================
// 5. KỊCH BẢN 2: PHÁT HIỆN SẠT LỞ (LANDSLIDE DETECTION)
// ============================================================

/**
 * Phát hiện sạt lở từ Sentinel-1
 * Đặc điểm: Phá hủy thực vật, lộ đất đá → tăng backscatter
 */

// ----- DẤU HIỆU SẠT LỞ -----
// VH thay đổi > 3 dB, độ dốc 20-55°, không phải ngập lụt
var landslideMask = diff55.abs().gt(3.0)
  .and(slope.gt(20)).and(slope.lt(55))
  .and(floodConfirmed.not());

// ----- XÁC NHẬN BẰNG SENTINEL-2 NDVI -----
var s2 = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
  .filterBounds(roi)
  .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20));

var ndvi = function(img) {
  return img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    .copyProperties(img, ["system:time_start"]);
};

var ndviPre = s2.filterDate("2025-06-01", "2025-07-01")
  .map(ndvi).median().clip(roi);
var ndviPost = s2.filterDate("2025-08-10", "2025-09-01")
  .map(ndvi).median().clip(roi);
var dNDVI = ndviPost.subtract(ndviPre);

// Sạt lở xác nhận: SAR phát hiện + NDVI giảm > 0.2
var landslideConfirmed = landslideMask.and(dNDVI.lt(-0.2));

// ----- HIỂN THỊ -----
Map.addLayer(landslideConfirmed.selfMask(), {
  palette: ["#A32D2D"],
  opacity: 0.8
}, "03_Landslide Confirmed");

// ============================================================
// 6. KỊCH BẢN 4: THEO DÕI BÃI THẢI MỎ
// ============================================================

/**
 * Giám sát dịch chuyển bãi thải mỏ
 */

// Định nghĩa vùng bãi thải (tọa độ ví dụ - cần điều chỉnh)
var mineWaste = ee.Geometry.MultiPoint([
  [105.920, 22.715],
  [105.935, 22.720],
  [105.950, 22.705]
]).buffer(300);

// Thay đổi backscatter > 4 dB trong vùng bãi thải
var mineChange = diff55.abs().gt(4.0)
  .and(diff55.select("VH_diff").abs().gt(4.0))
  .clip(mineWaste);

Map.addLayer(mineChange.selfMask(), {
  palette: ["#BA7517"],
  opacity: 0.8
}, "04_Mine Waste Change");

// ============================================================
// 7. BẢN ĐỒ RỦI RO TỔNG HỢP
// ============================================================

/**
 * Tích hợp ngập lụt + sạt lở + bãi thải
 */

var riskScore = ee.Image(0)
  .where(floodFinal, 1)
  .where(landslideConfirmed, ee.Image(2))
  .where(mineChange, ee.Image(3));

var extremeRisk = riskScore.gte(3);

Map.addLayer(riskScore, {
  min: 0,
  max: 3,
  palette: ['#FFFFFF', '#FFFACD', '#F39C12', '#E74C3C']
}, "05_Risk Score");

// ============================================================
// 8. THỐNG KÊ VÀ XUẤT KẾT QUẢ
// ============================================================

/**
 * Tính diện tích ngập (m²)
 */
var pixelArea = ee.Image.pixelArea();
var floodArea = floodFinal.multiply(pixelArea)
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: roi,
    scale: 10,
    maxPixels: 1e9
  });

print("Diện tích ngập (m²):", floodArea);
print("Diện tích ngập (ha):", ee.Number(floodArea.get("constant")).divide(10000));

/**
 * Thống kê sạt lở
 */
var landslideArea = landslideConfirmed.multiply(pixelArea)
  .reduceRegion({
    reducer: ee.Reducer.sum(),
    geometry: roi,
    scale: 10,
    maxPixels: 1e9
  });

print("Diện tích sạt lở (m²):", landslideArea);

// ============================================================
// 9. EXPORT KẾT QUẢ
// ============================================================

/**
 * Xuất bản đồ ngập ra Google Drive
 */
Export.image.toDrive({
  image: floodFinal.unmask(0).byte(),
  description: "FloodMap_TinhTuc_2025_v3",
  folder: "InSAR_TinhTuc",
  region: roi,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

/**
 * Xuất bản đồ sạt lở
 */
Export.image.toDrive({
  image: landslideConfirmed.unmask(0).byte(),
  description: "LandslideMap_TinhTuc_2025_v3",
  folder: "InSAR_TinhTuc",
  region: roi,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

/**
 * Xuất bản đồ rủi ro
 */
Export.image.toDrive({
  image: riskScore.uint8(),
  description: "RiskMap_TinhTuc_2025_v3",
  folder: "InSAR_TinhTuc",
  region: roi,
  scale: 10,
  crs: "EPSG:4326",
  maxPixels: 1e13
});

/**
 * Xuất vector vùng ngập (GeoJSON)
 */
var floodVectors = floodFinal.reduceToVectors({
  geometry: roi,
  scale: 10,
  eightConnected: true,
  maxPixels: 1e9
});

Export.table.toDrive({
  collection: floodVectors,
  description: "FloodVectors_TinhTuc_2025",
  folder: "InSAR_TinhTuc",
  fileFormat: "GeoJSON"
});

// ============================================================
// 10. CHẠY TỰ ĐỘNG (BATCH PROCESSING)
// ============================================================

/**
 * Hàm xử lý batch cho nhiều thời kỳ
 */
var processFloodBatch = function(dates) {
  var results = dates.map(function(dateRange) {
    var preStart = dateRange[0];
    var preEnd = dateRange[1];
    var postStart = dateRange[2];
    var postEnd = dateRange[3];
    var label = dateRange[4];
    
    // Xử lý tương tự như trên
    // ... (có thể mở rộng)
    
    return {
      label: label,
      period: preStart + "_" + postEnd
    };
  });
  
  return results;
};

// Ví dụ chạy batch
var batchDates = [
  ["2025-06-01", "2025-07-01", "2025-07-15", "2025-07-31", "Flood_Jul"],
  ["2025-06-01", "2025-07-01", "2025-08-01", "2025-08-31", "Flood_Aug"],
  ["2025-06-01", "2025-07-01", "2025-09-01", "2025-09-30", "Flood_Sep"]
];

print("Batch configuration:", batchDates);

// ============================================================
// HOÀN THÀNH
// ============================================================
print("=== Flood & Landslide Monitoring Script Loaded ===");
print("AOI:", roi.bounds().getInfo());
print("Check layers in the Map panel");
