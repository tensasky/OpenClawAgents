#!/usr/bin/env python3
"""发财交易闭环 - 盘前/盘中/盘后"""

import sqlite3
import time
from datetime import datetime

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class TradingLoop:
    def __init__(self):
        self.capital = 100000
        self.max_position = 10000
        self.max_positions = 10
        self.risk_limit = 0.8
    
    def pre_trade(self):
        """盘前检查"""
        print("\n=== 盘前检查 (Pre-Trade) ===")
        
        # 1. 检查信号
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price, score FROM signals 
            WHERE timestamp >= datetime('now', '-2 hours')
            AND strategy NOT IN ('EXPIRED', 'FILLED', 'REJECTED')
            ORDER BY score DESC
        """)
        
        signals = [{'code': r[0], 'price': r[1], 'score': r[2]} for r in cursor.fetchall()]
        
        # 2. 检查持仓
        cursor.execute("""
            SELECT stock_code, COUNT(*) FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
            GROUP BY stock_code
        """)
        
        positions = [r[0] for r in cursor.fetchall()]
        
        conn.close()
        
        # 3. 风控检查
        can_buy = len(positions) < self.max_positions
        
        print(f"  待处理信号: {len(signals)}只")
        print(f"  当前持仓: {len(positions)}只")
        print(f"  可买入: {'是' if can_buy else '否'}")
        
        return signals, positions
    
    def in_trade(self, signals, positions):
        """盘中下单"""
        print("\n=== 盘中下单 (In-Trade) ===")
        
        executed = []
        
        for signal in signals[:self.max_positions - len(positions)]:
            code = signal['code']
            
            # 风控
            if code in positions:
                print(f"  ⚠️ {code} 已有持仓，跳过")
                continue
            
            price = signal['price']
            score = signal['score']
            
            # 资金分配
            pct = min(score / 100, 0.3)
            amount = min(self.capital * pct, self.max_position)
            shares = int(amount / price) if price > 0 else 0
            
            if shares <= 0:
                continue
            
            # 执行
            print(f"  ✅ 买入 {code}: {shares}股 @ ¥{price}")
            
            # 更新状态
            conn = sqlite3.connect(SIGNALS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE signals SET strategy='FILLED'
                WHERE stock_code=? AND timestamp >= datetime('now', '-2 hours')
            """, (code,))
            conn.commit()
            conn.close()
            
            executed.append(code)
        
        return executed
    
    def post_trade(self):
        """盘后对账"""
        print("\n=== 盘后对账 (Post-Trade) ===")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        # 统计
        cursor.execute("""
            SELECT stock_code, entry_price FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
        """)
        
        filled = cursor.fetchall()
        
        # 计算市值
        total_value = 0
        print("  持仓明细:")
        
        for code, entry_price in filled:
            conn2 = sqlite3.connect(STOCKS_DB)
            cursor2 = conn2.cursor()
            
            # 当前价格
            cursor2.execute("""
                SELECT close FROM daily WHERE stock_code=? AND timestamp='2026-03-26'
            """, (code,))
            row = cursor2.fetchone()
            current_price = row[0] if row else entry_price
            
            conn2.close()
            
            # 假设每只10000元
            value = 10000
            total_value += value
            
            pnl = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0
            
            print(f"    {code}: 入场¥{entry_price} 现价¥{current_price} 盈亏{pnl:+.1f}%")
        
        conn.close()
        
        # 总结
        print(f"\n  总持仓: {len(filled)}只")
        print(f"  总市值: ¥{total_value}")
        print(f"  仓位: {total_value/self.capital*100:.0f}%")
        print(f"  现金: ¥{self.capital - total_value}")
        
        return len(filled), total_value
    
    def run(self):
        """完整闭环"""
        print("=" * 50)
        print("💰 发财交易闭环")
        print("=" * 50)
        
        # 1. 盘前
        signals, positions = self.pre_trade()
        
        # 2. 盘中
        executed = self.in_trade(signals, positions)
        
        # 3. 盘后
        count, value = self.post_trade()
        
        print("\n" + "=" * 50)
        print("✅ 闭环完成")
        print("=" * 50)

if __name__ == "__main__":
    TradingLoop().run()
