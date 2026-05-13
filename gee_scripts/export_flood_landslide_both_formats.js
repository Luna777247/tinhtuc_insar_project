// =========================================================
// EXPORT BOTH FORMATS - Flood & Landslide Detection
// GeoTIFF (raster) + GeoJSON (vector) cho Sentinel-1
// =========================================================

// 1. CONFIGURATION
var ROI = ee.Geometry.Rectangle([105.85, 22.62, 106.05, 22.80]);
var START_DATE = '2025-06-01';
var END_DATE = '2025-12-31';
var ORBIT = 55;  // Primary orbit cho Tĩnh Túc
var EXPORT_SCALE = 10;  // 10m resolution

// 2. LOAD SENTINEL-1 DATA
var S1 = ee.ImageCollection('COPERNICUS/S1_GRD')
  .filterBounds(ROI)
  .filterDate(START_DATE, END_DATE)
  .filter(ee.Filter.eq('instrumentMode', 'IW'))
  .filter(ee.Filter.eq('relativeOrbitNumber_start', ORBIT))
  .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'));

print('Total S1 images:', S1.size());

// 3. MOSAIC FUNCTION
var mosaicByDate = function(collection, date) {
  var d = ee.Date(date);
  return collection
    .filterDate(d, d.advance(1, 'day'))
    .select('VV', 'VH')
    .mosaic()
    .clip(ROI);
};

// 4. PRE/POST EVENT IMAGES
var pre = mosaicByDate(S1, '2025-07-07');
var post = mosaicByDate(S1, '2025-08-12');

// 5. CHANGE DETECTION
var diffVV = post.select('VV').subtract(pre.select('VV')).rename('diffVV');
var diffVH = post.select('VH').subtract(pre.select('VH')).rename('diffVH');

// 6. DEM & SLOPE
var dem = ee.Image('NASA/NASADEM_HGT/001').select('elevation');
var slope = ee.Terrain.slope(dem);

// 7. ADAPTIVE THRESHOLD FOR FLOOD
var floodStats = diffVV.reduceRegion({
  reducer: ee.Reducer.mean().combine(ee.Reducer.stdDev(), '', true),
  geometry: ROI, 
  scale: 30, 
  bestEffort: true
});
var floodMu = ee.Number(floodStats.get('diffVV_mean'));
var floodSigma = ee.Number(floodStats.get('diffVV_stdDev'));
var floodThresh = floodMu.subtract(floodSigma.multiply(1.5));

// 8. FLOOD DETECTION (VV < threshold, slope < 5°)
var floodRaster = diffVV.lt(floodThresh).and(slope.lt(5)).rename('flood_mask');

// 9. LANDSLIDE DETECTION (VH change > 3dB, slope 20-55°)
var landslideRaster = diffVH.abs().gt(3.0)
  .and(slope.gt(20)).and(slope.lt(55))
  .rename('landslide_mask');

// 10. REMOVE PERMANENT WATER
var jrc = ee.Image('JRC/GSW1_4/GlobalSurfaceWater').select('occurrence');
var floodFinal = floodRaster.and(jrc.lt(80));

// 11. VECTORIZATION FUNCTION
var rasterToVector = function(raster, value, name) {
  return raster.eq(value)
    .selfMask()
    .reduceToVectors({
      geometry: ROI,
      crs: raster.projection(),
      scale: EXPORT_SCALE,
      geometryType: 'polygon',
      eightConnected: false,
      labelProperty: 'label',
      reducer: ee.Reducer.countEvery()
    })
    .map(function(feature) {
      return feature.set({
        'class': name,
        'area_m2': feature.geometry().area(),
        'area_ha': ee.Number(feature.geometry().area()).divide(10000),
        'date_processed': ee.Date(post.date()).format('YYYY-MM-dd'),
        'orbit': ORBIT,
        'pass': 'ASCENDING'
      });
    });
};

// 12. CREATE VECTOR LAYERS
var floodVectors = rasterToVector(floodFinal, 1, 'flood');
var landslideVectors = rasterToVector(landslideRaster, 1, 'landslide');

