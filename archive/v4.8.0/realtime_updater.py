#!/usr/bin/env python3
"""
实时数据更新器 - Trading Day Real-time Updater
在交易时段使用实时行情接口更新当日数据
"""

import sqlite3
import requests
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def fetch_realtime_quote(stock_code):
    """获取实时行情"""
    # 转换代码格式
    if stock_code.startswith('sh'):
        tencent_code = 'sh' + stock_code[2:]
    elif stock_code.startswith('sz'):
        tencent_code = 'sz' + stock_code[2:]
    else:
        tencent_code = stock_code
    
    url = f"https://qt.gtimg.cn/q={tencent_code}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.text
        
        # 解析数据
        # 格式: v_sh000001="1~名称~代码~当前价~昨收~开盘..."
        if '~' in data:
            parts = data.split('~')
            if len(parts) > 45:
                return {
                    'code': stock_code,
                    'name': parts[1],
                    'current': float(parts[3]),
                    'prev_close': float(parts[4]),
                    'open': float(parts[5]),
                    'high': float(parts[33]),
                    'low': float(parts[34]),
                    'volume': int(parts[6]),
                    'amount': float(parts[37]) if parts[37] else 0,
                    'change_pct': float(parts[32]) if parts[32] else 0,
                    'timestamp': parts[30]  # 格式: 20260316133227
                }
        return None
    except Exception as e:
        print(f"❌ 获取 {stock_code} 失败: {e}")
        return None

def update_daily_realtime(stock_codes):
    """更新日线数据（实时）"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    updated = 0
    
    print(f"📊 更新实时数据 ({today})...")
    
    for code in stock_codes:
        quote = fetch_realtime_quote(code)
        if quote:
            # 插入或更新当日数据
            cursor.execute("""
                INSERT OR REPLACE INTO daily 
                (stock_code, timestamp, open, high, low, close, volume, amount, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'realtime')
            """, (
                code,
                today,
                quote['open'],
                quote['high'],
                quote['low'],
                quote['current'],
                quote['volume'],
                quote['amount']
            ))
            updated += 1
            print(f"  ✅ {code}: ¥{quote['current']} ({quote['change_pct']:+.2f}%)")
    
    conn.commit()
    conn.close()
    
    print(f"\n✅ 已更新 {updated} 只股票")
    return updated

if __name__ == '__main__':
    # 重点股票列表
    stocks = [
        'sh000001',  # 上证指数
        'sz399001',  # 深证成指
        'sh600519',  # 贵州茅台
        'sz300750',  # 宁德时代
        'sh601012',  # 隆基绿能
        'sz300274',  # 阳光电源
        'sh601888',  # 中国中免
        'sh600118',  # 中国卫星
        'sz000063',  # 中兴通讯
        'sh603019',  # 中科曙光
    ]
    
    update_daily_realtime(stocks)
