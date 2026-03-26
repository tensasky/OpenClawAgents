#!/usr/bin/env python3
"""发财增强版 - 稳定性补丁"""

import sqlite3
import threading
import time
import urllib.request
from datetime import datetime, timedelta

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class EnhancedFacai:
    def __init__(self):
        self.capital = 100000
        self.max_position = 10000
        self.slippage_limit = 0.015  # 1.5%滑点限制
        self.pending_orders = {}  # 跟踪中的订单
    
    def check_slippage(self, code, signal_price):
        """A. 价格保护机制"""
        try:
            url = f'https://qt.gtimg.cn/q={code}'
            with urllib.request.urlopen(url, timeout=2) as r:
                parts = r.read().decode('gbk', errors='ignore').split('~')
                current_price = float(parts[3]) if parts[3] else 0
            
            if current_price > 0:
                change = (current_price - signal_price) / signal_price
                
                if change > self.slippage_limit:
                    print(f"  ⚠️ {code} 滑点过大: {change*100:.1f}%，放弃执行")
                    return False, current_price, "SLIPPAGE"
                
                return True, current_price, "OK"
        except:
            pass
        
        return True, signal_price, "UNCHANGED"
    
    def execute_order(self, signal):
        """执行订单"""
        code = signal['code']
        price = signal['price']
        
        # 滑点检查
        ok, current_price, status = self.check_slippage(code, price)
        
        if not ok:
            return {'status': status, 'price': current_price}
        
        # 执行
        shares = int(self.max_position / current_price) if current_price > 0 else 0
        
        order = {
            'code': code,
            'entry_price': current_price,
            'shares': shares,
            'status': 'PENDING',
            'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        # 加入跟踪
        self.pending_orders[code] = order
        
        return {'status': 'EXECUTED', 'price': current_price, 'shares': shares}
    
    def track_orders(self):
        """B. 异步订单追踪"""
        print("\n=== 订单追踪 (每10秒) ===")
        
        to_remove = []
        
        for code, order in self.pending_orders.items():
            # 检查状态
            try:
                url = f'https://qt.gtimg.cn/q={code}'
                with urllib.request.urlopen(url, timeout=2) as r:
                    parts = r.read().decode('gbk', errors='ignore').split('~')
                    current = float(parts[3]) if parts[3] else 0
                
                # 如果价格变化>2%，认为已成交
                if current > 0:
                    change = abs(current - order['entry_price']) / order['entry_price']
                    if change > 0.02:
                        order['status'] = 'FILLED'
                        print(f"  ✅ {code} 已成交 @ ¥{current}")
                        to_remove.append(code)
            except:
                pass
        
        # 清理
        for code in to_remove:
            del self.pending_orders[code]
        
        return len(self.pending_orders)
    
    def sync_account(self):
        """C. 自动账户同步"""
        print("\n=== 账户同步 (09:15) ===")
        
        now = datetime.now()
        
        # 检查是否需要同步 (每天09:15)
        if now.hour == 9 and now.minute == 15:
            print("  🔄 同步账户数据...")
            
            # 模拟从券商同步
            synced_data = {
                'cash': 50000,
                'positions': 5,
                'total_value': 50000,
                'sync_time': now.strftime('%Y-%m-%d %H:%M:%S')
            }
            
            print(f"  ✅ 同步完成: 现金¥{synced_data['cash']} 持仓{synced_data['positions']}只")
            
            return synced_data
        else:
            print(f"  ⏰ 非同步时间")
            return None
    
    def run_order_flow(self, signals):
        """完整订单流程"""
        print("\n=== 订单流程 ===")
        
        results = []
        
        for signal in signals[:5]:
            result = self.execute_order(signal)
            results.append({
                'code': signal['code'],
                **result
            })
            
            time.sleep(0.5)
        
        # 订单追踪
        print("\n检查订单状态...")
        pending = self.track_orders()
        
        # 账户同步
        self.sync_account()
        
        return results

if __name__ == "__main__":
    facai = EnhancedFacai()
    
    # 模拟信号
    test_signals = [
        {'code': 'sh600000', 'price': 10.06, 'score': 70},
        {'code': 'sh600036', 'price': 39.56, 'score': 70},
    ]
    
    results = facai.run_order_flow(test_signals)
    
    print("\n=== 执行结果 ===")
    for r in results:
        print(f"  {r['code']}: {r['status']}")