// 13. CALCULATE STATISTICS
var floodArea = floodFinal.multiply(ee.Image.pixelArea())
  .reduceRegion({reducer: ee.Reducer.sum(), geometry: ROI, scale: EXPORT_SCALE});
var landslideArea = landslideRaster.multiply(ee.Image.pixelArea())
  .reduceRegion({reducer: ee.Reducer.sum(), geometry: ROI, scale: EXPORT_SCALE});

// 14. CREATE METADATA TABLE
var metadata = ee.Feature(null, {
  'processing_date': ee.Date(Date.now()).format('YYYY-MM-dd HH:mm:ss'),
  'pre_event_date': '2025-07-07',
  'post_event_date': '2025-08-12',
  'orbit': ORBIT,
  'pass': 'ASCENDING',
  'flood_threshold_db': floodThresh.getInfo(),
  'landslide_threshold_db': 3.0,
  'flood_area_m2': floodArea.get('flood_mask'),
  'flood_area_ha': ee.Number(floodArea.get('flood_mask')).divide(10000),
  'landslide_area_m2': landslideArea.get('landslide_mask'),
  'landslide_area_ha': ee.Number(landslideArea.get('landslide_mask')).divide(10000),
  'total_polygons_flood': floodVectors.size(),
  'total_polygons_landslide': landslideVectors.size(),
  'pixel_size_m': EXPORT_SCALE
});

// =========================================================
// EXPORT CONFIGURATION
// =========================================================

// 15. EXPORT RASTER (GeoTIFF)
print('Starting raster exports...');

// Flood Mask - GeoTIFF uint8
Export.image.toDrive({
  image: floodFinal.uint8().selfMask(),
  description: 'Flood_Mask_GeoTIFF',
  fileNamePrefix: 'flood_mask_20250812_uint8',
  region: ROI,
  scale: EXPORT_SCALE,
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF',
  formatOptions: {
    'cloudOptimized': true
  }
});

// Landslide Mask - GeoTIFF uint8
Export.image.toDrive({
  image: landslideRaster.uint8().selfMask(),
  description: 'Landslide_Mask_GeoTIFF',
  fileNamePrefix: 'landslide_mask_20250812_uint8',
  region: ROI,
  scale: EXPORT_SCALE,
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF',
  formatOptions: {
    'cloudOptimized': true
  }
});

// Backscatter Difference - GeoTIFF float32
Export.image.toDrive({
  image: diffVV.float32(),
  description: 'Backscatter_Diff_VV_GeoTIFF',
  fileNamePrefix: 'backscatter_diff_vv_20250812',
  region: ROI,
  scale: EXPORT_SCALE,
  maxPixels: 1e13,
  fileFormat: 'GeoTIFF',
  formatOptions: {
    'cloudOptimized': true
  }
});

// 16. EXPORT VECTOR (GeoJSON)
print('Starting vector exports...');

// Flood Polygons - GeoJSON
Export.table.toDrive({
  collection: floodVectors,
  description: 'Flood_Polygons_GeoJSON',
  fileFormat: 'GeoJSON',
  fileNamePrefix: 'flood_polygons_20250812'
});

// Landslide Polygons - GeoJSON
Export.table.toDrive({
  collection: landslideVectors,
  description: 'Landslide_Polygons_GeoJSON',
  fileFormat: 'GeoJSON',
  fileNamePrefix: 'landslide_polygons_20250812'
});

// 17. EXPORT METADATA
print('Starting metadata export...');

Export.table.toDrive({
  collection: ee.FeatureCollection([metadata]),
  description: 'Processing_Metadata',
  fileFormat: 'CSV',
  fileNamePrefix: 'flood_landslide_metadata_20250812'
});

// =========================================================
// VISUALIZATION
// =========================================================

// 18. LAYER VISUALIZATION
Map.centerObject(ROI, 12);
Map.addLayer(ROI, {color: 'yellow'}, 'ROI');

// Pre/Post Event
Map.addLayer(pre.select('VV'), {min: -25, max: 0, palette: ['red', 'yellow', 'green']}, 'Pre VV');
Map.addLayer(post.select('VV'), {min: -25, max: 0, palette: ['red', 'yellow', 'green']}, 'Post VV');

