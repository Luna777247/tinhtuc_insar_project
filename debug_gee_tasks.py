"""
Debug GEE Tasks - Kiểm tra lý do FAILED
=======================================

Usage:
    python debug_gee_tasks.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import ee

GEE_KEY_PATH = Path("gee_scripts/gee-private-key.json")
GEE_RESULTS_DIR = Path("outputs/gee_results")

def initialize_ee():
    """Initialize GEE."""
    credentials = ee.ServiceAccountCredentials(None, str(GEE_KEY_PATH))
    ee.Initialize(credentials)
    return ee

def find_latest_report():
    """Tìm report mới nhất."""
    reports = list(GEE_RESULTS_DIR.rglob("report.json"))
    if not reports:
        reports = list(GEE_RESULTS_DIR.glob("gee_run_report_*.json"))
    return max(reports, key=lambda p: p.stat().st_mtime) if reports else None

def debug_tasks():
    """Debug chi tiết lỗi từng task."""
    print("🔍 Debug GEE Tasks\n")
    
    report_path = find_latest_report()
    if not report_path:
        print("❌ Không tìm thấy report")
        return
    
    print(f"📄 Report: {report_path}\n")
    
    with open(report_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    tasks = data.get('tasks', [])
    
    if not tasks:
        print("⚠️  Không có tasks")
        return
    
    try:
        ee = initialize_ee()
    except Exception as e:
        print(f"❌ Lỗi kết nối GEE: {e}")
        return
    
    print("📋 Chi tiết lỗi:")
    print("=" * 70)
    
    for task in tasks:
        task_id = task.get('id')
        task_name = task.get('name', 'Unknown')
        
        if not task_id:
            print(f"\n⚠️  {task_name}: Không có task ID")
            continue
        
        try:
            status_info = ee.data.getTaskStatus(task_id)[0]
            state = status_info.get('state', 'UNKNOWN')
            
            print(f"\n📝 {task_name}")
            print(f"   ID: {task_id}")
            print(f"   Status: {state}")
            
            if state == 'FAILED':
                error_msg = status_info.get('error_message', 'Không có thông tin lỗi')
                print(f"   ❌ ERROR: {error_msg}")
                
                # Phân tích lỗi phổ biến
                if 'geometry' in error_msg.lower():
                    print(f"   💡 Gợi ý: Vấn đề với ROI geometry - thử đơn giản hóa polygon")
                elif 'quota' in error_msg.lower() or 'limit' in error_msg.lower():
                    print(f"   💡 Gợi ý: Hết quota GEE - đợi 24h hoặc giảm vùng phân tích")
                elif 'memory' in error_msg.lower():
                    print(f"   💡 Gợi ý: Vùng quá lớn - thu nhỏ ROI hoặc giảm độ phân giải")
                elif 'timeout' in error_msg.lower():
                    print(f"   💡 Gợi ý: Task timeout - giảm phạm vi thời gian")
                elif 'band' in error_msg.lower():
                    print(f"   💡 Gợi ý: Lỗi band - kiểm tra tên band trong GEE script")
                    
            elif state == 'COMPLETED':
                destination = status_info.get('destination_uris', ['N/A'])
                print(f"   ✅ Completed: {destination}")
            
        except Exception as e:
            print(f"\n⚠️  {task_name}: Không thể lấy status - {e}")
    
    print("\n" + "=" * 70)
    print("\n💡 Các giải pháp thường gặp:")
    print("   1. Thu nhỏ ROI (dùng bounding box thay vì polygon chi tiết)")
    print("   2. Giảm phạm vi thời gian (6 tháng thay vì 5 năm)")
    print("   3. Kiểm tra lại GEE scripts trong thư mục gee_scripts/")
    print("   4. Đợi 24h nếu hết quota export")
    print("   5. Kiểm tra service account có quyền export không")

if __name__ == '__main__':
    debug_tasks()
