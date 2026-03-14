#!/usr/bin/env python3
"""
多策略回测系统 - 验证5种策略的历史表现
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
import statistics

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from strategy_config import STRATEGIES, get_strategy

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("策略回测")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class StrategyBacktest:
    """策略回测器"""
    
    def __init__(self, strategy_name: str):
        self.strategy = get_strategy(strategy_name)
        self.strategy_name = strategy_name
        self.db_path = BEIFENG_DB
    
    def get_historical_signals(self, test_date: str, max_stocks: int = 200) -> list:
        """获取历史日期的信号"""
        try:
            from nanfeng_v5_1 import NanFengV5_1
            
            # 创建临时V5.1实例，使用指定策略
            v51 = NanFengV5_1(use_realtime=False, strategy_name=self.strategy_name)
            
            # 获取股票列表
            import sqlite3
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT stock_code 
                FROM kline_data 
                WHERE data_type = 'daily'
                LIMIT ?
            """, (max_stocks,))
            stock_codes = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            # 加载历史数据
            all_data = {}
            for code in stock_codes:
                df = self._get_historical_data(code, test_date)
                if df is not None:
                    all_data[code] = df
            
            # 分析信号
            signals = []
            for code, df in all_data.items():
                try:
                    signal = v51.analyze_stock(code, df, all_data)
                    if signal:
                        future_return = self._get_future_return(code, test_date)
                        if future_return is not None:
                            signals.append({
                                'code': code,
                                'score': signal.total_score,
                                'entry_price': signal.current_price,
                                'future_return': future_return,
                                'adx': signal.adx,
                                'rsi': signal.rsi
                            })
                except:
                    continue
            
            # 排序并取Top
            signals.sort(key=lambda x: x['score'], reverse=True)
            return signals[:5]  # 取Top 5
            
        except Exception as e:
            logger.error(f"获取历史信号失败: {e}")
            return []
    
    def _get_historical_data(self, stock_code: str, end_date: str, days: int = 60):
        """获取历史数据"""
        try:
            import sqlite3
            import pandas as pd
            
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp <= ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(stock_code, end_date, days + 15))
            conn.close()
            
            if len(df) < 30:
                return None
            
            return df.sort_values('timestamp').reset_index(drop=True)
        except:
            return None
    
    def _get_future_return(self, stock_code: str, entry_date: str) -> float:
        """获取未来收益（根据策略持有周期）"""
        try:
            import sqlite3
            
            # 解析持有周期
            holding_days = self._parse_holding_period()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取入场价格
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp = ?
            """, (stock_code, entry_date))
            row = cursor.fetchone()
            if not row:
                return None
            entry_price = row[0]
            
            # 获取N日后的价格
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp > ?
                ORDER BY timestamp
                LIMIT 1 OFFSET ?
            """, (stock_code, entry_date, holding_days - 1))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return (row[0] / entry_price - 1) * 100
        except:
            return None
    
    def _parse_holding_period(self) -> int:
        """解析持有周期为天数"""
        period = self.strategy.holding_period
        if "周" in period:
            # 2-4周 -> 取中间值3周 = 21天
            return 15
        elif "天" in period:
            # 提取数字
            import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("南风")

            numbers = re.findall(r'\d+', period)
            if numbers:
                return int(sum(map(int, numbers)) / len(numbers))
        return 5  # 默认5天
    
    def run_backtest(self, test_dates: list) -> dict:
        """运行回测"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🎯 策略回测: {self.strategy_name}")
        logger.info(f"{'='*60}")
        logger.info(f"策略描述: {self.strategy.description}")
        logger.info(f"持有周期: {self.strategy.holding_period}")
        logger.info(f"风险等级: {self.strategy.risk_level}")
        logger.info(f"{'='*60}\n")
        
        all_results = []
        
        for date in test_dates:
            signals = self.get_historical_signals(date)
            if signals:
                avg_return = statistics.mean([s['future_return'] for s in signals])
                win_rate = len([s for s in signals if s['future_return'] > 0]) / len(signals) * 100
                
                all_results.append({
                    'date': date,
                    'signals': signals,
                    'avg_return': avg_return,
                    'win_rate': win_rate
                })
                
                logger.info(f"{date}: {len(signals)}只信号, 平均收益{avg_return:+.2f}%, 胜率{win_rate:.1f}%")
        
        # 汇总统计
        if all_results:
            returns = [r['avg_return'] for r in all_results]
            win_rates = [r['win_rate'] for r in all_results]
            
            summary = {
                'strategy': self.strategy_name,
                'test_days': len(all_results),
                'avg_return': statistics.mean(returns),
                'avg_win_rate': statistics.mean(win_rates),
                'best_day': max(returns),
                'worst_day': min(returns),
                'win_rate_over_50': len([w for w in win_rates if w > 50]) / len(win_rates) * 100,
                'holding_period': self.strategy.holding_period,
                'risk_level': self.strategy.risk_level
            }
            
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 {self.strategy_name} 回测汇总")
            logger.info(f"{'='*60}")
            logger.info(f"测试天数: {summary['test_days']}")
            logger.info(f"平均收益: {summary['avg_return']:+.2f}%")
            logger.info(f"平均胜率: {summary['avg_win_rate']:.1f}%")
            logger.info(f"胜率>50%天数: {summary['win_rate_over_50']:.1f}%")
            logger.info(f"最佳单日: {summary['best_day']:+.2f}%")
            logger.info(f"最差单日: {summary['worst_day']:+.2f}%")
            logger.info(f"{'='*60}\n")
            
            return summary
        
        return None


def run_all_strategies_backtest():
    """运行所有策略回测"""
    # 测试日期
    test_dates = [
        '2026-03-03', '2026-02-27', '2026-02-24', '2026-02-21',
        '2026-02-18', '2026-02-13', '2026-02-10', '2026-02-07'
    ]
    
    logger.info("\n" + "="*70)
    logger.info("🌬️ 南风V5.1 多策略回测系统")
    logger.info("="*70)
    
    results = []
    
    for strategy_name in STRATEGIES.keys():
        backtest = StrategyBacktest(strategy_name)
        result = backtest.run_backtest(test_dates)
        if result:
            results.append(result)
    
    # 对比报告
    logger.info("\n" + "="*70)
    logger.info("📊 策略对比报告")
    logger.info("="*70)
    
    # 按平均收益排序
    results.sort(key=lambda x: x['avg_return'], reverse=True)
    
    for i, r in enumerate(results, 1):
        logger.info(f"\n{i}. {r['strategy']} ({r['risk_level']}风险)")
        logger.info(f"   平均收益: {r['avg_return']:+.2f}% | 胜率: {r['avg_win_rate']:.1f}%")
        logger.info(f"   持有周期: {r['holding_period']} | 胜率>50%天数: {r['win_rate_over_50']:.1f}%")
    
    # 保存结果
    output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/strategy_backtest_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'backtest_date': datetime.now().isoformat(),
            'test_dates': test_dates,
            'results': results
        }, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n💾 结果已保存: {output_file}")
    logger.info("="*70 + "\n")
    
    return results


if __name__ == '__main__':
    run_all_strategies_backtest()