// Difference
Map.addLayer(diffVV, {min: -5, max: 5, palette: ['red', 'white', 'blue']}, 'VV Difference');

// Raster Results
Map.addLayer(floodFinal.selfMask(), {palette: ['blue']}, 'Flood Raster');
Map.addLayer(landslideRaster.selfMask(), {palette: ['red']}, 'Landslide Raster');

// Vector Results
Map.addLayer(floodVectors, {color: 'blue', fillColor: '0000FF40'}, 'Flood Polygons');
Map.addLayer(landslideVectors, {color: 'red', fillColor: 'FF000040'}, 'Landslide Polygons');

// =========================================================
// PRINT STATISTICS
// =========================================================

print('=== PROCESSING STATISTICS ===');
print('Flood area (ha):', ee.Number(floodArea.get('flood_mask')).divide(10000));
print('Landslide area (ha):', ee.Number(landslideArea.get('landslide_mask')).divide(10000));
print('Flood polygons count:', floodVectors.size());
print('Landslide polygons count:', landslideVectors.size());
print('Flood threshold (dB):', floodThresh);
print('Metadata:', metadata);

// =========================================================
// QUALITY CONTROL
// =========================================================

// 19. VALIDATION CHECKS
var validateExports = function() {
  print('=== VALIDATION CHECKS ===');
  
  // Check if data exists
  var hasFlood = floodFinal.reduceRegion({
    reducer: ee.Reducer.anyNonZero(),
    geometry: ROI,
    scale: EXPORT_SCALE,
    maxPixels: 1e9
  });
  
  var hasLandslide = landslideRaster.reduceRegion({
    reducer: ee.Reducer.anyNonZero(),
    geometry: ROI,
    scale: EXPORT_SCALE,
    maxPixels: 1e9
  });
  
  print('Has flood pixels:', hasFlood);
  print('Has landslide pixels:', hasLandslide);
  
  // Check vector counts
  print('Flood vector count:', floodVectors.size().getInfo());
  print('Landslide vector count:', landslideVectors.size().getInfo());
  
  return {
    flood_detected: hasFlood.get('flood_mask'),
    landslide_detected: hasLandslide.get('landslide_mask'),
    flood_polygons: floodVectors.size().getInfo(),
    landslide_polygons: landslideVectors.size().getInfo()
  };
};

// Run validation
var validationResults = validateExports();
print('Validation Results:', validationResults);

// =========================================================
// USAGE NOTES
// =========================================================

/*
USAGE INSTRUCTIONS:

1. RUN THIS SCRIPT IN GOOGLE EARTH ENGINE
   - Copy entire script to GEE Code Editor
   - Run to generate all export tasks
   - Check console for statistics and validation

2. EXPORT TASKS CREATED:
   RASTER (GeoTIFF):
   - Flood_Mask_GeoTIFF → flood_mask_20250812_uint8.tif
   - Landslide_Mask_GeoTIFF → landslide_mask_20250812_uint8.tif
   - Backscatter_Diff_VV_GeoTIFF → backscatter_diff_vv_20250812.tif
   
   VECTOR (GeoJSON):
   - Flood_Polygons_GeoJSON → flood_polygons_20250812.geojson
   - Landslide_Polygons_GeoJSON → landslide_polygons_20250812.geojson
   
   METADATA:
   - Processing_Metadata → flood_landslide_metadata_20250812.csv

3. FILE FORMATS:
   - GeoTIFF: uint8 for masks, float32 for backscatter
   - GeoJSON: polygons with area, date, orbit info
   - CSV: processing parameters and statistics

4. COORDINATE SYSTEM:
   - All exports use original CRS from Sentinel-1
   - Scale: 10m (native Sentinel-1 resolution)

5. QUALITY:
   - Cloud Optimized GeoTIFF (COG) enabled
   - Self-mask applied to remove no-data
   - Area calculations in m² and ha

6. CUSTOMIZATION:
   - Change dates in section 4 for different events
   - Adjust thresholds in sections 7-9 for different conditions
   - Modify ROI coordinates for different areas
*/
