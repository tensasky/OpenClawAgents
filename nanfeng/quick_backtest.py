#!/usr/bin/env python3
"""
南风策略快速回测 - 简化版
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5_1 import NanFengV5_1

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def get_stocks(date: str, limit: int = 100):
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT stock_code
        FROM kline_data
        WHERE data_type = 'daily' AND date(timestamp) = ?
        LIMIT ?
    """, (date, limit))
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def get_stock_data(stock_code: str, end_date: str, days: int = 40):
    conn = sqlite3.connect(BEIFENG_DB)
    query = """
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE stock_code = ? AND data_type = 'daily'
        AND date(timestamp) <= ?
        ORDER BY timestamp DESC
        LIMIT ?
    """
    df = pd.read_sql_query(query, conn, params=(stock_code, end_date, days))
    conn.close()
    return df.sort_values('timestamp').reset_index(drop=True) if len(df) > 0 else None

def quick_backtest(strategy_name: str = "趋势跟踪", date: str = "2026-03-10"):
    """快速回测单日"""
    print(f"\n🎯 策略: {strategy_name}")
    print(f"📅 日期: {date}")
    print("-" * 50)
    
    nanfeng = NanFengV5_1(strategy_name=strategy_name)
    stocks = get_stocks(date, limit=100)
    
    signals = []
    for code in stocks[:50]:  # 先测50只
        df = get_stock_data(code, date)
        if df is not None and len(df) >= 30:
            signal = nanfeng.analyze_stock(code, df, {})
            if signal:
                signals.append((code, signal.total_score))
    
    print(f"✅ 发现 {len(signals)} 个信号")
    
    if signals:
        signals.sort(key=lambda x: x[1], reverse=True)
        print("\n🏆 Top 5:")
        for i, (code, score) in enumerate(signals[:5], 1):
            print(f"  {i}. {code}: {score:.1f}分")
    
    return signals

if __name__ == '__main__':
    # 测试趋势跟踪策略
    signals = quick_backtest("趋势跟踪", "2026-03-10")
    
    if not signals:
        print("\n⚠️ 无信号，尝试降低门槛...")
        # 可以在这里调整门槛再测
