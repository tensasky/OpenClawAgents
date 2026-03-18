#!/usr/bin/env python3
"""
东风 V2.0 - 盘中监控+资金流向Agent
交易时段实时监控，动态筛选活跃股票，跟踪主力资金
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("东风")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class DongfengV2:
    """东风V2.0 - 盘中监控+资金流向"""
    
    def scan_active_stocks(self):
        """扫描活跃股票"""
        log.step("扫描活跃股票")
        
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute(f"""
            SELECT stock_code, close, (high-low)/open*100 as amp
            FROM daily
            WHERE date(timestamp) = '{today}'
            AND volume > 1000000
            AND (high-low)/open > 0.03
        """)
        
        stocks = cursor.fetchall()
        conn.close()
        
        log.info(f"发现 {len(stocks)} 只活跃股票")
        return stocks

if __name__ == '__main__':
    df = DongfengV2()
    df.scan_active_stocks()
