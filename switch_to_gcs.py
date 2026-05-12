"""
Chuyển đổi GEE Export từ Google Drive sang Google Cloud Storage
=================================================================

Service accounts không có Google Drive quota, cần dùng GCS.

Hướng dẫn setup GCS:
1. Vào https://console.cloud.google.com/storage
2. Tạo bucket (ví dụ: tinhtuc-insar-results)
3. Cấp quyền cho service account: Storage Object Admin

Usage:
    python switch_to_gcs.py --bucket tinhtuc-insar-results
"""

import json
import sys
from pathlib import Path

# Update GEE scripts to use GCS instead of Drive
GEE_SCRIPTS_DIR = Path("gee_scripts")

def update_script_to_gcs(script_path: Path, bucket_name: str):
    """Chuyển đổi script từ Drive sang GCS."""
    
    with open(script_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Thay thế Drive export bằng GCS export
    # Old: Export.image.toDrive({folder: 'TinhTuc_GEE_Results'})
    # New: Export.image.toCloudStorage({bucket: 'bucket-name'})
    
    changes = []
    
    # Check if already using GCS
    if 'toCloudStorage' in content:
        print(f"   ℹ️  {script_path.name} already using GCS")
        return False
    
    # Replace toDrive with toCloudStorage
    if 'Export.image.toDrive' in content:
        content = content.replace(
            'Export.image.toDrive',
            'Export.image.toCloudStorage'
        )
        changes.append("Export.image.toDrive → toCloudStorage")
    
    if 'Export.table.toDrive' in content:
        content = content.replace(
            'Export.table.toDrive',
            'Export.table.toCloudStorage'
        )
        changes.append("Export.table.toDrive → toCloudStorage")
    
    # Replace folder with bucket
    if 'folder:' in content and 'bucket:' not in content:
        content = content.replace(
            "folder: 'TinhTuc_GEE_Results'",
            f"bucket: '{bucket_name}'"
        )
        content = content.replace(
            'folder: "TinhTuc_GEE_Results"',
            f'bucket: "{bucket_name}"'
        )
        changes.append(f"folder → bucket: {bucket_name}")
    
    if changes:
        # Backup
        backup_path = script_path.with_suffix('.drive.js')
        if not backup_path.exists():
            script_path.rename(backup_path)
            script_path.write_text(content, encoding='utf-8')
            print(f"   ✅ Updated {script_path.name}:")
            for c in changes:
                print(f"      - {c}")
            return True
    
    return False

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Switch GEE exports to GCS')
    parser.add_argument('--bucket', default='tinhtuc-insar-results',
                       help='GCS bucket name')
    parser.add_argument('--restore', action='store_true',
                       help='Restore Drive version')
    
    args = parser.parse_args()
    
    if args.restore:
        # Restore from backup
        for backup in GEE_SCRIPTS_DIR.glob('*.drive.js'):
            original = backup.with_suffix('').with_suffix('.js')
            if original.exists():
                original.unlink()
            backup.rename(original)
            print(f"✅ Restored {original.name}")
        return
    
    print(f"🔧 Converting GEE scripts to use GCS bucket: {args.bucket}\n")
    
    updated = 0
    for script in GEE_SCRIPTS_DIR.glob('*.js'):
        if update_script_to_gcs(script, args.bucket):
            updated += 1
    
    print(f"\n📊 Updated {updated} scripts")
    
    if updated > 0:
        print(f"\n⚠️  Lưu ý:")
        print(f"   1. Bạn cần tạo GCS bucket: {args.bucket}")
        print(f"   2. Cấp quyền Storage Object Admin cho service account")
        print(f"   3. Chạy lại pipeline: python run_pipeline_gee.py --all")
        print(f"\n📚 Hướng dẫn tạo bucket:")
        print(f"   https://console.cloud.google.com/storage/create-bucket")
        print(f"   Bucket name: {args.bucket}")
        print(f"   Location: asia-southeast1 (Singapore - gần Việt Nam)")
        print(f"   Storage class: Standard")

if __name__ == '__main__':
    main()
