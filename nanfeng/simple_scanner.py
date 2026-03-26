#!/usr/bin/env python3
"""简化版选股器 - 基于个股技术指标"""

import sqlite3
import pandas as pd
import numpy as np
import urllib.request

DB_PATH = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def get_realtime_price(code):
    try:
        url = f'https://qt.gtimg.cn/q={code}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as r:
            parts = r.read().decode('gbk').split('~')
            return {'price': float(parts[3]), 'pct': float(parts[5])/100}
    except:
        return None

def scan():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily WHERE timestamp >= '2026-03-01' ORDER BY RANDOM() LIMIT 150")
    stocks = [r[0] for r in cursor.fetchall()]
    
    results = []
    for code in stocks[:80]:
        df = pd.read_sql_query(f"SELECT close FROM daily WHERE stock_code = '{code}' AND timestamp >= '2026-03-10' ORDER BY timestamp DESC LIMIT 25", conn)
        if len(df) < 20:
            continue
        
        df = df.sort_values('timestamp').reset_index(drop=True)
        ma = df['close'].rolling(20).mean()
        slope = (ma.iloc[-1] - ma.iloc[-5]) / ma.iloc[-5] if ma.iloc[-5] > 0 else 0
        
        rt = get_realtime_price(code)
        if rt and rt['pct'] > 0 and slope > 0:  # 上涨且MA20向上
            results.append({'code': code, 'price': rt['price'], 'pct': rt['pct'], 'slope': slope})
    
    conn.close()
    results.sort(key=lambda x: x['pct'], reverse=True)
    return results[:15]

if __name__ == "__main__":
    print("=== 个股扫描 (MA20向上) ===\n")
    results = scan()
    
    if results:
        for r in results[:10]:
            print(f"{r['code']}: ¥{r['price']:.2f} ({r['pct']:+.1f}%) MA20斜率:{r['slope']*100:+.1f}%")
    else:
        print("无符合条件的股票")
