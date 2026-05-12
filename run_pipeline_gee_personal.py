"""
GEE Pipeline - Dùng tài khoản cá nhân (có Drive quota)
======================================================

Thay vì service account, dùng tài khoản Google cá nhân đã 
authenticate với Earth Engine.

Yêu cầu: 
- earthengine authenticate (chạy 1 lần)
- Tài khoản có Google Drive

Usage:
    python run_pipeline_gee_personal.py --all
"""

import sys
from pathlib import Path

# Copy từ run_pipeline_gee.py nhưng thay đổi phần initialize
# ... (simplified version)

if __name__ == '__main__':
    print("🚀 GEE Pipeline (Personal Account)")
    print("=" * 50)
    print("\n⚠️  Hướng dẫn:")
    print("   1. Chạy: earthengine authenticate")
    print("   2. Đăng nhập bằng tài khoản Google cá nhân")
    print("   3. Sau đó chạy: python run_pipeline_gee.py --all")
    print("\n💡 Hoặc dùng GCS:")
    print("   python switch_to_gcs.py --bucket your-bucket")
