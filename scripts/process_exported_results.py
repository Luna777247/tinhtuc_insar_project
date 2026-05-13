#!/usr/bin/env python3
"""
Process exported flood and landslide results from GEE
Handles both GeoTIFF (raster) and GeoJSON (vector) outputs
"""

import os
import geopandas as gpd
import rasterio
from rasterio import features
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from shapely.geometry import shape
import json
from pathlib import Path

class FloodLandslideProcessor:
    def __init__(self, base_path="exports"):
        self.base_path = Path(base_path)
        self.results = {}
        
    def load_geotiff(self, filepath):
        """Load GeoTIFF raster file"""
        with rasterio.open(filepath) as src:
            data = src.read(1)  # Read first band
            transform = src.transform
            crs = src.crs
            profile = src.profile
            
        return {
            'data': data,
            'transform': transform,
            'crs': crs,
            'profile': profile,
            'nodata': src.nodata
        }
    
    def load_geojson(self, filepath):
        """Load GeoJSON vector file"""
        gdf = gpd.read_file(filepath)
        return gdf
    
    def load_metadata(self, filepath):
        """Load processing metadata CSV"""
        df = pd.read_csv(filepath)
        return df.iloc[0].to_dict() if len(df) > 0 else {}
    
    def calculate_raster_stats(self, raster_data):
        """Calculate statistics for raster data"""
        data = raster_data['data']
        
        # Remove nodata values
        if raster_data['nodata'] is not None:
            data = data[data != raster_data['nodata']]
        
        stats = {
            'total_pixels': len(data),
            'positive_pixels': np.sum(data > 0),
            'pixel_area_m2': 10 * 10,  # 10m resolution
            'total_area_m2': np.sum(data > 0) * 100,
            'total_area_ha': np.sum(data > 0) * 100 / 10000,
            'coverage_percent': (np.sum(data > 0) / len(data)) * 100
        }
        
        return stats
    
    def calculate_vector_stats(self, gdf):
        """Calculate statistics for vector data"""
        if gdf.empty:
            return {
                'total_polygons': 0,
                'total_area_m2': 0,
                'total_area_ha': 0,
                'mean_area_m2': 0,
                'max_area_m2': 0,
                'min_area_m2': 0
            }
        
        # Convert to metric CRS if needed (assuming WGS84)
        if gdf.crs != 'EPSG:3857':
            gdf = gdf.to_crs('EPSG:3857')
        
        areas = gdf.geometry.area
        
        stats = {
            'total_polygons': len(gdf),
            'total_area_m2': areas.sum(),
            'total_area_ha': areas.sum() / 10000,
            'mean_area_m2': areas.mean(),
            'max_area_m2': areas.max(),
            'min_area_m2': areas.min(),
            'std_area_m2': areas.std()
        }
        
        return stats
    
    def create_visualization(self, flood_raster, landslide_raster, output_path):
        """Create visualization of both raster results"""
        fig, axes = plt.subplots(1, 2, figsize=(15, 6))
        
        # Flood mask
        axes[0].imshow(flood_raster['data'], cmap='Blues', interpolation='nearest')
        axes[0].set_title('Flood Mask')
        axes[0].set_xlabel('Pixel X')
        axes[0].set_ylabel('Pixel Y')
        
        # Landslide mask
        axes[1].imshow(landslide_raster['data'], cmap='Reds', interpolation='nearest')
        axes[1].set_title('Landslide Mask')
        axes[1].set_xlabel('Pixel X')
        axes[1].set_ylabel('Pixel Y')
        
        plt.tight_layout()
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        return output_path
    
    def generate_report(self, flood_stats, landslide_stats, metadata):
        """Generate comprehensive report"""
        report = {
            'processing_info': metadata,
            'flood_detection': {
                'raster_stats': flood_stats['raster'],
                'vector_stats': flood_stats['vector'],
                'agreement': self.calculate_agreement(flood_stats)
            },
            'landslide_detection': {
                'raster_stats': landslide_stats['raster'],
                'vector_stats': landslide_stats['vector'],
                'agreement': self.calculate_agreement(landslide_stats)
            },
            'quality_metrics': self.calculate_quality_metrics(flood_stats, landslide_stats)
        }
        
        return report
    
    def calculate_agreement(self, stats):
        """Calculate agreement between raster and vector results"""
        raster_area = stats['raster']['total_area_ha']
        vector_area = stats['vector']['total_area_ha']
        
        if raster_area == 0:
            return {'agreement_percent': 0, 'difference_ha': vector_area}
        
        agreement = (1 - abs(raster_area - vector_area) / raster_area) * 100
        
        return {
            'agreement_percent': agreement,
            'raster_area_ha': raster_area,
            'vector_area_ha': vector_area,
            'difference_ha': abs(raster_area - vector_area)
        }
    
    def calculate_quality_metrics(self, flood_stats, landslide_stats):
        """Calculate quality metrics"""
        return {
            'flood_polygon_count': flood_stats['vector']['total_polygons'],
            'landslide_polygon_count': landslide_stats['vector']['total_polygons'],
            'flood_coverage_percent': flood_stats['raster']['coverage_percent'],
            'landslide_coverage_percent': landslide_stats['raster']['coverage_percent'],
            'total_affected_area_ha': flood_stats['raster']['total_area_ha'] + landslide_stats['raster']['total_area_ha']
        }
    
    def process_exports(self, export_date="20250812"):
        """Main processing function"""
        print(f"Processing exports for date: {export_date}")
        
        # File paths
        flood_raster_path = self.base_path / f"flood_mask_{export_date}_uint8.tif"
        landslide_raster_path = self.base_path / f"landslide_mask_{export_date}_uint8.tif"
        flood_vector_path = self.base_path / f"flood_polygons_{export_date}.geojson"
        landslide_vector_path = self.base_path / f"landslide_polygons_{export_date}.geojson"
        metadata_path = self.base_path / f"flood_landslide_metadata_{export_date}.csv"
        
        # Load data
        print("Loading raster data...")
        flood_raster = self.load_geotiff(flood_raster_path)
        landslide_raster = self.load_geotiff(landslide_raster_path)
        
        print("Loading vector data...")
        flood_vector = self.load_geojson(flood_vector_path)
        landslide_vector = self.load_geojson(landslide_vector_path)
        
        print("Loading metadata...")
        metadata = self.load_metadata(metadata_path)
        
        # Calculate statistics
        print("Calculating statistics...")
        flood_stats = {
            'raster': self.calculate_raster_stats(flood_raster),
            'vector': self.calculate_vector_stats(flood_vector)
        }
        
        landslide_stats = {
            'raster': self.calculate_raster_stats(landslide_raster),
            'vector': self.calculate_vector_stats(landslide_vector)
        }
        
        # Create visualization
        print("Creating visualization...")
        viz_path = self.base_path / f"flood_landslide_comparison_{export_date}.png"
        self.create_visualization(flood_raster, landslide_raster, viz_path)
        
        # Generate report
        print("Generating report...")
        report = self.generate_report(flood_stats, landslide_stats, metadata)
        
        # Save results
        output_path = self.base_path / f"processing_report_{export_date}.json"
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Print summary
        print("\n" + "="*50)
        print("PROCESSING SUMMARY")
        print("="*50)
        print(f"Flood Area (Raster): {flood_stats['raster']['total_area_ha']:.2f} ha")
        print(f"Flood Area (Vector): {flood_stats['vector']['total_area_ha']:.2f} ha")
        print(f"Flood Polygons: {flood_stats['vector']['total_polygons']}")
        print(f"Landslide Area (Raster): {landslide_stats['raster']['total_area_ha']:.2f} ha")
        print(f"Landslide Area (Vector): {landslide_stats['vector']['total_area_ha']:.2f} ha")
        print(f"Landslide Polygons: {landslide_stats['vector']['total_polygons']}")
        print(f"Total Affected Area: {report['quality_metrics']['total_affected_area_ha']:.2f} ha")
        print(f"Visualization saved: {viz_path}")
        print(f"Report saved: {output_path}")
        
        return report

def main():
    """Main execution function"""
    processor = FloodLandslideProcessor()
    
    # Process the most recent export
    report = processor.process_exports("20250812")
    
    return report

if __name__ == "__main__":
    main()
