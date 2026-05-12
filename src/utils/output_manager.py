"""
Output Manager - Quản lý và tổ chức kết quả outputs
==================================================

Tính năng:
- Tổ chức outputs theo cấu trúc thời gian
- Tự động dọn dẹp reports cũ
- Nén dữ liệu lớn
- Backup tự động

Usage:
    from src.utils.output_manager import OutputManager
    
    manager = OutputManager()
    manager.cleanup_old_reports(max_gee_reports=5, max_age_days=30)
    report_path = manager.save_gee_report(results)
"""

from __future__ import annotations

import gzip
import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class OutputManager:
    """Quản lý outputs với cấu trúc thời gian và tự động dọn dẹp."""
    
    def __init__(self, root_dir: Optional[Path] = None):
        self.root = root_dir or Path(__file__).resolve().parent.parent.parent / "outputs"
        self.root.mkdir(parents=True, exist_ok=True)
        
        # Cấu trúc thư mục
        self.gee_dir = self.root / "gee_results"
        self.archive_dir = self.root / "archive"
        self.compressed_dir = self.root / "compressed"
        
        # Tạo thư mục nếu chưa có
        for d in [self.gee_dir, self.archive_dir, self.compressed_dir]:
            d.mkdir(exist_ok=True)
    
    def get_daily_dir(self, timestamp: Optional[datetime] = None) -> Path:
        """Lấy hoặc tạo thư mục theo ngày."""
        if timestamp is None:
            timestamp = datetime.now()
        
        daily_dir = self.gee_dir / timestamp.strftime("%Y-%m-%d")
        daily_dir.mkdir(exist_ok=True)
        return daily_dir
    
    def get_run_dir(self, timestamp: Optional[datetime] = None) -> Path:
        """Lấy hoặc tạo thư mục cho mỗi lần chạy."""
        daily_dir = self.get_daily_dir(timestamp)
        
        if timestamp is None:
            timestamp = datetime.now()
        
        run_name = f"run_{timestamp.strftime('%H%M%S')}"
        run_dir = daily_dir / run_name
        run_dir.mkdir(exist_ok=True)
        
        # Tạo symlink latest trong daily_dir
        latest_link = daily_dir / "latest"
        if latest_link.exists() or latest_link.is_symlink():
            latest_link.unlink()
        
        try:
            latest_link.symlink_to(run_dir, target_is_directory=True)
        except (OSError, NotImplementedError):
            # Windows có thể cần admin để tạo symlink
            # Fallback: tạo file text chỉ đường
            latest_file = daily_dir / "latest.txt"
            latest_file.write_text(str(run_dir), encoding='utf-8')
        
        return run_dir
    
    def save_gee_report(
        self,
        results: Dict,
        timestamp: Optional[datetime] = None,
        compress: bool = False
    ) -> Path:
        """Lưu báo cáo GEE với cấu trúc thời gian."""
        if timestamp is None:
            timestamp = datetime.now()
        
        run_dir = self.get_run_dir(timestamp)
        
        # Lưu report.json
        report_path = run_dir / "report.json"
        report_path.write_text(
            json.dumps(results, indent=2, default=str),
            encoding='utf-8'
        )
        
        # Tạo exports.log
        exports = []
        for r in results.get('tasks', []):
            exports.extend(r.get('exports', []))
        
        exports_log = run_dir / "exports.log"
        exports_log.write_text(
            f"GEE Export Tasks - {timestamp.isoformat()}\n" +
            f"Google Drive: TinhTuc_GEE_Results/\n" +
            "\n".join([f"- {e}" for e in exports]),
            encoding='utf-8'
        )
        
        # Nén nếu yêu cầu
        if compress:
            compressed_path = self.compress_file(report_path)
            return compressed_path
        
        logger.info(f"💾 Report saved: {report_path}")
        return report_path
    
    def cleanup_old_reports(
        self,
        max_gee_reports: int = 5,
        max_age_days: int = 30,
        dry_run: bool = False
    ) -> List[Path]:
        """Dọn dẹp reports cũ."""
        deleted = []
        cutoff_date = datetime.now() - timedelta(days=max_age_days)
        
        # 1. Dọn trong gee_results/
        if self.gee_dir.exists():
            # Tìm tất cả report.json
            all_reports = sorted(
                self.gee_dir.rglob("report.json"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            
            # Giữ max_gee_reports mới nhất
            reports_to_keep = all_reports[:max_gee_reports]
            reports_to_delete = all_reports[max_gee_reports:]
            
            for report_path in reports_to_delete:
                # Kiểm tra tuổi file
                mtime = datetime.fromtimestamp(report_path.stat().st_mtime)
                
                if mtime < cutoff_date:
                    if not dry_run:
                        # Xóa cả thư mục run
                        run_dir = report_path.parent
                        shutil.rmtree(run_dir, ignore_errors=True)
                        logger.info(f"🗑️  Deleted old run: {run_dir}")
                    else:
                        logger.info(f"[DRY RUN] Would delete: {report_path.parent}")
                    
                    deleted.append(report_path)
        
        # 2. Dọn các file JSON cũ trong gee_results/ (backward compat)
        old_json_files = list(self.gee_dir.glob("gee_run_report_*.json"))
        old_json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        for old_file in old_json_files[max_gee_reports:]:
            mtime = datetime.fromtimestamp(old_file.stat().st_mtime)
            
            if mtime < cutoff_date:
                if not dry_run:
                    old_file.unlink()
                    logger.info(f"🗑️  Deleted old report: {old_file.name}")
                else:
                    logger.info(f"[DRY RUN] Would delete: {old_file.name}")
                
                deleted.append(old_file)
        
        # 3. Dọn summary files trong reports/
        reports_dir = self.root / "reports"
        if reports_dir.exists():
            summary_files = list(reports_dir.glob("summary_*.txt"))
            summary_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            
            # Giữ 1 file mới nhất mỗi ngày
            daily_keep = {}
            for f in summary_files:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                date_key = mtime.strftime("%Y-%m-%d")
                
                if date_key not in daily_keep:
                    daily_keep[date_key] = f
            
            files_to_delete = set(summary_files) - set(daily_keep.values())
            
            for f in files_to_delete:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                
                if mtime < cutoff_date:
                    if not dry_run:
                        f.unlink()
                        logger.info(f"🗑️  Deleted summary: {f.name}")
                    else:
                        logger.info(f"[DRY RUN] Would delete: {f.name}")
                    
                    deleted.append(f)
        
        logger.info(f"📊 Cleanup complete: {len(deleted)} files removed")
        return deleted
    
    def compress_file(self, file_path: Path, remove_original: bool = False) -> Path:
        """Nén file bằng gzip."""
        compressed_path = self.compressed_dir / f"{file_path.name}.gz"
        
        with open(file_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        if remove_original:
            file_path.unlink()
        
        # Tính tỷ lệ nén
        original_size = file_path.stat().st_size
        compressed_size = compressed_path.stat().st_size
        ratio = (1 - compressed_size / original_size) * 100
        
        logger.info(f"🗜️  Compressed: {file_path.name} ({ratio:.1f}% smaller)")
        
        return compressed_path
    
    def compress_numpy_files(self, max_size_mb: float = 1.0) -> List[Path]:
        """Nén các file .npy lớn thành .npz."""
        compressed = []
        max_size_bytes = max_size_mb * 1024 * 1024
        
        for npy_file in self.root.rglob("*.npy"):
            size = npy_file.stat().st_size
            
            if size > max_size_bytes:
                # Đọc và nén
                data = np.load(npy_file)
                npz_file = npy_file.with_suffix('.npz')
                
                np.savez_compressed(npz_file, data=data)
                
                # Backup file gốc vào archive
                archive_path = self.archive_dir / npy_file.name
                shutil.move(str(npy_file), str(archive_path))
                
                compressed.append(npz_file)
                
                ratio = (1 - npz_file.stat().st_size / size) * 100
                logger.info(f"🗜️  Compressed: {npy_file.name} → {npz_file.name} ({ratio:.1f}% smaller)")
        
        return compressed
    
    def backup_important_reports(self) -> List[Path]:
        """Backup reports quan trọng sang archive/."""
        backed_up = []
        
        # Các file quan trọng cần backup
        important_patterns = [
            "bao_cao_nghien_cuu.md",
            "bao_cao_nguy_co_ngap_lut_*.md",
            "gee_run_report_*.json"
        ]
        
        reports_dir = self.root / "reports"
        
        for pattern in important_patterns:
            for file_path in reports_dir.glob(pattern):
                backup_path = self.archive_dir / file_path.name
                
                if not backup_path.exists():
                    shutil.copy2(file_path, backup_path)
                    backed_up.append(backup_path)
                    logger.info(f"💾 Backed up: {file_path.name}")
        
        # Backup file GEE mới nhất
        latest_gee = self.get_latest_gee_report()
        if latest_gee:
            backup_path = self.archive_dir / f"backup_{latest_gee.name}"
            if not backup_path.exists():
                shutil.copy2(latest_gee, backup_path)
                backed_up.append(backup_path)
        
        logger.info(f"📦 Backup complete: {len(backed_up)} files")
        return backed_up
    
    def get_latest_gee_report(self) -> Optional[Path]:
        """Lấy báo cáo GEE mới nhất."""
        all_reports = []
        
        # Tìm trong cấu trúc mới
        for report_path in self.gee_dir.rglob("report.json"):
            all_reports.append((report_path, report_path.stat().st_mtime))
        
        # Tìm trong cấu trúc cũ
        for report_path in self.gee_dir.glob("gee_run_report_*.json"):
            all_reports.append((report_path, report_path.stat().st_mtime))
        
        if not all_reports:
            return None
        
        # Sắp xếp theo thời gian, lấy mới nhất
        all_reports.sort(key=lambda x: x[1], reverse=True)
        return all_reports[0][0]
    
    def get_storage_stats(self) -> Dict:
        """Thống kê dung lượng lưu trữ."""
        stats = {
            'total_size_mb': 0,
            'gee_results_mb': 0,
            'reports_mb': 0,
            'compressed_mb': 0,
            'archive_mb': 0,
            'file_counts': {}
        }
        
        def dir_size(path: Path) -> float:
            total = 0
            for f in path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
            return total / (1024 * 1024)  # MB
        
        stats['total_size_mb'] = dir_size(self.root)
        stats['gee_results_mb'] = dir_size(self.gee_dir)
        stats['reports_mb'] = dir_size(self.root / "reports")
        stats['compressed_mb'] = dir_size(self.compressed_dir)
        stats['archive_mb'] = dir_size(self.archive_dir)
        
        # Đếm files
        stats['file_counts']['gee_reports'] = len(list(self.gee_dir.rglob("report.json")))
        stats['file_counts']['npy_files'] = len(list(self.root.rglob("*.npy")))
        stats['file_counts']['compressed'] = len(list(self.compressed_dir.glob("*")))
        
        return stats


def main():
    """CLI cho output manager."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Output Manager CLI')
    parser.add_argument('--cleanup', action='store_true', help='Dọn dẹp reports cũ')
    parser.add_argument('--compress', action='store_true', help='Nén dữ liệu lớn')
    parser.add_argument('--backup', action='store_true', help='Backup reports')
    parser.add_argument('--stats', action='store_true', help='Hiển thị thống kê')
    parser.add_argument('--dry-run', action='store_true', help='Chỉ hiển thị, không xóa')
    parser.add_argument('--max-reports', type=int, default=5, help='Số reports tối đa')
    parser.add_argument('--max-age', type=int, default=30, help='Tuổi tối đa (ngày)')
    
    args = parser.parse_args()
    
    manager = OutputManager()
    
    if args.stats:
        stats = manager.get_storage_stats()
        print("\n📊 Storage Statistics:")
        print(f"   Total: {stats['total_size_mb']:.2f} MB")
        print(f"   GEE Results: {stats['gee_results_mb']:.2f} MB")
        print(f"   Reports: {stats['reports_mb']:.2f} MB")
        print(f"   Compressed: {stats['compressed_mb']:.2f} MB")
        print(f"   Archive: {stats['archive_mb']:.2f} MB")
        print(f"\n   File counts: {stats['file_counts']}")
    
    if args.cleanup:
        deleted = manager.cleanup_old_reports(
            max_gee_reports=args.max_reports,
            max_age_days=args.max_age,
            dry_run=args.dry_run
        )
        print(f"\n🗑️  Cleaned up: {len(deleted)} files")
    
    if args.compress:
        compressed = manager.compress_numpy_files()
        print(f"\n🗜️  Compressed: {len(compressed)} files")
    
    if args.backup:
        backed_up = manager.backup_important_reports()
        print(f"\n💾 Backed up: {len(backed_up)} files")


if __name__ == '__main__':
    main()
