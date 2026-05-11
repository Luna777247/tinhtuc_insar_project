"""
subsidence package - Cấp 1 + 2 xác định sụt lún
========================================================

Cấp 1: Proxy Detection (Backscatter Trend Analysis)
    - Phát hiện vùng biến động/bất ổn qua backscatter
    - Độ chính xác: qualitative
    - Dữ liệu: GEE GRD

Cấp 2: Offset Tracking
    - Dịch chuyển thô ~0.5m
    - Độ chính xác: ~0.5m (relative)
    - Dữ liệu: GEE GRD

Cấp 3: SBAS-InSAR (External)
    - Đo chính xác mm-cm
    - ASF HyP3 + MintPy
    - Dữ liệu: SLC

Author: InSAR Team
"""

from .level1_proxy import ProxySubsidenceDetector
from .level2_offset import OffsetTrackingDetector
from .subsidence_integrator import SubsidenceIntegrator

__all__ = [
    "ProxySubsidenceDetector",
    "OffsetTrackingDetector", 
    "SubsidenceIntegrator"
]
