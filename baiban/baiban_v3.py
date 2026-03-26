#!/usr/bin/env python3
"""白板 V3 - 盘后复盘+数据库维护"""

import sqlite3
import numpy as np
import subprocess
from datetime import datetime, timedelta

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STRATEGY_DB = "/Users/roberto/Documents/OpenClawAgents/strategy/strategy.db"

class BaibanV3:
    def __init__(self):
        pass
    
    def daily_review(self):
        """盘后复盘"""
        print("\n=== 盘后复盘 ===\n")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        # 今日信号统计
        cursor.execute("""
            SELECT strategy, COUNT(*) FROM signals 
            WHERE timestamp >= date('now')
            GROUP BY strategy
        """)
        
        stats = {}
        for row in cursor.fetchall():
            stats[row[0]] = row[1]
        
        conn.close()
        
        print(f"今日信号统计:")
        for status, count in stats.items():
            print(f"  {status}: {count}只")
        
        return stats
    
    def db_maintenance(self):
        """数据库维护"""
        print("\n=== 数据库维护 ===\n")
        
        # 调用维护脚本
        result = subprocess.run([
            'python3', 
            '/Users/roberto/Documents/OpenClawAgents/baiban/db_maintenance.py'
        ], capture_output=True, text=True, timeout=120)
        
        print(result.stdout)
        
        return True
    
    def backtest(self, days=30):
        """回测"""
        print("\n=== 回测分析 ===\n")
        
        # 简化的回测逻辑
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT score, COUNT(*) FROM signals 
            WHERE timestamp >= datetime('now', '-30 days')
            GROUP BY score / 10 * 10
        """)
        
        print("评分分布:")
        for row in cursor.fetchall():
            print(f"  评分{int(row[0])}: {row[1]}只")
        
        conn.close()
        
        return True
    
    def run(self):
        """运行盘后流程"""
        print("="*60)
        print("📊 白板 V3 - 盘后流程")
        print("="*60)
        
        # 1. 盘后复盘
        self.daily_review()
        
        # 2. 数据库维护 (VACUUM)
        self.db_maintenance()
        
        # 3. 回测分析
        self.backtest()
        
        print("\n✅ 盘后流程完成")

if __name__ == "__main__":
    BaibanV3().run()
