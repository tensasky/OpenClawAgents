#!/usr/bin/env python3
"""
南风V5批量历史回测 - 验证策略稳定性
测试多个历史日期，统计胜率、收益率分布
"""

import sqlite3
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import statistics

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5 import NanFengV5

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"batch_backtest_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风批量回测")


class BatchBacktest:
    """批量回测器"""
    
    def __init__(self):
        self.v5 = NanFengV5()
        self.db_path = BEIFENG_DB
        
        # 选择测试日期（最近20个交易日，每周一个）
        self.test_dates = self._get_test_dates(20)
    
    def _get_test_dates(self, count: int) -> List[str]:
        """获取测试日期列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取最近的交易日期
        cursor.execute("""
            SELECT DISTINCT timestamp 
            FROM kline_data 
            WHERE data_type = 'daily'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (count * 2,))
        
        dates = [row[0][:10] for row in cursor.fetchall()]
        conn.close()
        
        # 每隔3天取一个，确保有足够未来数据
        return dates[::3][:count]
    
    def get_stock_data(self, stock_code: str, end_date: str, days: int = 60):
        """获取历史数据"""
        try:
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
    
    def get_future_return(self, stock_code: str, entry_date: str, hold_days: int = 5) -> float:
        """获取未来N日收益率"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp = ?
            """, (stock_code, entry_date))
            row = cursor.fetchone()
            if not row:
                return None
            entry_price = row[0]
            
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp > ?
                ORDER BY timestamp
                LIMIT 1 OFFSET ?
            """, (stock_code, entry_date, hold_days - 1))
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            return (row[0] / entry_price - 1) * 100
        except:
            return None
    
    def run_single_backtest(self, test_date: str, max_stocks: int = 150) -> Dict:
        """运行单日回测"""
        logger.info(f"\n📅 回测日期: {test_date}")
        
        # 获取股票列表
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
        
        # 加载数据
        all_data = {}
        for code in stock_codes:
            df = self.get_stock_data(code, test_date + 'T00:00:00', days=40)
            if df is not None:
                all_data[code] = df
        
        # 分析
        results = []
        for code, df in all_data.items():
            try:
                signal = self.v5.analyze_stock(code, df, all_data)
                if signal:
                    future_ret = self.get_future_return(code, test_date + 'T00:00:00', 5)
                    if future_ret is not None:
                        results.append({
                            'code': code,
                            'score': signal.total_score,
                            'return': future_ret,
                            'adx': signal.adx,
                            'rsi': signal.rsi
                        })
            except:
                continue
        
        # 按门槛分组统计
        thresholds = [7.5, 8.0, 8.5, 9.0]
        stats = {}
        
        for thresh in thresholds:
            selected = [r for r in results if r['score'] >= thresh]
            if selected:
                returns = [r['return'] for r in selected]
                stats[f'thresh_{thresh}'] = {
                    'count': len(selected),
                    'avg_return': statistics.mean(returns),
                    'win_rate': len([r for r in returns if r > 0]) / len(returns) * 100,
                    'max_return': max(returns),
                    'min_return': min(returns)
                }
            else:
                stats[f'thresh_{thresh}'] = {'count': 0}
        
        return {
            'date': test_date,
            'stats': stats,
            'total_analyzed': len(results)
        }
    
    def run_batch_backtest(self):
        """运行批量回测"""
        logger.info("=" * 80)
        logger.info("🌬️ 南风V5批量历史回测")
        logger.info(f"测试日期数: {len(self.test_dates)}")
        logger.info("=" * 80)
        
        all_results = []
        
        for i, date in enumerate(self.test_dates):
            result = self.run_single_backtest(date, max_stocks=150)
            all_results.append(result)
            
            # 显示进度
            for thresh, stat in result['stats'].items():
                if stat.get('count', 0) > 0:
                    logger.info(f"  {thresh}: 信号{stat['count']}个, "
                              f"收益{stat['avg_return']:+.2f}%, 胜率{stat['win_rate']:.1f}%")
        
        # 汇总分析
        self._summarize_results(all_results)
        return all_results
    
    def _summarize_results(self, results: List[Dict]):
        """汇总所有回测结果"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 批量回测汇总")
        logger.info("=" * 80)
        
        thresholds = [7.5, 8.0, 8.5, 9.0]
        
        for thresh in thresholds:
            key = f'thresh_{thresh}'
            
            # 收集所有日期的数据
            all_returns = []
            all_win_rates = []
            all_counts = []
            
            for r in results:
                if key in r['stats'] and r['stats'][key].get('count', 0) > 0:
                    stat = r['stats'][key]
                    all_returns.append(stat['avg_return'])
                    all_win_rates.append(stat['win_rate'])
                    all_counts.append(stat['count'])
            
            if all_returns:
                logger.info(f"\n🎯 门槛 {thresh}分:")
                logger.info(f"  测试天数: {len(all_returns)}")
                logger.info(f"  平均信号数: {statistics.mean(all_counts):.1f}")
                logger.info(f"  平均收益率: {statistics.mean(all_returns):+.2f}%")
                logger.info(f"  收益率标准差: {statistics.stdev(all_returns) if len(all_returns) > 1 else 0:.2f}%")
                logger.info(f"  平均胜率: {statistics.mean(all_win_rates):.1f}%")
                logger.info(f"  胜率>50%的天数: {len([w for w in all_win_rates if w > 50])}/{len(all_win_rates)}")
                logger.info(f"  最佳单日收益: {max(all_returns):+.2f}%")
                logger.info(f"  最差单日收益: {min(all_returns):+.2f}%")
        
        # 保存详细结果
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/batch_backtest_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'backtest_date': datetime.now().isoformat(),
                'test_dates': self.test_dates,
                'results': results
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 详细结果已保存: {output_file}")


def main():
    """主函数"""
    backtest = BatchBacktest()
    results = backtest.run_batch_backtest()
    
    print("\n" + "=" * 80)
    print("🌬️ 批量回测完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
