"""
Migrate Outputs - Chuyển đổi cấu trúc cũ sang mới
=================================================

Chuyển các file gee_run_report_*.json cũ sang cấu trúc thư mục theo thời gian.

Usage:
    python migrate_outputs.py [--dry-run]
"""

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

OUTPUTS_DIR = Path("outputs")
GEE_RESULTS_DIR = OUTPUTS_DIR / "gee_results"

def parse_timestamp_from_filename(filename: str) -> datetime:
    """Trích xuất timestamp từ tên file (gee_run_report_YYYYMMDD_HHMMSS.json)."""
    try:
        # Format: gee_run_report_20260512_022237.json
        parts = filename.stem.split('_')
        if len(parts) >= 5:
            date_str = parts[3]  # YYYYMMDD
            time_str = parts[4]  # HHMMSS
            return datetime.strptime(f"{date_str}_{time_str}", "%Y%m%d_%H%M%S")
    except (IndexError, ValueError):
        pass
    
    # Fallback: dùng mtime
    return None

def migrate_old_reports(dry_run: bool = False):
    """Chuyển các report cũ sang cấu trúc mới."""
    if not GEE_RESULTS_DIR.exists():
        print("No gee_results directory found")
        return
    
    old_reports = list(GEE_RESULTS_DIR.glob("gee_run_report_*.json"))
    
    if not old_reports:
        print("No old reports to migrate")
        return
    
    print(f"Found {len(old_reports)} old reports to migrate\n")
    
    migrated = 0
    
    for old_file in sorted(old_reports, key=lambda p: p.stat().st_mtime):
        # Parse timestamp
        timestamp = parse_timestamp_from_filename(old_file)
        if timestamp is None:
            timestamp = datetime.fromtimestamp(old_file.stat().st_mtime)
        
        # Tạo cấu trúc thư mục mới
        daily_dir = GEE_RESULTS_DIR / timestamp.strftime("%Y-%m-%d")
        run_dir = daily_dir / f"run_{timestamp.strftime('%H%M%S')}"
        
        if dry_run:
            print(f"[DRY RUN] Would migrate:")
            print(f"  From: {old_file}")
            print(f"  To: {run_dir}/report.json")
            continue
        
        # Đọc và chuyển đổi
        try:
            with open(old_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Tạo thư mục
            run_dir.mkdir(parents=True, exist_ok=True)
            
            # Lưu dưới dạng mới
            new_file = run_dir / "report.json"
            with open(new_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, default=str)
            
            # Tạo exports.log
            exports_log = run_dir / "exports.log"
            exports = []
            for task in data.get('tasks', []):
                exports.extend(task.get('exports', []))
            
            exports_log.write_text(
                f"GEE Export Tasks - {timestamp.isoformat()}\n" +
                f"Google Drive: TinhTuc_GEE_Results/\n" +
                "\n".join([f"- {e}" for e in exports]),
                encoding='utf-8'
            )
            
            # Xóa file cũ
            old_file.unlink()
            
            migrated += 1
            print(f"✅ Migrated: {old_file.name} → {run_dir}/")
            
        except Exception as e:
            print(f"❌ Failed to migrate {old_file}: {e}")
    
    print(f"\n📊 Migration complete: {migrated}/{len(old_reports)} files migrated")
    
    if not dry_run and migrated > 0:
        print(f"\n💡 New structure:")
        print(f"  outputs/gee_results/YYYY-MM-DD/run_HHMMSS/")
        print(f"    ├── report.json")
        print(f"    └── exports.log")

def main():
    parser = argparse.ArgumentParser(description='Migrate outputs to new structure')
    parser.add_argument('--dry-run', action='store_true', help='Preview without changes')
    
    args = parser.parse_args()
    
    migrate_old_reports(dry_run=args.dry_run)

if __name__ == '__main__':
    main()
