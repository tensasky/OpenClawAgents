#!/usr/bin/env python3
"""
分钟数据采集脚本 - 使用minute_fetcher
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from minute_fetcher import MinuteDataFetcher
import sqlite3
from datetime import datetime

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def save_minute_data(stock_code, data):
    """保存分钟数据到数据库"""
    if not data:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    count = 0
    for item in data:
        try:
            # 时间格式: HHMM
            time_str = str(item['time']).zfill(4)
            hour = int(time_str[:2])
            minute = int(time_str[2:])
            
            timestamp = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            cursor.execute("""
                INSERT OR REPLACE INTO minute 
                (stock_code, timestamp, open, high, low, close, volume, amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                stock_code,
                timestamp,
                item.get('open', item['price']),
                item.get('high', item['price']),
                item.get('low', item['price']),
                item['price'],
                item['volume'],
                item.get('amount', 0)
            ))
            count += 1
        except Exception as e:
            print(f"保存失败: {e}")
    
    conn.commit()
    conn.close()
    return count

def main():
    fetcher = MinuteDataFetcher()
    
    # 采集上证指数分钟数据
    stock_code = "sh000001"
    print(f"📊 采集 {stock_code} 分钟数据...")
    
    data = fetcher.fetch_tencent_minute(stock_code)
    if data:
        count = save_minute_data(stock_code, data)
        print(f"✅ 成功保存 {count} 条分钟数据")
    else:
        print("❌ 无数据")

if __name__ == '__main__':
    main()
