/**
 * ============================================================================
 * GEE SCRIPT: STATISTICAL ANALYSIS FLOAT - UNIFIED
 * ============================================================================
 * 
 * Phân tích thống kê chi tiết trên dữ liệu Sentinel-1 GRD_FLOAT
 * 
 * PHÂN TÍCH:
 * - Gamma distribution parameters
 * - Speckle statistics (ENL)
 * - Temporal variance analysis
 * - Change detection statistical tests
 * - Quality assessment
 * 
 * Export: Cả Drive và Cloud Storage
 * ============================================================================
 */

// ============================================================
// 1. CẤU HÌNH
// ============================================================

var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
Map.centerObject(ROI, 12);

// Thời gian phân tích
var START_DATE = "2025-06-01";
var END_DATE = "2025-12-31";
var ORBIT = 55; // Primary orbit

print("=== STATISTICAL ANALYSIS (FLOAT) ===");
print("ROI:", ROI.bounds().getInfo());
print("Time range:", START_DATE, "to", END_DATE);
print("Orbit:", ORBIT);

// ============================================================
// 2. LOAD SENTINEL-1 GRD_FLOAT
// ============================================================

print("Loading Sentinel-1 GRD_FLOAT data...");

var s1Float = ee.ImageCollection("COPERNICUS/S1_GRD_FLOAT")
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq("instrumentMode", "IW"))
  .filter(ee.Filter.eq("relativeOrbitNumber_start", ORBIT))
  .filter(ee.Filter.eq("orbitProperties_pass", "ASCENDING"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
  .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH"))
  .select(["VV", "VH"]);

print("Total images:", s1Float.size());

// ============================================================
// 3. STATISTICAL ANALYSIS FUNCTIONS
// ============================================================

/**
 * Tính gamma distribution parameters
 * Gamma distribution phù hợp cho SAR intensity
 */
var computeGammaParameters = function(collection, bandName) {
  var stats = collection.select(bandName)
    .reduceRegion({
      reducer: ee.Reducer.mean()
        .combine(ee.Reducer.variance(), '', true)
        .combine(ee.Reducer.minMax(), '', true),
      geometry: ROI,
      scale: 30,
      maxPixels: 1e9
    });
  
  var mean = ee.Number(stats.get(bandName + '_mean'));
  var variance = ee.Number(stats.get(bandName + '_variance'));
  
  // Gamma parameters: α = mean²/variance, β = variance/mean
  var alpha = mean.multiply(mean).divide(variance);
  var beta = variance.divide(mean);
  
  return {
    alpha: alpha,
    beta: beta,
    mean: mean,
    variance: variance,
    stdDev: variance.sqrt(),
    min: ee.Number(stats.get(bandName + '_min')),
    max: ee.Number(stats.get(bandName + '_max'))
  };
};

/**
 * Tính ENL (Equivalent Number of Looks)
 * ENL = mean²/variance cho homogeneous areas
 */
var computeENL = function(image, bandName) {
  var stats = image.select(bandName).reduceRegion({
    reducer: ee.Reducer.mean()
      .combine(ee.Reducer.variance(), '', true),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var mean = ee.Number(stats.get(bandName + '_mean'));
  var variance = ee.Number(stats.get(bandName + '_variance'));
  var enl = mean.multiply(mean).divide(variance);
  
  return enl;
};

/**
 * Tính temporal variance cho time series
 */
var computeTemporalVariance = function(collection, bandName) {
  return collection.select(bandName)
    .reduce(ee.Reducer.variance())
    .rename(bandName + '_temporal_variance');
};

/**
 * Statistical change detection (Chi-square test)
 */
var chiSquareTest = function(img1, img2, bandName) {
  var stats1 = img1.select(bandName).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var stats2 = img2.select(bandName).reduceRegion({
    reducer: ee.Reducer.mean(),
    geometry: ROI,
    scale: 30,
    maxPixels: 1e9
  });
  
  var mean1 = ee.Number(stats1.get(bandName + '_mean'));
  var mean2 = ee.Number(stats2.get(bandName + '_mean'));
  
  // Simple chi-square approximation
  var chiSquare = mean1.subtract(mean2).pow(2).divide(mean2);
  
  return chiSquare;
};

// ============================================================
// 4. COMPUTE STATISTICS
// ============================================================

print("Computing statistical parameters...");

// Gamma parameters for VV and VH
var vvGamma = computeGammaParameters(s1Float, "VV");
var vhGamma = computeGammaParameters(s1Float, "VH");

// Compute ENL for a sample image
var sampleImage = s1Float.first();
var vvENL = computeENL(sampleImage, "VV");
var vhENL = computeENL(sampleImage, "VH");

// Temporal variance
var vvTemporalVar = computeTemporalVariance(s1Float, "VV");
var vhTemporalVar = computeTemporalVariance(s1Float, "VH");

// Split for change detection
var midPoint = ee.Date(START_DATE).advance(
  ee.Date(END_DATE).difference(ee.Date(START_DATE), 'day').divide(2), 'day'
);

var preCollection = s1Float.filterDate(START_DATE, midPoint);
var postCollection = s1Float.filterDate(midPoint, END_DATE);

var preMean = preCollection.mean();
var postMean = postCollection.mean();

// Chi-square test
var vvChiSquare = chiSquareTest(preMean, postMean, "VV");
var vhChiSquare = chiSquareTest(preMean, postMean, "VH");

print("=== STATISTICAL RESULTS ===");
print("VV Gamma alpha:", vvGamma.alpha.getInfo());
print("VV Gamma beta:", vvGamma.beta.getInfo());
print("VH Gamma alpha:", vhGamma.alpha.getInfo());
print("VH Gamma beta:", vhGamma.beta.getInfo());
print("VV ENL:", vvENL.getInfo());
print("VH ENL:", vhENL.getInfo());

// ============================================================
// 5. QUALITY METRICS
// ============================================================

/**
 * Tính quality metrics
 */
var computeQualityMetrics = function() {
  var metrics = {
    data_quality: {
      total_images: s1Float.size(),
      temporal_coverage: ee.Date(END_DATE).difference(ee.Date(START_DATE), 'day'),
      orbit_consistency: ee.Algorithms.If(
        s1Float.size().gt(10),
        'Good',
        'Limited'
      )
    },
    speckle_characteristics: {
      vv_enl: vvENL,
      vh_enl: vhENL,
      speckle_level: ee.Number(1).divide(vvENL.add(vhENL).divide(2))
    },
    distribution_parameters: {
      vv_mean: vvGamma.mean,
      vv_std: vvGamma.stdDev,
      vh_mean: vhGamma.mean,
      vh_std: vhGamma.stdDev
    }
  };
  
  return metrics;
};

var qualityMetrics = computeQualityMetrics();

// ============================================================
// 6. VISUALIZATION
// ============================================================

// Mean images
Map.addLayer(preMean.select("VV"), {
  min: 0,
  max: 0.3,
  palette: ["black", "gray", "white"]
}, "Pre VV Mean");

Map.addLayer(postMean.select("VV"), {
  min: 0,
  max: 0.3,
  palette: ["black", "gray", "white"]
}, "Post VV Mean");

// Temporal variance
Map.addLayer(vvTemporalVar, {
  min: 0,
  max: 0.01,
  palette: ["blue", "white", "red"]
}, "VV Temporal Variance");

Map.addLayer(vhTemporalVar, {
  min: 0,
  max: 0.01,
  palette: ["blue", "white", "red"]
}, "VH Temporal Variance");

// Chi-square change detection
Map.addLayer(vvChiSquare, {
  min: 0,
  max: 10,
  palette: ["white", "yellow", "red"]
}, "VV Chi-Square Change");

Map.addLayer(vhChiSquare, {
  min: 0,
  max: 10,
  palette: ["white", "yellow", "red"]
}, "VH Chi-Square Change");

// ============================================================
// 7. EXPORT - CẢ HAI LỰA CHỌN
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
  
  // Temporal variance
  Export.image.toDrive({
    image: vvTemporalVar.float(),
    description: "VV_TemporalVariance_Statistical_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toDrive({
    image: vhTemporalVar.float(),
    description: "VH_TemporalVariance_Statistical_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Chi-square change
  Export.image.toDrive({
    image: vvChiSquare.float(),
    description: "VV_ChiSquare_Change_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toDrive({
    image: vhChiSquare.float(),
    description: "VH_ChiSquare_Change_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Mean composites
  Export.image.toDrive({
    image: preMean.select("VV").float(),
    description: "VV_PreMean_Statistical_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toDrive({
    image: postMean.select("VV").float(),
    description: "VV_PostMean_Statistical_Drive",
    folder: exportConfig.folder,
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });
};

/**
 * Export ra Google Cloud Storage
 */
var exportToCloudStorage = function() {
  print("=== EXPORT TO GOOGLE CLOUD STORAGE ===");
  
  // Temporal variance
  Export.image.toCloudStorage({
    image: vvTemporalVar.float(),
    description: "VV_TemporalVariance_Statistical_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toCloudStorage({
    image: vhTemporalVar.float(),
    description: "VH_TemporalVariance_Statistical_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Chi-square change
  Export.image.toCloudStorage({
    image: vvChiSquare.float(),
    description: "VV_ChiSquare_Change_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toCloudStorage({
    image: vhChiSquare.float(),
    description: "VH_ChiSquare_Change_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  // Mean composites
  Export.image.toCloudStorage({
    image: preMean.select("VV").float(),
    description: "VV_PreMean_Statistical_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });

  Export.image.toCloudStorage({
    image: postMean.select("VV").float(),
    description: "VV_PostMean_Statistical_GCS",
    bucket: "your-bucket-name", // Cần thay đổi
    region: exportConfig.region,
    scale: exportConfig.scale,
    crs: exportConfig.crs,
    maxPixels: exportConfig.maxPixels
  });
};

// ============================================================
// 8. METADATA EXPORT
// ============================================================

var metadata = ee.Feature(null, {
  'processing_date': ee.Date(Date.now()).format('YYYY-MM-dd HH:mm:ss'),
  'start_date': START_DATE,
  'end_date': END_DATE,
  'orbit': ORBIT,
  'total_images': s1Float.size(),
  'vv_gamma_alpha': vvGamma.alpha,
  'vv_gamma_beta': vvGamma.beta,
  'vh_gamma_alpha': vhGamma.alpha,
  'vh_gamma_beta': vhGamma.beta,
  'vv_enl': vvENL,
  'vh_enl': vhENL,
  'vv_mean': vvGamma.mean,
  'vv_std': vvGamma.stdDev,
  'vh_mean': vhGamma.mean,
  'vh_std': vhGamma.stdDev,
  'analysis_type': 'Statistical_Analysis_Float',
  'data_source': 'Sentinel1_GRD_Float'
});

Export.table.toDrive({
  collection: ee.FeatureCollection([metadata]),
  description: "Statistical_Analysis_Metadata_Drive",
  folder: exportConfig.folder,
  fileFormat: "CSV"
});

// ============================================================
// 9. CHẠY EXPORT - CHỌN PHƯƠNG ÁN
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
print("=== STATISTICAL ANALYSIS (FLOAT) COMPLETED ===");
print("Data Source: Sentinel-1 GRD_FLOAT");
print("Statistical Tests: Gamma distribution, ENL, Chi-square");
print("Choose export method: exportToDrive() or exportToCloudStorage()");
