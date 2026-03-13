#!/usr/bin/env python3
"""
白板 - 5策略回测系统V1.0
回测南风5策略，生成详细报告
"""

import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import json

# 数据库路径
REAL_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)

# 导入V5.2策略配置
import sys
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from strategy_config_v52 import get_strategy_v52, calculate_stop_loss_price, calculate_take_profit_levels


class StrategyBacktester:
    """策略回测器"""
    
    def __init__(self, strategy_name: str):
        self.strategy_name = strategy_name
        self.strategy = get_strategy_v52(strategy_name)
        self.config = self.strategy["config"]
        self.trades = []
        
    def get_historical_signals(self, limit: int = 100) -> List[Dict]:
        """获取历史信号（模拟生成基于策略条件的信号）"""
        print(f"🀆 白板: 为 {self.strategy_name} 生成历史信号...")
        
        conn = sqlite3.connect(REAL_DB)
        
        # 获取最近有数据的股票
        stocks = pd.read_sql_query("""
            SELECT DISTINCT stock_code 
            FROM daily 
            WHERE timestamp >= date('now', '-30 days')
            ORDER BY RANDOM()
            LIMIT 200
        """, conn)
        
        signals = []
        
        for stock_code in stocks['stock_code'][:limit]:
            # 获取股票历史数据
            df = pd.read_sql_query(f"""
                SELECT * FROM daily
                WHERE stock_code = '{stock_code}'
                AND timestamp >= date('now', '-60 days')
                ORDER BY timestamp
            """, conn)
            
            if len(df) < 20:
                continue
            
            # 计算技术指标
            df['ma5'] = df['close'].rolling(5).mean()
            df['ma10'] = df['close'].rolling(10).mean()
            df['ma20'] = df['close'].rolling(20).mean()
            df['volume_ma5'] = df['volume'].rolling(5).mean()
            
            # 计算RSI
            delta = df['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=6).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
            rs = gain / loss
            df['rsi'] = 100 - (100 / (1 + rs))
            
            # 寻找信号点（简化版）
            for i in range(20, len(df)):
                row = df.iloc[i]
                prev = df.iloc[i-1]
                
                # 基础条件检查
                volume_ratio = row['volume'] / row['volume_ma5'] if row['volume_ma5'] > 0 else 0
                rsi = row['rsi']
                
                # 策略特定条件
                if self.strategy_name == "趋势跟踪":
                    # MA5>MA10>MA20，RSI 45-75，放量
                    if (row['ma5'] > row['ma10'] > row['ma20'] and 
                        45 <= rsi <= 75 and volume_ratio >= 1.5):
                        signals.append({
                            'stock_code': stock_code,
                            'entry_date': row['timestamp'],
                            'entry_price': row['close'],
                            'rsi': rsi,
                            'volume_ratio': volume_ratio
                        })
                        break
                        
                elif self.strategy_name == "均值回归":
                    # RSI<30，超卖反弹
                    if rsi < 30 and volume_ratio >= 1.2:
                        signals.append({
                            'stock_code': stock_code,
                            'entry_date': row['timestamp'],
                            'entry_price': row['close'],
                            'rsi': rsi,
                            'volume_ratio': volume_ratio
                        })
                        break
                        
                elif self.strategy_name == "突破策略":
                    # 放量突破近期高点
                    recent_high = df.iloc[i-5:i]['high'].max()
                    if row['close'] > recent_high and volume_ratio >= 2.0:
                        signals.append({
                            'stock_code': stock_code,
                            'entry_date': row['timestamp'],
                            'entry_price': row['close'],
                            'rsi': rsi,
                            'volume_ratio': volume_ratio
                        })
                        break
                        
                elif self.strategy_name == "稳健增长":
                    # MA20斜率向上，RSI 45-55
                    ma20_slope = (row['ma20'] - df.iloc[i-5]['ma20']) / df.iloc[i-5]['ma20']
                    if ma20_slope > 0.003 and 45 <= rsi <= 55:
                        signals.append({
                            'stock_code': stock_code,
                            'entry_date': row['timestamp'],
                            'entry_price': row['close'],
                            'rsi': rsi,
                            'volume_ratio': volume_ratio
                        })
                        break
                        
                elif self.strategy_name == "热点追击":
                    # 高放量，RSI>55
                    if volume_ratio >= 3.0 and rsi > 55:
                        signals.append({
                            'stock_code': stock_code,
                            'entry_date': row['timestamp'],
                            'entry_price': row['close'],
                            'rsi': rsi,
                            'volume_ratio': volume_ratio
                        })
                        break
        
        conn.close()
        
        print(f"  生成 {len(signals)} 个信号")
        return signals[:100]  # 最多100个
    
    def simulate_trade(self, signal: Dict) -> Dict:
        """模拟单笔交易"""
        conn = sqlite3.connect(REAL_DB)
        
        # 获取入场后的数据
        df = pd.read_sql_query(f"""
            SELECT * FROM daily
            WHERE stock_code = '{signal['stock_code']}'
            AND timestamp > '{signal['entry_date']}'
            ORDER BY timestamp
            LIMIT 30
        """, conn)
        
        conn.close()
        
        if len(df) == 0:
            return None
        
        entry_price = signal['entry_price']
        
        # 计算止盈目标
        tp_levels = calculate_take_profit_levels(entry_price, self.strategy_name)
        
        # 模拟持仓
        position = 1.0  # 100%仓位
        exit_price = None
        exit_date = None
        exit_reason = None
        max_profit = 0
        max_loss = 0
        
        for i, row in df.iterrows():
            current_price = row['close']
            profit_pct = (current_price - entry_price) / entry_price
            
            # 更新最大盈亏
            max_profit = max(max_profit, profit_pct)
            max_loss = min(max_loss, profit_pct)
            
            # 检查止损
            stop_price, stop_type = calculate_stop_loss_price(
                entry_price, self.strategy_name, current_price
            )
            
            if current_price <= stop_price:
                exit_price = current_price
                exit_date = row['timestamp']
                exit_reason = f"止损({stop_type})"
                break
            
            # 检查止盈目标1
            if position >= 0.7 and current_price >= tp_levels['target_1']['price']:
                position -= 0.3  # 卖出30%
                if position <= 0.1:
                    exit_price = current_price
                    exit_date = row['timestamp']
                    exit_reason = "止盈目标1"
                    break
            
            # 检查止盈目标2
            if position >= 0.3 and current_price >= tp_levels['target_2']['price']:
                position -= 0.4  # 卖出40%
                if position <= 0.1:
                    exit_price = current_price
                    exit_date = row['timestamp']
                    exit_reason = "止盈目标2"
                    break
            
            # 检查止盈目标3
            if current_price >= tp_levels['target_3']['price']:
                exit_price = current_price
                exit_date = row['timestamp']
                exit_reason = "止盈目标3"
                break
            
            # 时间止损
            if i >= self.strategy["take_profit"].time_exit_days - 1:
                exit_price = current_price
                exit_date = row['timestamp']
                exit_reason = "时间止损"
                break
        
        # 如果未触发任何条件，以最后价格结算
        if exit_price is None and len(df) > 0:
            exit_price = df.iloc[-1]['close']
            exit_date = df.iloc[-1]['timestamp']
            exit_reason = "持有期末"
        
        if exit_price:
            final_profit = (exit_price - entry_price) / entry_price
            return {
                'stock_code': signal['stock_code'],
                'entry_date': signal['entry_date'],
                'entry_price': entry_price,
                'exit_date': exit_date,
                'exit_price': exit_price,
                'profit_pct': final_profit * 100,
                'max_profit_pct': max_profit * 100,
                'max_loss_pct': max_loss * 100,
                'exit_reason': exit_reason,
                'holding_days': len(df)
            }
        
        return None
    
    def run_backtest(self) -> Dict:
        """运行回测"""
        print(f"\n{'='*70}")
        print(f"🀆 白板回测: {self.strategy_name}")
        print(f"{'='*70}")
        
        signals = self.get_historical_signals(100)
        
        if len(signals) == 0:
            print(f"❌ 未找到信号")
            return {}
        
        print(f"\n📊 回测 {len(signals)} 笔交易...")
        
        results = []
        for i, signal in enumerate(signals, 1):
            result = self.simulate_trade(signal)
            if result:
                results.append(result)
            if i % 20 == 0:
                print(f"  进度: {i}/{len(signals)}")
        
        if len(results) == 0:
            print(f"❌ 无有效交易结果")
            return {}
        
        # 计算统计指标
        profits = [r['profit_pct'] for r in results]
        winning_trades = [p for p in profits if p > 0]
        losing_trades = [p for p in profits if p <= 0]
        
        total_return = sum(profits)
        avg_return = np.mean(profits)
        win_rate = len(winning_trades) / len(profits) * 100
        
        avg_win = np.mean(winning_trades) if winning_trades else 0
        avg_loss = np.mean(losing_trades) if losing_trades else 0
        profit_factor = abs(sum(winning_trades) / sum(losing_trades)) if sum(losing_trades) != 0 else float('inf')
        
        max_drawdown = min([r['max_loss_pct'] for r in results])
        avg_holding = np.mean([r['holding_days'] for r in results])
        
        # 退出原因统计
        exit_reasons = {}
        for r in results:
            reason = r['exit_reason']
            exit_reasons[reason] = exit_reasons.get(reason, 0) + 1
        
        report = {
            'strategy': self.strategy_name,
            'total_trades': len(results),
            'win_rate': win_rate,
            'avg_return': avg_return,
            'total_return': total_return,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'profit_factor': profit_factor,
            'max_drawdown': max_drawdown,
            'avg_holding_days': avg_holding,
            'exit_reasons': exit_reasons,
            'monthly_target': self.strategy["monthly_target"] * 100,
            'trades': results
        }
        
        return report


def generate_full_report(all_reports: List[Dict]):
    """生成完整回测报告"""
    report_file = REPORT_DIR / f"backtest_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("# 🀆 白板 - 5策略回测报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("---\n\n")
        
        # 总览
        f.write("## 📊 策略总览\n\n")
        f.write("| 策略 | 交易数 | 胜率 | 平均收益 | 总收益 | 盈亏比 | 最大回撤 | 目标达成 |\n")
        f.write("|------|--------|------|----------|--------|--------|----------|----------|\n")
        
        for report in all_reports:
            target_achieved = "✅" if report['avg_return'] >= report['monthly_target'] else "❌"
            f.write(f"| {report['strategy']} | {report['total_trades']} | {report['win_rate']:.1f}% | "
                   f"{report['avg_return']:.2f}% | {report['total_return']:.2f}% | "
                   f"{report['profit_factor']:.2f} | {report['max_drawdown']:.2f}% | {target_achieved} |\n")
        
        f.write("\n---\n\n")
        
        # 详细报告
        for report in all_reports:
            f.write(f"## 📈 {report['strategy']} 详细报告\n\n")
            f.write(f"**月目标**: {report['monthly_target']:.1f}%\n\n")
            
            f.write("### 核心指标\n\n")
            f.write(f"- **交易次数**: {report['total_trades']}\n")
            f.write(f"- **胜率**: {report['win_rate']:.1f}%\n")
            f.write(f"- **平均收益**: {report['avg_return']:.2f}%\n")
            f.write(f"- **总收益**: {report['total_return']:.2f}%\n")
            f.write(f"- **平均盈利**: {report['avg_win']:.2f}%\n")
            f.write(f"- **平均亏损**: {report['avg_loss']:.2f}%\n")
            f.write(f"- **盈亏比**: {report['profit_factor']:.2f}\n")
            f.write(f"- **最大回撤**: {report['max_drawdown']:.2f}%\n")
            f.write(f"- **平均持仓**: {report['avg_holding_days']:.1f}天\n\n")
            
            f.write("### 退出原因分布\n\n")
            for reason, count in report['exit_reasons'].items():
                pct = count / report['total_trades'] * 100
                f.write(f"- {reason}: {count}次 ({pct:.1f}%)\n")
            
            f.write("\n---\n\n")
        
        # 结论
        f.write("## 📝 结论与建议\n\n")
        
        achieved = [r for r in all_reports if r['avg_return'] >= r['monthly_target']]
        not_achieved = [r for r in all_reports if r['avg_return'] < r['monthly_target']]
        
        f.write(f"**目标达成**: {len(achieved)}/5 个策略\n\n")
        
        if achieved:
            f.write("✅ **达标策略**:\n")
            for r in achieved:
                f.write(f"  - {r['strategy']}: 平均收益{r['avg_return']:.2f}% (目标{r['monthly_target']:.1f}%)\n")
            f.write("\n")
        
        if not_achieved:
            f.write("❌ **未达标策略**:\n")
            for r in not_achieved:
                f.write(f"  - {r['strategy']}: 平均收益{r['avg_return']:.2f}% (目标{r['monthly_target']:.1f}%)\n")
            f.write("\n")
        
        f.write("### 优化建议\n\n")
        f.write("1. **参数微调**: 根据回测结果调整RSI区间和均线周期\n")
        f.write("2. **仓位管理**: 胜率高的策略可增加仓位，反之降低\n")
        f.write("3. **市场环境**: 不同策略适应不同市场环境，需动态切换\n")
        f.write("4. **止损优化**: 部分策略止损过宽，可收紧以保护本金\n\n")
    
    print(f"\n📄 报告已保存: {report_file}")
    return report_file


def main():
    """主程序"""
    print("="*70)
    print("🀆 白板 - 5策略回测系统")
    print("="*70)
    
    strategies = ["趋势跟踪", "均值回归", "突破策略", "稳健增长", "热点追击"]
    all_reports = []
    
    for strategy_name in strategies:
        backtester = StrategyBacktester(strategy_name)
        report = backtester.run_backtest()
        if report:
            all_reports.append(report)
    
    if all_reports:
        report_file = generate_full_report(all_reports)
        
        # 打印摘要
        print("\n" + "="*70)
        print("📊 回测摘要")
        print("="*70)
        for report in all_reports:
            status = "✅" if report['avg_return'] >= report['monthly_target'] else "❌"
            print(f"{status} {report['strategy']}: 胜率{report['win_rate']:.1f}%, "
                  f"平均收益{report['avg_return']:.2f}% (目标{report['monthly_target']:.1f}%)")
        print("="*70)


if __name__ == '__main__':
    main()
