#!/usr/bin/env python3
"""
日志清理工具 - Log Cleanup
定期清理过期日志文件，释放磁盘空间
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent))
from agent_logger import get_logger

log = get_logger("日志清理")


class LogCleaner:
    """日志清理器"""
    
    def __init__(self, workspace_path: Path = None):
        self.workspace = workspace_path or Path.home() / ".openclaw/workspace"
        self.log_dirs = [
            self.workspace / "logs",
            Path.home() / "Documents/OpenClawAgents/beifeng/logs",
            Path.home() / "Documents/OpenClawAgents/nanfeng/logs",
            Path.home() / "Documents/OpenClawAgents/baiban/logs",
        ]
    
    def scan_logs(self) -> Tuple[List[Path], int]:
        """
        扫描所有日志文件
        
        Returns:
            (日志文件列表, 总大小字节)
        """
        log_files = []
        total_size = 0
        
        for log_dir in self.log_dirs:
            if not log_dir.exists():
                continue
            
            for file_path in log_dir.glob("*.log"):
                if file_path.is_file():
                    log_files.append(file_path)
                    total_size += file_path.stat().st_size
        
        return log_files, total_size
    
    def cleanup(self, days: int = 7, dry_run: bool = False) -> dict:
        """
        清理过期日志
        
        Args:
            days: 保留天数，超过此天数的删除
            dry_run: 是否仅预览，不实际删除
        
        Returns:
            清理结果统计
        """
        cutoff_time = time.time() - (days * 24 * 3600)
        
        log_files, total_size = self.scan_logs()
        
        to_delete = []
        to_keep = []
        
        for file_path in log_files:
            mtime = file_path.stat().st_mtime
            if mtime < cutoff_time:
                to_delete.append(file_path)
            else:
                to_keep.append(file_path)
        
        # 统计
        delete_count = len(to_delete)
        delete_size = sum(f.stat().st_size for f in to_delete)
        keep_count = len(to_keep)
        keep_size = sum(f.stat().st_size for f in to_keep)
        
        result = {
            "scanned": len(log_files),
            "to_delete": delete_count,
            "delete_size_mb": delete_size / (1024 * 1024),
            "to_keep": keep_count,
            "keep_size_mb": keep_size / (1024 * 1024),
            "dry_run": dry_run
        }
        
        if dry_run:
            log.info(f"[预览] 将删除 {delete_count} 个文件, 释放 {delete_size/(1024*1024):.1f}MB")
        else:
            # 实际删除
            deleted = 0
            for file_path in to_delete:
                try:
                    file_path.unlink()
                    deleted += 1
                except Exception as e:
                    log.warning(f"删除失败 {file_path}: {e}")
            
            result["deleted"] = deleted
            log.success(f"已删除 {deleted} 个过期日志文件, 释放 {delete_size/(1024*1024):.1f}MB")
        
        return result
    
    def generate_report(self) -> str:
        """生成日志统计报告"""
        log_files, total_size = self.scan_logs()
        
        # 按日期分组
        by_date = {}
        for file_path in log_files:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            date_key = mtime.strftime('%Y-%m-%d')
            
            if date_key not in by_date:
                by_date[date_key] = {"count": 0, "size": 0}
            
            by_date[date_key]["count"] += 1
            by_date[date_key]["size"] += file_path.stat().st_size
        
        # 排序
        sorted_dates = sorted(by_date.keys(), reverse=True)
        
        report = f"""
🧹 日志清理报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

总体统计:
  日志文件总数: {len(log_files)}
  总大小: {total_size/(1024*1024):.1f} MB
  
按日期分布（最近7天）:
"""
        
        for date in sorted_dates[:7]:
            info = by_date[date]
            report += f"  {date}: {info['count']}个文件, {info['size']/(1024*1024):.1f}MB\n"
        
        # 计算7天前日志
        old_files = [f for f in log_files 
                     if f.stat().st_mtime < time.time() - 7*24*3600]
        old_size = sum(f.stat().st_size for f in old_files)
        
        report += f"\n可清理（7天前）:\n"
        report += f"  文件数: {len(old_files)}\n"
        report += f"  大小: {old_size/(1024*1024):.1f} MB\n"
        
        return report
    
    def auto_cleanup(self):
        """自动清理（保留7天）"""
        log.step("开始自动清理日志")
        result = self.cleanup(days=7, dry_run=False)
        return result


# 快捷函数
def cleanup_logs(days: int = 7, dry_run: bool = False) -> dict:
    """清理日志"""
    cleaner = LogCleaner()
    return cleaner.cleanup(days=days, dry_run=dry_run)

def show_log_report():
    """显示日志报告"""
    cleaner = LogCleaner()
    print(cleaner.generate_report())


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='日志清理工具')
    parser.add_argument('--days', type=int, default=7, help='保留天数')
    parser.add_argument('--dry-run', action='store_true', help='仅预览不删除')
    parser.add_argument('--report', action='store_true', help='显示报告')
    parser.add_argument('--auto', action='store_true', help='自动清理')
    
    args = parser.parse_args()
    
    cleaner = LogCleaner()
    
    if args.report:
        print(cleaner.generate_report())
    elif args.auto:
        cleaner.auto_cleanup()
    else:
        result = cleaner.cleanup(days=args.days, dry_run=args.dry_run)
        print(f"\n清理结果: {result}")
