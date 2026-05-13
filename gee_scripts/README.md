# GEE Scripts - Tĩnh Túc InSAR Project

## 📁 Directory Structure

```
gee_scripts/
├── 📄 Unified Analysis Scripts
│   ├── 05_flood_landslide_monitoring_unified.js
│   ├── 06_flood_event_20250929_1001_unified.js
│   ├── 07_subsidence_proxy_level1_unified.js
│   ├── 08_statistical_analysis_float_unified.js
│   └── 09_primary_orbit55_analysis_unified.js
├── 📄 Export Scripts
│   └── export_flood_landslide_both_formats.js
├── 📁 templates/
│   ├── 01_sentinel1_acquisition.template.js
│   └── 03_optical_landslide.template.js
└── 📁 generated/
    ├── 01_sentinel1_acquisition.js
    └── 03_optical_landslide.js
```

## 🚀 Unified Scripts Features

### ✅ **Dual Export Options**
- **Google Drive**: `exportToDrive()` function
- **Google Cloud Storage**: `exportToCloudStorage()` function
- **Easy switching**: Comment/uncomment desired export method

### ✅ **Comprehensive Analysis**
1. **05_flood_landslide_monitoring_unified.js**
   - Flood detection with multi-orbit consensus
   - Landslide detection with NDVI validation
   - Mine waste monitoring
   - Risk mapping

2. **06_flood_event_20250929_1001_unified.js**
   - Specific event analysis (28/09 - 01/10/2025)
   - Dual-orbit change detection
   - Adaptive thresholding
   - Consensus mapping

3. **07_subsidence_proxy_level1_unified.js**
   - Long-term trend analysis (2015-2026)
   - Stability index computation
   - Hotspot detection
   - Statistical quality metrics

4. **08_statistical_analysis_float_unified.js**
   - Gamma distribution analysis
   - ENL (Equivalent Number of Looks)
   - Chi-square change detection
   - Temporal variance

5. **09_primary_orbit55_analysis_unified.js**
   - Orbit 55 comprehensive analysis
   - Multi-orbit comparison
   - Time series trends
   - Seasonal patterns

## 🔧 Usage Instructions

### 1. **Choose Script**
Select appropriate unified script based on analysis needs.

### 2. **Configure Export Method**
```javascript
// CHỌN MỘT TRONG HAI:
// 1. exportToDrive();     // Xuất ra Google Drive
// 2. exportToCloudStorage(); // Xuất ra Google Cloud Storage

// Mặc định: Uncomment dòng muốn chạy
exportToDrive();
// exportToCloudStorage();
```

### 3. **Run in GEE**
1. Copy script content
2. Paste in [Google Earth Engine Code Editor](https://code.earthengine.google.com)
3. Run script
4. Check Tasks tab for exports

## 📊 Export Products

### **Raster (GeoTIFF)**
- Flood masks (uint8)
- Landslide masks (uint8)
- Trend analysis (float32)
- Statistical maps (float32)
- Risk maps (uint8)

### **Vector (GeoJSON)**
- Flood polygons
- Landslide polygons
- Hotspot polygons
- Time series data (CSV)

### **Metadata (CSV)**
- Processing parameters
- Statistical results
- Quality metrics
- Area calculations

## 🎯 Key Features

### **Multi-Orbit Analysis**
- **Orbit 55 (ASC)**: Primary - 544 images (48%)
- **Orbit 91 (DESC)**: Secondary - 320 images (28%)
- **Orbit 128 (ASC)**: Tertiary - 269 images (24%)

### **Adaptive Thresholding**
- Dynamic threshold calculation
- Statistical significance testing
- Region-specific optimization

### **Quality Control**
- Speckle filtering
- Terrain correction
- Water body masking
- Urban area exclusion

### **Validation**
- Cross-orbit consensus
- Multi-sensor validation (S2 NDVI)
- Statistical confidence metrics

## 📈 Analysis Levels

| Level | Method | Accuracy | Data Source | Purpose |
|-------|---------|-----------|-------------|---------|
| **Level 1** | Proxy Detection | Qualitative | Screening, hotspot identification |
| **Level 2** | Change Detection | Semi-quantitative | Event monitoring, trend analysis |
| **Level 3** | SBAS-InSAR | Quantitative (mm) | Precise deformation measurement |

## 🔒 Important Notes

### **Data Limitations**
- GEE provides **GRD only** (no SLC)
- **No phase information** → No true InSAR
- **10m resolution** limitation
- **Temporal gaps** possible

### **Best Practices**
1. **Always use same orbit** for change detection
2. **Apply terrain masking** for mountainous areas
3. **Use adaptive thresholds** for different conditions
4. **Validate with multiple data sources**
5. **Document processing parameters**

### **Export Recommendations**
- **Cloud Optimized GeoTIFF (COG)** for web applications
- **GeoJSON** for vector analysis
- **CSV** for time series and metadata
- **Scale**: 10m for analysis, 30m for regional

## 📞 Support

For questions or issues:
1. Check GEE console for error messages
2. Verify ROI coordinates
3. Ensure sufficient data coverage
4. Review processing parameters

---
**Last Updated**: 2026-05-12
**Project**: Tĩnh Túc InSAR, Cao Bằng
**Data Source**: Sentinel-1 GRD (2015-2026)
