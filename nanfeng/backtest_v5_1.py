#!/usr/bin/env python3
"""
南风V5.1批量回测 - 验证精选策略
"""

import sqlite3
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import statistics

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5_1 import NanFengV5_1

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"backtest_v5_1_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风回测V5.1")


class V51Backtest:
    """V5.1回测器"""
    
    def __init__(self):
        self.v51 = NanFengV5_1()
        self.db_path = BEIFENG_DB
    
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
    
    def run_backtest(self, test_dates: List[str], max_stocks: int = 200):
        """运行批量回测"""
        logger.info("=" * 80)
        logger.info("🌬️ 南风V5.1批量回测 - 精选Top 5策略")
        logger.info("=" * 80)
        
        all_results = []
        
        for date in test_dates:
            logger.info(f"\n📅 回测日期: {date}")
            
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
                df = self.get_stock_data(code, date + 'T00:00:00', days=40)
                if df is not None:
                    all_data[code] = df
            
            # 分析所有股票
            signals = []
            for code, df in all_data.items():
                try:
                    signal = self.v51.analyze_stock(code, df, all_data)
                    if signal:
                        future_ret = self.get_future_return(code, date + 'T00:00:00', 5)
                        if future_ret is not None:
                            signals.append({
                                'code': code,
                                'score': signal.total_score,
                                'return': future_ret,
                                'is_hot': signal.is_hot_sector
                            })
                except:
                    continue
            
            # 排序并取Top 5
            signals.sort(key=lambda x: x['score'], reverse=True)
            top5 = signals[:5]
            
            if top5:
                returns = [s['return'] for s in top5]
                avg_return = statistics.mean(returns)
                win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
                
                logger.info(f"  Top 5 信号: {len(top5)}个")
                logger.info(f"  平均收益: {avg_return:+.2f}% | 胜率: {win_rate:.1f}%")
                for i, s in enumerate(top5, 1):
                    hot_tag = "🔥" if s['is_hot'] else ""
                    logger.info(f"    {i}. {s['code']}: {s['score']:.1f}分 -> {s['return']:+.2f}% {hot_tag}")
                
                all_results.append({
                    'date': date,
                    'signals': top5,
                    'avg_return': avg_return,
                    'win_rate': win_rate
                })
            else:
                logger.info("  无信号")
        
        # 汇总
        self._summarize(all_results)
        return all_results
    
    def _summarize(self, results: List[Dict]):
        """汇总结果"""
        if not results:
            logger.warning("无回测结果")
            return
        
        logger.info("\n" + "=" * 80)
        logger.info("📊 V5.1回测汇总")
        logger.info("=" * 80)
        
        avg_returns = [r['avg_return'] for r in results]
        win_rates = [r['win_rate'] for r in results]
        
        logger.info(f"测试天数: {len(results)}")
        logger.info(f"平均收益率: {statistics.mean(avg_returns):+.2f}%")
        logger.info(f"收益率标准差: {statistics.stdev(avg_returns) if len(avg_returns) > 1 else 0:.2f}%")
        logger.info(f"平均胜率: {statistics.mean(win_rates):.1f}%")
        logger.info(f"胜率>50%天数: {len([w for w in win_rates if w > 50])}/{len(win_rates)}")
        logger.info(f"最佳单日: {max(avg_returns):+.2f}%")
        logger.info(f"最差单日: {min(avg_returns):+.2f}%")
        
        # 保存结果
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/backtest_v5_1_results.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'backtest_date': datetime.now().isoformat(),
                'version': 'V5.1',
                'summary': {
                    'test_days': len(results),
                    'avg_return': statistics.mean(avg_returns),
                    'avg_win_rate': statistics.mean(win_rates),
                    'best_day': max(avg_returns),
                    'worst_day': min(avg_returns)
                },
                'results': results
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 结果已保存: {output_file}")


def main():
    """主函数"""
    backtest = V51Backtest()
    
    # 测试最近12个交易日
    test_dates = [
        '2026-03-03', '2026-02-27', '2026-02-24', '2026-02-21',
        '2026-02-18', '2026-02-13', '2026-02-10', '2026-02-07',
        '2026-02-04', '2026-01-30', '2026-01-27', '2026-01-24'
    ]
    
    backtest.run_backtest(test_dates, max_stocks=200)
    
    print("\n" + "=" * 80)
    print("🌬️ V5.1回测完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
