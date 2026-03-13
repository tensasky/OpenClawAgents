#!/usr/bin/env python3
"""
北风历史数据补全工具
补全缺失的日线数据
"""

import requests
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

def fetch_historical_daily(stock_code: str, date: str) -> dict:
    """从网易财经获取历史日线数据"""
    try:
        # 转换代码格式
        if stock_code.startswith('sh'):
            code = '0' + stock_code[2:]
        elif stock_code.startswith('sz'):
            code = '1' + stock_code[2:]
        else:
            return None
        
        url = f"https://quotes.money.163.com/service/chddata.html?code={code}&start={date.replace('-', '')}&end={date.replace('-', '')}&fields=TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;TURNOVER;VOTURNOVER;VATURNOVER"
        
        response = requests.get(url, timeout=30)
        response.encoding = 'gb2312'
        
        lines = response.text.strip().split('\n')
        if len(lines) < 2:
            return None
        
        # 解析数据行
        data_line = lines[1]  # 第一行是数据
        fields = data_line.split(',')
        
        if len(fields) >= 10:
            return {
                'date': fields[0],
                'open': float(fields[6]) if fields[6] else 0,
                'high': float(fields[4]) if fields[4] else 0,
                'low': float(fields[5]) if fields[5] else 0,
                'close': float(fields[3]) if fields[3] else 0,
                'volume': int(float(fields[11])) if fields[11] else 0,
                'amount': float(fields[12]) if len(fields) > 12 and fields[12] else 0
            }
        
        return None
    except Exception as e:
        print(f"  获取 {stock_code} {date} 失败: {e}")
        return None

def fill_missing_data(target_date: str):
    """补全指定日期的数据"""
    print(f"\n{'='*70}")
    print(f"📅 补全 {target_date} 的数据")
    print("="*70)
    
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    # 获取所有股票列表
    cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type='daily' LIMIT 100")
    all_stocks = [row[0] for row in cursor.fetchall()]
    
    # 检查已有数据
    cursor.execute(f"""
        SELECT COUNT(DISTINCT stock_code) 
        FROM kline_data 
        WHERE data_type='daily' AND date(timestamp)='{target_date}'
    """)
    existing_count = cursor.fetchone()[0]
    
    print(f"已有数据: {existing_count} 只")
    print(f"目标股票: {len(all_stocks)} 只")
    print(f"需要补全: {len(all_stocks) - existing_count} 只")
    
    # 获取已有数据的股票
    cursor.execute(f"""
        SELECT DISTINCT stock_code
        FROM kline_data 
        WHERE data_type='daily' AND date(timestamp)='{target_date}'
    """)
    existing_stocks = set(row[0] for row in cursor.fetchall())
    
    # 需要补全的股票
    missing_stocks = [s for s in all_stocks if s not in existing_stocks]
    
    print(f"\n开始补全 {len(missing_stocks)} 只股票...")
    
    success = 0
    failed = 0
    
    for i, stock_code in enumerate(missing_stocks, 1):
        data = fetch_historical_daily(stock_code, target_date)
        
        if data and data['close'] > 0:
            try:
                timestamp = f"{target_date}T00:00:00"
                cursor.execute("""
                    INSERT INTO kline_data 
                    (stock_code, data_type, timestamp, open, high, low, close, volume, amount)
                    VALUES (?, 'daily', ?, ?, ?, ?, ?, ?, ?)
                """, (stock_code, timestamp, data['open'], data['high'], 
                      data['low'], data['close'], data['volume'], data['amount']))
                success += 1
                
                if i % 100 == 0:
                    conn.commit()
                    print(f"  进度: {i}/{len(missing_stocks)}, 成功: {success}")
                
            except Exception as e:
                failed += 1
                print(f"  {stock_code} 保存失败: {e}")
        else:
            failed += 1
        
        time.sleep(0.05)  # 避免请求过快
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 补全完成: 成功 {success} 只, 失败 {failed} 只")

if __name__ == '__main__':
    print("="*70)
    print("🌪️ 北风历史数据补全工具")
    print("="*70)
    
    # 补全3月10日
    fill_missing_data('2026-03-10')
    
    # 补全3月11日
    fill_missing_data('2026-03-11')
    
    print("\n" + "="*70)
    print("✅ 所有历史数据补全完成！")
    print("="*70)
