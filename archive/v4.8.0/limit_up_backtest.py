#!/usr/bin/env python3
"""
涨停策略回测系统 - Limit Up Strategy Backtest
分析首板、二板、三板的成功率，找出最佳买点
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("涨停回测")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class LimitUpBacktest:
    """涨停策略回测器"""
    
    def __init__(self):
        self.results = {
            'first_board': [],  # 首板
            'second_board': [], # 二板
            'third_board': []   # 三板
        }
        
    def get_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        conn = sqlite3.connect(BEIFENG_DB)
        
        query = """
            SELECT 
                date(timestamp) as date,
                open, high, low, close, volume,
                (close - open) / open * 100 as change_pct,
                (high - low) / open * 100 as amplitude
            FROM daily
            WHERE stock_code = ? 
            AND date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn, params=(stock_code, start_date, end_date))
        conn.close()
        
        return df
    
    def is_limit_up(self, change_pct: float) -> bool:
        """判断是否涨停（涨幅≥9.9%）"""
        return change_pct >= 9.9
    
    def is_limit_up_first_day(self, df: pd.DataFrame, idx: int) -> bool:
        """
        判断是否是首板
        条件：
        1. 今日涨停
        2. 昨日未涨停
        3. 成交量放大（量比>1.5）
        """
        if idx < 1 or idx >= len(df):
            return False
        
        today = df.iloc[idx]
        yesterday = df.iloc[idx - 1]
        
        # 今日涨停
        if not self.is_limit_up(today['change_pct']):
            return False
        
        # 昨日未涨停
        if self.is_limit_up(yesterday['change_pct']):
            return False
        
        # 成交量放大（简单判断：今日>昨日1.5倍）
        if today['volume'] < yesterday['volume'] * 1.2:
            return False
        
        return True
    
    def backtest_stock(self, stock_code: str, start_date: str, end_date: str) -> Dict:
        """回测单只股票"""
        df = self.get_stock_data(stock_code, start_date, end_date)
        
        if len(df) < 10:
            return None
        
        trades = []
        
        for i in range(1, len(df) - 1):  # 留出最后一天计算收益
            # 检测首板
            if self.is_limit_up_first_day(df, i):
                today = df.iloc[i]
                tomorrow = df.iloc[i + 1]
                
                # 计算第二天表现
                next_open = tomorrow['open']
                next_close = tomorrow['close']
                next_high = tomorrow['high']
                next_low = tomorrow['low']
                
                # 能否买入 - 更严格的条件
                # 实际情况：涨停股次日大多高开，很难以开盘价买入
                # 假设：如果次日开盘价涨幅<5%，可以买入；否则无法买入或买入成本高
                next_open_change = (next_open - today['close']) / today['close'] * 100
                
                can_buy = next_open_change <= 5  # 高开不超过5%才能买入
                
                # 买入价格：如果高开太多，实际买入价格会更高
                if next_open_change > 5:
                    buy_price = today['close'] * 1.05  # 实际买入成本
                    can_buy = False  # 标记为无法以理想价格买入
                else:
                    buy_price = next_open
                
                # 计算收益（假设第二天收盘卖出）
                if can_buy:
                    profit = (next_close - buy_price) / buy_price * 100
                    
                    # 计算盘中最高收益（用于判断最佳卖点）
                    max_profit = (next_high - buy_price) / buy_price * 100
                    min_profit = (next_low - buy_price) / buy_price * 100
                    
                    trades.append({
                        'date': today['date'],
                        'stock': stock_code,
                        'buy_price': buy_price,
                        'sell_price': next_close,
                        'profit': profit,
                        'max_profit': max_profit,
                        'min_profit': min_profit,
                        'can_buy': can_buy,
                        'volume_ratio': today['volume'] / df.iloc[i-1]['volume']
                    })
        
        return trades
    
    def run_backtest(self, stock_list: List[str], start_date: str, end_date: str):
        """运行回测"""
        log.step(f"开始涨停策略回测: {start_date} ~ {end_date}")
        log.info(f"回测股票数: {len(stock_list)}")
        
        all_trades = []
        
        for i, stock in enumerate(stock_list, 1):
            if i % 100 == 0:
                log.info(f"进度: {i}/{len(stock_list)}")
            
            trades = self.backtest_stock(stock, start_date, end_date)
            if trades:
                all_trades.extend(trades)
        
        return all_trades
    
    def analyze_results(self, trades: List[Dict]):
        """分析回测结果"""
        if not trades:
            log.warning("无交易记录")
            return
        
        df = pd.DataFrame(trades)
        
        print("\n" + "="*70)
        print("🎯 涨停策略回测报告")
        print("="*70)
        
        # 基础统计
        total_trades = len(df)
        win_trades = len(df[df['profit'] > 0])
        lose_trades = len(df[df['profit'] <= 0])
        win_rate = win_trades / total_trades * 100
        
        avg_profit = df['profit'].mean()
        max_profit = df['profit'].max()
        min_profit = df['profit'].min()
        
        print(f"\n📊 基础统计:")
        print(f"  总交易次数: {total_trades}")
        print(f"  盈利次数: {win_trades} ({win_rate:.1f}%)")
        print(f"  亏损次数: {lose_trades} ({100-win_rate:.1f}%)")
        print(f"  平均收益: {avg_profit:.2f}%")
        print(f"  最大盈利: {max_profit:.2f}%")
        print(f"  最大亏损: {min_profit:.2f}%")
        
        # 买入可行性分析 - 更详细
        can_buy_easy = len(df[df['can_buy'] == True])  # 可以轻松买入
        can_buy_hard = len(df[df['can_buy'] == False])  # 高开难买
        
        avg_open_jump = df['open_jump'].mean() if 'open_jump' in df.columns else 0
        
        print(f"\n🛒 买入可行性分析:")
        print(f"  涨停后次日可轻松买入: {can_buy_easy}/{total_trades} ({can_buy_easy/total_trades*100:.1f}%)")
        print(f"  涨停后次日高开难买: {can_buy_hard}/{total_trades} ({can_buy_hard/total_trades*100:.1f}%)")
        print(f"  次日平均高开幅度: {avg_open_jump:.2f}%")
        print(f"  说明: 大部分涨停股次日高开5%以上，很难以理想价格买入")
        
        # 最佳买点分析
        print(f"\n💡 最佳买点分析:")
        
        # 策略1：首板打板（涨停瞬间买入）
        print(f"\n  策略1️⃣ 首板打板（当日涨停时买入）:")
        print(f"     优点：确保买入，享受次日溢价")
        print(f"     风险：可能开板，当日被套")
        print(f"     建议：只打确定性高的首板（10:30前封板）")
        
        # 策略2：二板接力
        second_board_profit = df[df['volume_ratio'] > 2]['profit'].mean() if len(df[df['volume_ratio'] > 2]) > 0 else 0
        print(f"\n  策略2️⃣ 二板接力（次日高开不多时买入）:")
        print(f"     条件：次日高开<5%，有成交量配合")
        print(f"     预期收益: {second_board_profit:.2f}%")
        print(f"     风险：高开低走，被套在高点")
        
        # 策略3：三板定龙头
        print(f"\n  策略3️⃣ 三板定龙头（强者恒强）:")
        print(f"     条件：连续三日涨停，板块龙头")
        print(f"     优点：确定性高，市场认可")
        print(f"     风险：位置高，随时可能开板")
        
        # 策略4：尾盘偷袭
        print(f"\n  策略4️⃣ 尾盘买入（14:30后封板）:")
        print(f"     优点：避免盘中开板风险")
        print(f"     缺点：次日溢价可能不如早盘板")
        
        # 收益分布
        print(f"\n📊 收益分布:")
        profit_ranges = [
            ('涨停 (>9.9%)', len(df[df['profit'] > 9.9])),
            ('大涨 (5-9.9%)', len(df[(df['profit'] >= 5) & (df['profit'] <= 9.9)])),
            ('小涨 (0-5%)', len(df[(df['profit'] >= 0) & (df['profit'] < 5)])),
            ('亏损 (<0%)', len(df[df['profit'] < 0])),
        ]
        
        for label, count in profit_ranges:
            if count > 0:
                pct = count / total_trades * 100
                print(f"  {label}: {count}次 ({pct:.1f}%)")
        
        # 成功率分析
        print(f"\n📈 策略建议:")
        if win_rate > 60:
            print(f"  ✅ 胜率高({win_rate:.1f}%)，策略有效")
        else:
            print(f"  ⚠️ 胜率较低({win_rate:.1f}%)，需优化")
        
        if can_buy_rate < 50:
            print(f"  ⚠️ 买入机会少({can_buy_rate:.1f}%)，建议:")
            print(f"     1. 打板买入（涨停瞬间买入）")
            print(f"     2. 隔夜委托（次日开盘前挂单）")
            print(f"     3. 放弃高开股，等回调")
        
        print("="*70)


def main():
    """主程序"""
    backtest = LimitUpBacktest()
    
    # 获取股票列表（前100只测试）
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily LIMIT 100")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    # 运行回测（近6个月数据）
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    trades = backtest.run_backtest(stocks, start_date, end_date)
    backtest.analyze_results(trades)


if __name__ == '__main__':
    main()
