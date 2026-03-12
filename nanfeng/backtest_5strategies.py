#!/usr/bin/env python3
"""
南风5策略回测验证
测试各策略在历史数据上的盈利表现
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from strategy_config import get_strategy, STRATEGIES
from nanfeng_v5_1 import NanFengV5_1

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

class StrategyBacktest:
    def __init__(self, strategy_name: str, initial_capital: float = 100000):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.strategy = get_strategy(strategy_name)
        self.nanfeng = NanFengV5_1(strategy_name=strategy_name)
        
    def get_historical_dates(self, days: int = 30) -> List[str]:
        """获取最近N个交易日的日期"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT date(timestamp) as dt
            FROM kline_data
            WHERE data_type = 'daily'
            ORDER BY dt DESC
            LIMIT ?
        """, (days,))
        dates = [row[0] for row in cursor.fetchall()]
        conn.close()
        return sorted(dates)
    
    def get_stocks_for_date(self, date: str, limit: int = 100) -> List[str]:
        """获取某日期有数据的股票"""
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
    
    def get_stock_data(self, stock_code: str, end_date: str, days: int = 40) -> pd.DataFrame:
        """获取股票历史数据"""
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
    
    def get_future_return(self, stock_code: str, entry_date: str, hold_days: int = 5) -> float:
        """获取未来N日收益"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            # 获取入场价格
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND date(timestamp) = ?
            """, (stock_code, entry_date))
            row = cursor.fetchone()
            if not row:
                return None
            entry_price = row[0]
            
            # 获取未来价格
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND date(timestamp) > ?
                ORDER BY timestamp
                LIMIT 1 OFFSET ?
            """, (stock_code, entry_date, hold_days - 1))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            exit_price = row[0]
            return (exit_price / entry_price - 1) * 100
        except:
            return None
    
    def backtest_single_day(self, date: str, top_n: int = 5) -> Dict:
        """回测单日表现"""
        stocks = self.get_stocks_for_date(date, limit=200)
        signals = []
        
        for code in stocks:
            df = self.get_stock_data(code, date)
            if df is None or len(df) < 30:
                continue
            
            signal = self.nanfeng.analyze_stock(code, df, {})
            if signal:
                # 获取未来收益
                future_return = self.get_future_return(code, date, hold_days=5)
                if future_return is not None:
                    signal.future_return = future_return
                    signals.append(signal)
        
        if not signals:
            return {'date': date, 'signals': 0, 'avg_return': 0, 'win_rate': 0}
        
        # 排序取Top N
        signals.sort(key=lambda x: x.total_score, reverse=True)
        top_signals = signals[:top_n]
        
        returns = [s.future_return for s in top_signals]
        avg_return = np.mean(returns)
        win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
        
        return {
            'date': date,
            'signals': len(signals),
            'top_signals': len(top_signals),
            'avg_return': avg_return,
            'win_rate': win_rate,
            'details': [(s.stock_code, s.total_score, s.future_return) for s in top_signals]
        }
    
    def run_backtest(self, days: int = 10) -> Dict:
        """运行回测"""
        print(f"\n{'='*60}")
        print(f"🎯 策略回测: {self.strategy_name}")
        print(f"{'='*60}")
        print(f"初始资金: ¥{self.initial_capital:,.0f}")
        print(f"回测天数: {days}天")
        print(f"每日选股: Top 5")
        print(f"持有周期: 5天")
        
        dates = self.get_historical_dates(days)
        results = []
        
        for date in dates:
            result = self.backtest_single_day(date)
            results.append(result)
            print(f"\n{date}: 信号{result['signals']}个, 选中{result['top_signals']}个")
            print(f"  平均收益: {result['avg_return']:+.2f}%, 胜率: {result['win_rate']:.0f}%")
        
        # 汇总
        all_returns = [r['avg_return'] for r in results if r['top_signals'] > 0]
        if all_returns:
            total_return = np.mean(all_returns)
            overall_win_rate = len([r for r in all_returns if r > 0]) / len(all_returns) * 100
        else:
            total_return = 0
            overall_win_rate = 0
        
        print(f"\n{'='*60}")
        print(f"📊 回测汇总")
        print(f"{'='*60}")
        print(f"总交易次数: {len([r for r in results if r['top_signals'] > 0])}")
        print(f"平均单次收益: {total_return:+.2f}%")
        print(f"整体胜率: {overall_win_rate:.1f}%")
        print(f"预估月收益: {total_return * 4:+.2f}%")
        print(f"{'='*60}")
        
        return {
            'strategy': self.strategy_name,
            'total_return': total_return,
            'win_rate': overall_win_rate,
            'monthly_estimate': total_return * 4,
            'daily_results': results
        }

def main():
    """测试所有策略"""
    print("🌬️ 南风5策略回测系统")
    print("="*60)
    
    all_results = {}
    
    for strategy_name in STRATEGIES.keys():
        try:
            backtest = StrategyBacktest(strategy_name)
            result = backtest.run_backtest(days=5)  # 先测5天
            all_results[strategy_name] = result
        except Exception as e:
            print(f"❌ {strategy_name} 回测失败: {e}")
    
    # 对比汇总
    print(f"\n{'='*60}")
    print("🏆 策略对比")
    print(f"{'='*60}")
    print(f"{'策略':<12} {'单次收益':>10} {'胜率':>8} {'预估月收益':>12}")
    print("-"*60)
    
    for name, result in all_results.items():
        print(f"{name:<12} {result['total_return']:>+9.2f}% {result['win_rate']:>7.1f}% {result['monthly_estimate']:>+11.2f}%")
    
    # 找出最佳策略
    if all_results:
        best = max(all_results.values(), key=lambda x: x['monthly_estimate'])
        print(f"\n🥇 最佳策略: {best['strategy']}")
        print(f"   预估月收益: {best['monthly_estimate']:+.2f}%")

if __name__ == '__main__':
    main()
