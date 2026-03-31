#!/usr/bin/env python3
"""日志监控 - 异常检测"""

import re
from pathlib import Path
from datetime import datetime, timedelta

LOG_FILE = Path(BASE_DIR / "logs/manager.log")

class LogMonitor:
    def __init__(self):
        self.error_threshold = 0.05  # 5%错误率告警
        self.trap_patterns = [
            r'脉冲诱多',
            r'连板过高',
            r'L2拦截',
            r'滑点',
        ]
    
    def scan_log(self, hours=1):
        """扫描日志"""
        if not LOG_FILE.exists():
            return {'status': 'ok', 'errors': 0}
        
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
        
        # 最近N小时
        now = datetime.now()
        recent_lines = []
        
        for line in lines[-1000:]:  # 最近1000行
            # 简单处理
            recent_lines.append(line)
        
        # 统计错误
        errors = sum(1 for l in recent_lines if '❌' in l or 'ERROR' in l)
        traps = []
        
        for pattern in self.trap_patterns:
            matches = [l for l in recent_lines if re.search(pattern, l)]
            if matches:
                traps.append({'pattern': pattern, 'count': len(matches)})
        
        return {
            'status': 'warning' if errors > 10 else 'ok',
            'errors': errors,
            'traps': traps,
            'total': len(recent_lines)
        }
    
    def run(self):
        """运行监控"""
        result = self.scan_log()
        
        print("=== 日志监控 ===\n")
        
        if result['status'] == 'ok':
            print(f"✅ 状态正常 (错误:{result['errors']})")
        else:
            print(f"⚠️ 发现 {result['errors']} 个错误")
        
        if result.get('traps'):
            print("\n陷阱检测:")
            for t in result['traps']:
                print(f"  {t['pattern']}: {t['count']}次")
        
        return result

if __name__ == "__main__":
    LogMonitor().run()
