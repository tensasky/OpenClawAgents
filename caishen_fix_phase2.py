#!/usr/bin/env python3
"""
财神爷 - 第二阶段修复：红中重构 + 实时数据聚合
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HONGZHONG_DB = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

def aggregate_minute_to_daily():
    """
    实时聚合：分钟数据 -> 日线数据
    交易时段用分钟数据聚合，收盘后用真实日线
    """
    print("="*80)
    print("🌪️ 北风 - 实时数据聚合")
    print("="*80)
    
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 获取所有有分钟数据的股票
    cursor.execute(f"""
        SELECT DISTINCT stock_code
        FROM minute
        WHERE date(timestamp) = '{today}'
    """)
    
    stocks = [row[0] for row in cursor.fetchall()]
    print(f"发现 {len(stocks)} 只股票有分钟数据")
    
    aggregated = 0
    for stock in stocks[:100]:  # 先处理100只测试
        # 聚合分钟数据
        cursor.execute(f"""
            SELECT 
                MIN(open) as day_open,
                MAX(high) as day_high,
                MIN(low) as day_low,
                (SELECT close FROM minute 
                 WHERE stock_code = '{stock}' AND date(timestamp) = '{today}'
                 ORDER BY timestamp DESC LIMIT 1) as day_close,
                SUM(volume) as day_volume,
                SUM(amount) as day_amount
            FROM minute
            WHERE stock_code = '{stock}' AND date(timestamp) = '{today}'
        """)
        
        result = cursor.fetchone()
        if result and result[0]:
            open_p, high, low, close, volume, amount = result
            
            # 更新日线表
            cursor.execute(f"""
                UPDATE daily
                SET open = ?, high = ?, low = ?, close = ?, volume = ?, amount = ?
                WHERE stock_code = ? AND date(timestamp) = '{today}'
            """, (open_p, high, low, close, volume, amount, stock))
            
            if cursor.rowcount > 0:
                aggregated += 1
    
    conn.commit()
    conn.close()
    
    print(f"✅ 已聚合 {aggregated} 只股票数据")
    return aggregated

def generate_realtime_signals():
    """
    红中重构：从北风实时数据生成信号
    不再使用硬编码价格
    """
    print("\n" + "="*80)
    print("🀄 红中 - 实时信号生成（重构版）")
    print("="*80)
    
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 获取今日涨幅前列的股票（真实数据）
    cursor.execute(f"""
        SELECT stock_code, 
               (close - open) / open * 100 as change_pct,
               close,
               volume
        FROM daily
        WHERE date(timestamp) = '{today}'
        AND close > 0 AND open > 0
        AND volume > 1000000
        ORDER BY change_pct DESC
        LIMIT 20
    """)
    
    candidates = cursor.fetchall()
    conn.close()
    
    print(f"发现 {len(candidates)} 只候选股票")
    
    # 生成信号（使用真实价格）
    signals = []
    for code, change, close, vol in candidates[:5]:
        if change > 3:  # 涨幅>3%
            signal = {
                'stock_code': code,
                'stock_name': get_stock_name(code),
                'entry_price': close,  # 真实收盘价
                'change_pct': change,
                'volume': vol,
                'strategy': '趋势跟踪' if change > 5 else '突破策略',
                'version': 'conservative' if change > 7 else 'balance',
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stop_loss': round(close * 0.97, 2),  # -3%止损
                'target_1': round(close * 1.05, 2),   # +5%目标
                'target_2': round(close * 1.10, 2),   # +10%目标
            }
            signals.append(signal)
            print(f"✅ 生成信号: {code} | 涨幅{change:.1f}% | 价格¥{close:.2f}")
    
    # 保存到红中数据库
    if signals:
        conn = sqlite3.connect(HONGZHONG_DB)
        cursor = conn.cursor()
        
        for sig in signals:
            cursor.execute("""
                INSERT OR REPLACE INTO signals 
                (stock_code, stock_name, entry_price, strategy, version, 
                 timestamp, stop_loss, target_1, target_2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (sig['stock_code'], sig['stock_name'], sig['entry_price'],
                  sig['strategy'], sig['version'], sig['timestamp'],
                  sig['stop_loss'], sig['target_1'], sig['target_2']))
        
        conn.commit()
        conn.close()
        print(f"✅ 已保存 {len(signals)} 个信号到数据库")
    
    return signals

def get_stock_name(stock_code):
    """获取股票名称"""
    try:
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_name FROM stock_names WHERE stock_code = ?", (stock_code,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else stock_code
    except:
        return stock_code

def verify_fix():
    """验证修复结果"""
    print("\n" + "="*80)
    print("⚖️ 判官 - 修复验证")
    print("="*80)
    
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 检查数据一致性
    cursor.execute(f"""
        SELECT d.stock_code, d.close as daily_close,
               (SELECT close FROM minute m 
                WHERE m.stock_code = d.stock_code 
                AND date(m.timestamp) = '{today}'
                ORDER BY m.timestamp DESC LIMIT 1) as minute_close
        FROM daily d
        WHERE date(d.timestamp) = '{today}'
        LIMIT 10
    """)
    
    print("\n📊 数据一致性抽查:")
    for row in cursor.fetchall():
        code, d_close, m_close = row
        if m_close:
            diff = abs(d_close - m_close) / d_close * 100
            status = "✅" if diff < 1 else "❌"
            print(f"  {status} {code}: 日线{d_close:.2f} vs 分钟{m_close:.2f} (差异{diff:.2f}%)")
    
    conn.close()

if __name__ == '__main__':
    print("💰 财神爷 - 第二阶段修复\n")
    
    # 1. 实时数据聚合
    aggregate_minute_to_daily()
    
    # 2. 红中重构 - 实时信号
    signals = generate_realtime_signals()
    
    # 3. 验证修复
    verify_fix()
    
    print("\n" + "="*80)
    print("✅ 第二阶段修复完成")
    print("="*80)
