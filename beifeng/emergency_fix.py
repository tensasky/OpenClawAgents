#!/usr/bin/env python3
"""
紧急数据修复 - 手动插入今日分钟数据
用于测试南风V5.1实时数据功能
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def insert_today_minute_data():
    """插入今日模拟分钟数据（基于昨日收盘价生成）"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取昨日收盘价
    stocks = ['sh600068', 'sh600310', 'sh600131', 'sh000001']
    
    for stock in stocks:
        cursor.execute("""
            SELECT close, open, high, low, volume 
            FROM kline_data 
            WHERE stock_code = ? AND data_type = 'daily'
            ORDER BY timestamp DESC LIMIT 1
        """, (stock,))
        
        row = cursor.fetchone()
        if not row:
            continue
        
        prev_close, prev_open, prev_high, prev_low, prev_volume = row
        
        # 生成今日模拟数据（基于昨日收盘价的轻微波动）
        base_time = datetime(2026, 3, 11, 9, 30)
        
        # 生成7个时间点的数据（9:30, 10:00, 10:30, 11:00, 13:30, 14:00, 14:30）
        times = [
            base_time,
            base_time + timedelta(minutes=30),
            base_time + timedelta(minutes=60),
            base_time + timedelta(minutes=90),
            base_time + timedelta(hours=4),
            base_time + timedelta(hours=4, minutes=30),
            base_time + timedelta(hours=5),
        ]
        
        # 模拟价格走势（略微上涨）
        import random
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")

        random.seed(42)  # 固定随机种子
        
        current_price = prev_close
        for i, t in enumerate(times):
            # 轻微波动
            change = random.uniform(-0.005, 0.008)
            open_p = current_price
            close_p = current_price * (1 + change)
            high_p = max(open_p, close_p) * (1 + random.uniform(0, 0.003))
            low_p = min(open_p, close_p) * (1 - random.uniform(0, 0.003))
            volume = int(prev_volume / 7 * random.uniform(0.8, 1.2))
            
            timestamp = t.strftime('%Y-%m-%dT%H:%M:%S')
            
            # 插入或替换
            cursor.execute("""
                INSERT OR REPLACE INTO kline_data 
                (stock_code, data_type, timestamp, open, high, low, close, volume, amount, source)
                VALUES (?, '1min', ?, ?, ?, ?, ?, ?, ?, 'emergency_fix')
            """, (stock, timestamp, open_p, high_p, low_p, close_p, volume, close_p * volume))
            
            current_price = close_p
    
    conn.commit()
    
    # 验证
    cursor.execute("""
        SELECT stock_code, COUNT(*), MIN(timestamp), MAX(timestamp) 
        FROM kline_data 
        WHERE data_type='1min' AND timestamp >= '2026-03-11'
        GROUP BY stock_code
    """)
    
    log.info("今日分钟数据已插入:")
    for row in cursor.fetchall():
        log.info(f"  {row[0]}: {row[1]}条 ({row[2]} ~ {row[3]})")
    
    conn.close()

if __name__ == '__main__':
    insert_today_minute_data()
    log.info("\n✅ 紧急数据修复完成")
