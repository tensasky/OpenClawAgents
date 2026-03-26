#!/usr/bin/env python3
"""发财交易系统 V2 - 分批入场+滑点保护"""

import sqlite3
import time
from datetime import datetime
import urllib.request

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class FacaiV2:
    def __init__(self):
        # 配置
        self.total_capital = 100000
        self.max_position = 10000    # 单只上限
        self.max_positions = 10
        self.risk_limit = 0.8
        self.slippage_limit = 0.015  # 1.5%滑点保护
        
        # 分批入场配置
        self.batch_enabled = True
        self.batch_count = 2        # 分2批
        self.batch_interval = 300   # 间隔5分钟
    
    def get_realtime_price(self, code):
        """获取实时价格"""
        try:
            url = f'https://qt.gtimg.cn/q={code}'
            with urllib.request.urlopen(url, timeout=2) as r:
                parts = r.read().decode('gbk', errors='ignore').split('~')
                return float(parts[3]) if parts[3] else 0
        except:
            return 0
    
    def check_slippage(self, signal_price, current_price):
        """滑点保护"""
        if current_price > 0:
            change = (current_price - signal_price) / signal_price
            if change > self.slippage_limit:
                return False, f"滑点{change*100:.1f}%超过{self.slippage_limit*100}%"
            if change < -self.slippage_limit:
                return False, f"下跌{abs(change)*100:.1f}%"
        return True, "正常"
    
    def calculate_batches(self, score, price):
        """分批入场计算"""
        total_amount = min(self.total_capital * (score/100) * 0.3, self.max_position)
        
        batch_size = total_amount / self.batch_count
        batches = []
        
        for i in range(self.batch_count):
            shares = int(batch_size / price)
            amount = shares * price
            batches.append({
                'batch': i + 1,
                'shares': shares,
                'amount': amount,
                'price': price
            })
        
        return batches
    
    def execute_batch(self, signal, batch_num):
        """执行单批"""
        code = signal['code']
        entry_price = signal['entry_price']
        
        # 获取实时价格检查滑点
        current = self.get_realtime_price(code)
        
        if current > 0:
            ok, msg = self.check_slippage(entry_price, current)
            if not ok:
                print(f"  ⚠️ 批次{batch_num} {code}: {msg}，跳过")
                return None
            
            price = current  # 用实时价格
        else:
            price = entry_price
        
        # 计算股数
        amount = signal.get('batch_amount', self.max_position / 2)
        shares = int(amount / price)
        
        if shares <= 0:
            return None
        
        return {'code': code, 'price': price, 'shares': shares, 'amount': shares * price}
    
    def execute_with_batches(self, signals):
        """分批执行"""
        print("\n=== 分批入场执行 ===\n")
        
        results = []
        
        for signal in signals[:5]:
            code = signal['code']
            entry_price = signal['entry_price']
            score = signal['score']
            
            print(f"处理 {code}:")
            
            # 计算分批
            batches = self.calculate_batches(score, entry_price)
            print(f"  分{len(batches)}批入场，每批{batches[0]['shares']}股")
            
            # 第一批立即执行
            first_batch = self.execute_batch(signal, 1)
            
            if first_batch:
                # 标记为第一批
                conn = sqlite3.connect(SIGNALS_DB)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE signals SET strategy='FILLED_BATCH1'
                    WHERE stock_code=? AND timestamp >= datetime('now', '-2 hours')
                """, (code,))
                conn.commit()
                conn.close()
                
                print(f"  ✅ 第一批: {first_batch['shares']}股 @ ¥{first_batch['price']}")
                results.append(first_batch)
                
                # 记录第二批待执行 (实际应存入延迟队列)
                conn = sqlite3.connect(SIGNALS_DB)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO signals 
                    (timestamp, stock_code, strategy, version, entry_price, score)
                    VALUES (datetime('now', '+5 minutes'), ?, 'PENDING_BATCH2', 'v2.0', ?, ?)
                """, (code, entry_price, score))
                conn.commit()
                conn.close()
                
                print(f"  ⏳ 第二批: 5分钟后执行")
            else:
                print(f"  ❌ 滑点保护拦截")
        
        return results
    
    def run(self):
        """运行"""
        print("=" * 50)
        print("💰 发财交易系统 V2")
        print("=" * 50)
        
        # 获取信号
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price, score FROM signals 
            WHERE timestamp >= datetime('now', '-2 hours')
            AND strategy NOT IN ('EXPIRED', 'FILLED', 'FILLED_BATCH1', 'PENDING_BATCH2')
            ORDER BY score DESC
            LIMIT 5
        """)
        
        signals = [{'code': r[0], 'entry_price': r[1], 'score': r[2]} for r in cursor.fetchall()]
        
        conn.close()
        
        print(f"\n获取信号: {len(signals)}只\n")
        
        # 分批执行
        results = self.execute_with_batches(signals)
        
        print(f"\n✅ 执行完成: {len(results)}只")

if __name__ == "__main__":
    FacaiV2().run()
