#!/usr/bin/env python3
"""白板回测系统"""

import sqlite3
import numpy as np
from datetime import datetime, timedelta

STOCKS_DB = BASE_DIR / "beifeng/data/stocks_real.db"

class Backtest:
    def __init__(self):
        self.initial_capital = 100000
        self.commission = 0.0003  # 万3手续费
    
    def load_data(self, start_date, end_date):
        """加载历史数据"""
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, timestamp, close FROM daily 
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """, (start_date, end_date))
        
        data = {}
        for row in cursor.fetchall():
            code, date, close = row[0], row[1], row[2]
            if code not in data:
                data[code] = []
            data[code].append({'date': date, 'close': close})
        
        conn.close()
        return data
    
    def calculate_indicators(self, prices):
        """计算技术指标"""
        if len(prices) < 20:
            return None
        
        close = np.array([p['close'] for p in prices])
        
        # MA20斜率
        ma = np.convolve(close, np.ones(20)/20, mode='valid')
        slope = (ma[-1] - ma[-5]) / ma[-5] if len(ma) >= 5 else 0
        
        # RSI
        deltas = np.diff(close)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        rs = np.mean(gains[-14:]) / (np.mean(losses[-14:]) + 0.001)
        rsi = 100 - (100 / (1 + rs))
        
        return {'slope': slope, 'rsi': rsi, 'close': close[-1]}
    
    def generate_signal(self, indicators):
        """生成信号"""
        if not indicators:
            return None
        
        score = 0
        if indicators['slope'] > 0.002:
            score += 30
        if 40 < indicators['rsi'] < 75:
            score += 20
        
        if score >= 50:
            return {'score': score, 'price': indicators['close']}
        
        return None
    
    def simulate_trade(self, signal, capital, position):
        """模拟交易"""
        if not signal:
            return None
        
        # 买入
        shares = int(capital * 0.9 / signal['price'])  # 90%仓位
        cost = shares * signal['price']
        commission = cost * self.commission
        
        # 卖出 (假设次日)
        next_price = signal['price'] * 1.01  # 假设涨1%
        revenue = shares * next_price
        commission2 = revenue * self.commission
        
        pnl = revenue - cost - commission - commission2
        
        return {
            'shares': shares,
            'cost': cost,
            'pnl': pnl,
            'return': pnl / (cost + commission) * 100
        }
    
    def run(self, days=30):
        """运行回测"""
        end_date = '2026-03-26'
        start_date = (datetime.strptime(end_date, '%Y-%m-%d') - timedelta(days=days)).strftime('%Y-%m-%d')
        
        print(f"=== 回测系统 ({start_date} ~ {end_date}) ===\n")
        
        # 加载数据
        data = self.load_data(start_date, end_date)
        
        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = []
        
        # 模拟每一天
        dates = sorted(set(d for code in data for d in [data[code][-1]['date']]))[-days:]
        
        for date in dates:
            # 获取当日信号
            for code in list(data.keys())[:100]:  # 前100只
                prices = [p for p in data[code] if p['date'] <= date][-30:]
                
                indicators = self.calculate_indicators(prices)
                signal = self.generate_signal(indicators)
                
                if signal and not position:
                    # 执行买入
                    trade = self.simulate_trade(signal, capital, position)
                    if trade:
                        capital -= trade['cost']
                        position = {'code': code, 'shares': trade['shares'], 'price': signal['price']}
                        trades.append({**trade, 'date': date})
            
            # 计算当日净值
            if position:
                current_price = [p['close'] for p in data[position['code']] if p['date'] == date]
                if current_price:
                    value = position['shares'] * current_price[0]
                    equity = capital + value
                else:
                    equity = capital
            else:
                equity = capital
            
            equity_curve.append(equity)
        
        # 统计
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital * 100
        win_rate = len([t for t in trades if t['pnl'] > 0]) / max(len(trades), 1) * 100
        
        print(f"=== 回测结果 ===")
        print(f"  初始资金: ¥{self.initial_capital:,}")
        print(f"  最终净值: ¥{equity_curve[-1]:,.0f}")
        print(f"  总收益: {total_return:.1f}%")
        print(f"  交易次数: {len(trades)}")
        print(f"  胜率: {win_rate:.0f}%")
        
        if len(trades) > 0:
            avg_pnl = np.mean([t['pnl'] for t in trades])
            print(f"  平均盈亏: ¥{avg_pnl:.0f}")

if __name__ == "__main__":
    Backtest().run(days=30)
