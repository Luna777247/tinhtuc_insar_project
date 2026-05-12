#!/usr/bin/env python
"""
Manage Outputs - CLI tool quản lý outputs
==========================================

Usage:
    python manage_outputs.py --stats              # Xem thống kê
    python manage_outputs.py --cleanup          # Dọn dẹp reports cũ
    python manage_outputs.py --cleanup --dry-run # Xem trước khi xóa
    python manage_outputs.py --compress         # Nén dữ liệu lớn
    python manage_outputs.py --backup           # Backup reports
    python manage_outputs.py --all              # Chạy tất cả
"""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

from src.utils.output_manager import main

if __name__ == '__main__':
    main()
