#!/usr/bin/env python3
"""
南风门槛回测 - 找最优分数阈值
"""

import sys
import sqlite3
import pandas as pd
from pathlib import Path
import statistics

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5_1 import NanFengV5_1, TechnicalIndicators

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

def backtest_threshold(threshold: int, test_date: str = '2026-03-10') -> dict:
    """测试特定门槛"""
    
    # 创建临时V5.1，修改门槛
    v51 = NanFengV5_1(strategy_name='趋势跟踪')
    v51.score_threshold = threshold  # 动态修改门槛
    
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    # 获取股票列表
    cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type='daily' LIMIT 100")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    signals = []
    
    for code in stocks:
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT 40
            """
            df = pd.read_sql_query(query, conn, params=(code, test_date))
            conn.close()
            
            if len(df) < 30:
                continue
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # 分析
            signal = v51.analyze_stock(code, df, {})
            if signal:
                # 获取未来5日收益
                future_return = get_future_return(code, test_date)
                signals.append({
                    'code': code,
                    'score': signal.total_score,
                    'future_return': future_return
                })
        except:
            continue
    
    if not signals:
        return {'threshold': threshold, 'count': 0}
    
    # 按分数排序，取前10
    signals.sort(key=lambda x: x['score'], reverse=True)
    top10 = [s for s in signals[:10] if s['future_return'] is not None]
    
    if not top10:
        return {'threshold': threshold, 'count': len(signals)}
    
    returns = [s['future_return'] for s in top10]
    
    return {
        'threshold': threshold,
        'count': len(signals),
        'top10_count': len(top10),
        'avg_return': statistics.mean(returns),
        'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100,
        'max_return': max(returns),
        'min_return': min(returns)
    }

def get_future_return(stock_code: str, entry_date: str) -> float:
    """获取未来5日收益"""
    try:
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT close FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            AND timestamp = ?
        """, (stock_code, entry_date))
        row = cursor.fetchone()
        if not row:
            return None
        entry_price = row[0]
        
        cursor.execute("""
            SELECT close FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            AND timestamp > ?
            ORDER BY timestamp
            LIMIT 1 OFFSET 4
        """, (stock_code, entry_date))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return (row[0] / entry_price - 1) * 100
    except:
        return None

def main():
    print("="*60)
    print("🎯 南风门槛回测")
    print("="*60)
    
    thresholds = [20, 30, 40, 50, 60, 70, 80]
    results = []
    
    for t in thresholds:
        print(f"\n测试门槛: {t}分")
        result = backtest_threshold(t)
        results.append(result)
        
        if result.get('avg_return') is not None:
            print(f"  信号数: {result['count']}, Top10: {result['top10_count']}")
            print(f"  平均收益: {result['avg_return']:+.2f}%")
            print(f"  胜率: {result['win_rate']:.1f}%")
    
    # 找最优
    valid_results = [r for r in results if r.get('avg_return') is not None]
    if valid_results:
        best = max(valid_results, key=lambda x: x['avg_return'])
        print("\n" + "="*60)
        print(f"🏆 最优门槛: {best['threshold']}分")
        print(f"   平均收益: {best['avg_return']:+.2f}%")
        print(f"   胜率: {best['win_rate']:.1f}%")
        print("="*60)

if __name__ == '__main__':
    main()
