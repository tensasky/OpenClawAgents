#!/usr/bin/env python3
"""发财交易系统 - 资金管理+订单执行+风控"""

import sqlite3
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "Documents/OpenClawAgents"
SIGNALS_DB = BASE_DIR / "hongzhong/data/signals_v3.db"
STOCKS_DB = BASE_DIR / "beifeng/data/stocks_real.db"

class FacaiTrader:
    def __init__(self):
        # 配置
        self.total_capital = 100000  # 总资金10万
        self.max_position = 10000    # 单只上限1万
        self.max_positions = 10       # 最多10只
        self.risk_limit = 0.8        # 仓位上限80%
    
    def get_pending_signals(self):
        """获取待执行信号"""
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price, score FROM signals 
            WHERE timestamp >= datetime('now', '-1 hour')
            AND strategy NOT IN ('EXPIRED', 'FILLED')
            ORDER BY score DESC
            LIMIT 10
        """)
        
        signals = []
        for row in cursor.fetchall():
            signals.append({
                'code': row[0],
                'entry_price': row[1],
                'score': row[2]
            })
        
        conn.close()
        return signals
    
    def calculate_position(self, score, price):
        """资金分配"""
        # 评分越高，仓位越大
        position_pct = min(score / 100, 1.0) * 0.3  # 最高30%仓位
        
        # 限制单只金额
        amount = min(self.total_capital * position_pct, self.max_position)
        
        # 计算股数
        shares = int(amount / price) if price > 0 else 0
        
        return shares, amount
    
    def check_risk(self, current_positions, new_code):
        """风控检查"""
        # 1. 持仓数量
        if len(current_positions) >= self.max_positions:
            print(f"  ⚠️ 持仓已达上限: {len(current_positions)}只")
            return False
        
        # 2. 总仓位
        total_value = sum(p['value'] for p in current_positions)
        if total_value / self.total_capital > self.risk_limit:
            print(f"  ⚠️ 仓位超限: {total_value/self.total_capital*100:.0f}%")
            return False
        
        # 3. 单只上限
        if any(p['code'] == new_code for p in current_positions):
            print(f"  ⚠️ 已有持仓: {new_code}")
            return False
        
        return True
    
    def execute_order(self, signal):
        """订单执行 (模拟)"""
        code = signal['code']
        price = signal['entry_price']
        shares, amount = self.calculate_position(signal['score'], price)
        
        if shares <= 0:
            return None
        
        print(f"  📊 执行订单: {code}")
        print(f"    价格: ¥{price}")
        print(f"    股数: {shares}")
        print(f"    金额: ¥{amount:.2f}")
        
        # 模拟成交
        order = {
            'code': code,
            'price': price,
            'shares': shares,
            'amount': amount,
            'status': 'FILLED',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        return order
    
    def update_signal_status(self, code, status):
        """更新信号状态"""
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE signals 
            SET strategy = ?
            WHERE stock_code = ?
            AND timestamp >= datetime('now', '-1 hour')
        """, (status, code))
        
        conn.commit()
        conn.close()
    
    def reconcile(self):
        """状态对账"""
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, COUNT(*) 
            FROM signals 
            WHERE strategy = 'FILLED'
            AND timestamp >= date('now')
            GROUP BY stock_code
        """)
        
        positions = []
        for row in cursor.fetchall():
            # 获取当前价格
            conn2 = sqlite3.connect(STOCKS_DB)
            cursor2 = conn2.cursor()
            cursor2.execute("""
                SELECT close FROM daily 
                WHERE stock_code=? AND timestamp='2026-03-26'
            """, (row[0],))
            price_row = cursor2.fetchone()
            conn2.close()
            
            price = price_row[0] if price_row else 0
            value = price * row[1] * 100  # 简化: 100股/手
            
            positions.append({
                'code': row[0],
                'shares': row[1] * 100,
                'value': value
            })
        
        conn.close()
        
        return positions
    
    def run(self):
        """执行交易"""
        print("=" * 50)
        print("💰 发财交易系统")
        print("=" * 50 + "\n")
        
        # 1. 获取信号
        print("📥 获取信号...")
        signals = self.get_pending_signals()
        print(f"  待执行: {len(signals)}只\n")
        
        # 2. 获取当前持仓
        print("📊 检查持仓...")
        positions = self.reconcile()
        print(f"  当前持仓: {len(positions)}只\n")
        
        # 3. 执行
        executed = 0
        for signal in signals:
            if not self.check_risk(positions, signal['code']):
                continue
            
            order = self.execute_order(signal)
            if order:
                self.update_signal_status(signal['code'], 'FILLED')
                positions.append({
                    'code': order['code'],
                    'value': order['amount']
                })
                executed += 1
        
        print(f"\n✅ 执行完成: {executed}只")
        
        # 4. 对账
        print("\n=== 持仓对账 ===")
        for p in positions:
            print(f"  {p['code']}: ¥{p.get('value', 0):.2f}")
        
        total = sum(p.get('value', 0) for p in positions)
        print(f"  总计: ¥{total:.2f} ({total/self.total_capital*100:.0f}%)")

if __name__ == "__main__":
    FacaiTrader().run()
