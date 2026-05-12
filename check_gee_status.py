"""
Kiểm tra trạng thái GEE tasks và liệt kê kết quả trên Google Drive
==============================================================

Usage:
    python check_gee_status.py          # Check tất cả tasks gần đây
    python check_gee_status.py --latest # Check report mới nhất
"""

import json
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import ee

GEE_RESULTS_DIR = Path("outputs/gee_results")
GEE_KEY_PATH = Path("gee_scripts/gee-private-key.json")

def initialize_ee():
    """Initialize GEE với service account."""
    if not GEE_KEY_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy key: {GEE_KEY_PATH}")
    
    credentials = ee.ServiceAccountCredentials(
        None,
        str(GEE_KEY_PATH)
    )
    ee.Initialize(credentials)
    return ee


DRIVE_FOLDER = "TinhTuc_GEE_Results"

def find_latest_report():
    """Tìm report.json mới nhất."""
    reports = list(GEE_RESULTS_DIR.rglob("report.json"))
    if not reports:
        # Fallback: tìm file cũ
        reports = list(GEE_RESULTS_DIR.glob("gee_run_report_*.json"))
    
    if not reports:
        return None
    
    return max(reports, key=lambda p: p.stat().st_mtime)

def check_status(report_path: Path = None):
    """Kiểm tra status các GEE tasks."""
    print("🔍 Kiểm tra trạng thái GEE tasks\n")
    
    if report_path is None:
        report_path = find_latest_report()
    
    if not report_path or not report_path.exists():
        print("❌ Không tìm thấy báo cáo GEE nào!")
        print(f"   Hãy chạy: python run_pipeline_gee.py --all")
        return
    
    print(f"📄 Report: {report_path}\n")
    
    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = data.get('tasks', [])
    
    if not tasks:
        print("⚠️  Không có tasks nào trong báo cáo")
        return
    
    # Kiểm tra status qua GEE API
    try:
        ee = initialize_ee()
        
        print("📊 Trạng thái tasks:")
        print("-" * 60)
        
        all_completed = True
        
        for task in tasks:
            task_id = task.get('id')
            task_name = task.get('name', 'Unknown')
            
            if task_id:
                try:
                    gee_task = ee.data.getTaskStatus(task_id)[0]
                    status = gee_task['state']
                    
                    # Icon theo status
                    icon = {
                        'READY': '⏳',
                        'RUNNING': '🔄',
                        'COMPLETED': '✅',
                        'FAILED': '❌',
                        'CANCELLED': '🚫'
                    }.get(status, '❓')
                    
                    print(f"{icon} {task_name:20} | {status}")
                    
                    if status not in ['COMPLETED', 'FAILED', 'CANCELLED']:
                        all_completed = False
                        
                except Exception as e:
                    print(f"❓ {task_name:20} | Không kiểm tra được: {e}")
            else:
                print(f"⚠️  {task_name:20} | Không có task ID")
        
        print("-" * 60)
        
        if all_completed:
            print("\n✅ Tất cả tasks đã hoàn thành!")
            print(f"\n📁 Kết quả trong Google Drive folder: {DRIVE_FOLDER}")
            print("   Đang mở Google Drive...")
            
            # Mở Google Drive (tìm folder theo tên)
            webbrowser.open(f"https://drive.google.com/drive/search?q={DRIVE_FOLDER}")
        else:
            print("\n⏳ Một số tasks vẫn đang chạy...")
            print("   Hãy đợi thêm hoặc chạy lại script này sau vài phút.")
        
    except Exception as e:
        print(f"❌ Lỗi kết nối GEE: {e}")
        print(f"\n📁 Kết quả sẽ lưu trong Google Drive: {DRIVE_FOLDER}")
        print("   Tasks đang chạy: " + ", ".join([t.get('name', '?') for t in tasks]))

def list_drive_contents():
    """Liệt kê nội dung Google Drive folder (cần API)."""
    print("\n📂 Để xem nội dung TinhTuc_GEE_Results/:")
    print("   1. Vào https://drive.google.com")
    print("   2. Tìm folder: TinhTuc_GEE_Results")
    print("   Hoặc tìm các file bắt đầu bằng:")
    print("   - Flood_Orbit55_*")
    print("   - Stability_Orbit55_*")
    print("   - Orbit55_Metadata_*")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--latest', action='store_true', help='Check report mới nhất')
    parser.add_argument('--list', action='store_true', help='Hướng dẫn tìm folder')
    
    args = parser.parse_args()
    
    if args.list:
        list_drive_contents()
    else:
        check_status()
