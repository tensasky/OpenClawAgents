#!/usr/bin/env python3
"""发财交易闭环 - 真实交易规则"""

import sqlite3
from datetime import datetime

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class TradingLoop:
    def __init__(self):
        self.capital = 100000
        self.max_position = 10000    # 单只上限1万
        self.max_positions = 10
        self.risk_limit = 0.8
        self.min_lot = 100          # 最小100股
    
    def calculate_lot_size(self, price, target_amount):
        """计算整手股数"""
        # 计算可买股数
        shares = int(target_amount / price)
        # 调整为100股整数倍
        lots = shares // self.min_lot
        final_shares = lots * self.min_lot
        return final_shots if 'final_shares' in locals() else 0
    
    def pre_trade(self):
        """盘前检查"""
        print("\n=== 盘前检查 ===")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price, score FROM signals 
            WHERE timestamp >= datetime('now', '-2 hours')
            AND strategy NOT IN ('EXPIRED', 'FILLED')
            ORDER BY score DESC
        """)
        
        signals = [{'code': r[0], 'price': r[1], 'score': r[2]} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT stock_code FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
        """)
        positions = [r[0] for r in cursor.fetchall()]
        
        conn.close()
        
        print(f"  待处理信号: {len(signals)}只")
        print(f"  当前持仓: {len(positions)}只")
        
        return signals, positions
    
    def in_trade(self, signals, positions):
        """盘中下单 - 真实规则"""
        print("\n=== 盘中下单 (真实规则) ===")
        
        executed = []
        
        for signal in signals[:self.max_positions - len(positions)]:
            if signal['code'] in positions:
                continue
            
            # 资金分配
            pct = min(signal['score'] / 100, 0.3)
            amount = min(self.capital * pct, self.max_position)
            
            # 真实规则: 100股整数倍
            shares = self.calculate_lot_size(signal['price'], amount)
            
            if shares < self.min_lot:
                continue
            
            print(f"  买入 {signal['code']}: {shares}股 ({shares//100}手) @ ¥{signal['price']}")
            
            # 更新状态
            conn = sqlite3.connect(SIGNALS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE signals SET strategy='FILLED'
                WHERE stock_code=? AND timestamp >= datetime('now', '-2 hours')
            """, (signal['code'],))
            conn.commit()
            conn.close()
            
            executed.append(signal['code'])
        
        return executed
    
    def post_trade(self):
        """盘后对账"""
        print("\n=== 盘后对账 ===")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
        """)
        
        filled = cursor.fetchall()
        
        total_cost = 0
        total_shares = 0
        
        for code, entry_price in filled:
            # 按100股计算
            shares = 1000  # 简化: 假设每只10手
            cost = shares * entry_price
            total_cost += cost
            total_shares += shares
            
            print(f"  {code}: {shares}股 @ ¥{entry_price} = ¥{cost:,}")
        
        conn.close()
        
        print(f"\n  总股数: {total_shares}股")
        print(f"  总市值: ¥{total_cost:,}")
        print(f"  仓位: {total_cost/self.capital*100:.0f}%")

if __name__ == "__main__":
    TradingLoop().post_trade()
