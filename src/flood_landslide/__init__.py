"""
Flood & Landslide Detection Module
==================================
Xử lý kết quả từ GEE cho kịch bản ngập lụt và sạt lở.

Kịch bản 1: Flood Mapping
- Change detection Sentinel-1 (VH backscatter)
- Consensus mask 3 track (Orbit 55, 91, 128)
- Adaptive threshold (μ - 1.5σ)

Kịch bản 2: Landslide Detection  
- Backscatter change detection
- Sentinel-2 NDVI confirmation
- Slope-based filtering

Kịch bản 4: Mine Waste Monitoring
- Multi-temporal change detection
- Alert system integration

Tham chiếu:
- Twele et al. (2016): Sentinel-1 flood mapping
- Bovenga et al. (2021): SAR landslide detection
"""

from .flood_detector import FloodDetector
from .landslide_detector import LandslideDetector
from .mine_monitor import MineWasteMonitor
from .risk_integrator import RiskIntegrator

__all__ = [
    'FloodDetector',
    'LandslideDetector', 
    'MineWasteMonitor',
    'RiskIntegrator'
]
