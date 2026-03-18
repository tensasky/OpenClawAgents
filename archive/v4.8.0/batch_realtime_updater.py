#!/usr/bin/env python3
"""
全A股实时数据批量采集器
分批采集，避免API限制
"""

import sqlite3
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
BATCH_SIZE = 50  # 每批50只，避免请求过多
BATCH_DELAY = 2  # 批次间隔2秒

def fetch_realtime_batch(stock_codes: List[str]) -> Dict[str, Dict]:
    """批量获取实时行情（腾讯支持批量查询）"""
    # 腾讯批量接口：用逗号分隔多个股票
    codes_str = ','.join(stock_codes)
    url = f"https://qt.gtimg.cn/q={codes_str}"
    
    results = {}
    
    try:
        response = requests.get(url, timeout=30)
        data = response.text
        
        # 解析批量返回数据
        # 格式: v_sh000001="...";v_sz000001="...";
        lines = data.strip().split(';')
        
        for line in lines:
            if '~' in line and '="' in line:
                # 提取代码
                code_part = line.split('="')[0]
                code = code_part.replace('v_', '').replace('=', '')
                
                # 解析数据
                parts = line.split('~')
                if len(parts) > 45:
                    try:
                        results[code] = {
                            'code': code,
                            'name': parts[1],
                            'current': float(parts[3]),
                            'prev_close': float(parts[4]),
                            'open': float(parts[5]),
                            'high': float(parts[33]),
                            'low': float(parts[34]),
                            'volume': int(parts[6]) if parts[6].isdigit() else 0,
                            'amount': float(parts[37]) if parts[37] else 0,
                            'change_pct': float(parts[32]) if parts[32] else 0,
                        }
                    except (ValueError, IndexError):
                        continue
        
        return results
    except Exception as e:
        print(f"❌ 批量请求失败: {e}")
        return {}

def update_database_batch(stock_data: Dict[str, Dict]):
    """批量更新数据库"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    
    for code, data in stock_data.items():
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO daily 
                (stock_code, timestamp, open, high, low, close, volume, amount, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'realtime_batch')
            """, (
                code,
                today,
                data['open'],
                data['high'],
                data['low'],
                data['current'],
                data['volume'],
                data['amount']
            ))
            updated += 1
        except Exception as e:
            print(f"  ⚠️ {code} 更新失败: {e}")
    
    conn.commit()
    conn.close()
    return updated

def get_all_stocks() -> List[str]:
    """获取所有股票代码"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 从stocks表获取所有股票
    cursor.execute("SELECT code FROM stocks ORDER BY code")
    stocks = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    return stocks

def batch_update_all():
    """分批更新所有股票"""
    print("="*70)
    print(f"🚀 全A股实时数据采集")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # 获取所有股票
    all_stocks = get_all_stocks()
    total = len(all_stocks)
    
    print(f"\n📊 总股票数: {total}")
    print(f"批次大小: {BATCH_SIZE}")
    print(f"预计批次: {(total + BATCH_SIZE - 1) // BATCH_SIZE}")
    print(f"批次间隔: {BATCH_DELAY}秒")
    print("="*70)
    
    total_updated = 0
    batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    
    for i in range(0, total, BATCH_SIZE):
        batch_num = i // BATCH_SIZE + 1
        batch = all_stocks[i:i+BATCH_SIZE]
        
        print(f"\n📦 批次 {batch_num}/{batches} ({len(batch)}只股票)...")
        
        # 获取数据
        data = fetch_realtime_batch(batch)
        
        if data:
            # 更新数据库
            updated = update_database_batch(data)
            total_updated += updated
            
            # 显示进度
            progress = (batch_num / batches) * 100
            print(f"  ✅ 成功: {updated}/{len(batch)} ({progress:.1f}%)")
            
            # 显示前几只的数据
            for code in list(data.keys())[:3]:
                d = data[code]
                emoji = "📈" if d['change_pct'] > 0 else "📉"
                print(f"     {code}: ¥{d['current']:.2f} ({d['change_pct']:+.2f}%) {emoji}")
        else:
            print(f"  ❌ 本批次获取失败")
        
        # 批次间隔（最后一批不需要等待）
        if batch_num < batches:
            time.sleep(BATCH_DELAY)
    
    print("\n" + "="*70)
    print(f"✅ 采集完成！")
    print(f"总更新: {total_updated}/{total} 只股票")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)

if __name__ == '__main__':
    batch_update_all()
