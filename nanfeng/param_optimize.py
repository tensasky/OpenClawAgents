#!/usr/bin/env python3
"""
南风V5参数优化 - 网格搜索最佳参数组合
"""

import sqlite3
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import statistics
from concurrent.futures import ProcessPoolExecutor, as_completed
import itertools

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5 import NanFengV5

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"param_opt_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风参数优化")


class ParameterOptimizer:
    """参数优化器"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        
        # 参数搜索空间
        self.param_grid = {
            'min_adx': [20, 25, 30],           # 趋势强度门槛
            'min_ma20_slope': [0.0005, 0.001, 0.002],  # MA20斜率
            'min_volume_ratio': [1.0, 1.2, 1.5],       # 最小放量
            'score_threshold': [7.0, 7.5, 8.0]         # 买入门槛
        }
        
        # 测试日期（选择有代表性的市场阶段）
        self.test_dates = [
            '2026-02-20',  # 上涨期
            '2026-02-27',  # 震荡期
            '2026-03-03',  # 近期
        ]
    
    def get_stock_data(self, stock_code: str, end_date: str, days: int = 60):
        """获取历史数据"""
        try:
            import pandas as pd
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("南风")

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
        except Exception as e:
            return None
    
    def get_future_return(self, stock_code: str, entry_date: str, hold_days: int = 5) -> Optional[float]:
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
    
    def test_params(self, params: Dict, test_date: str, max_stocks: int = 100) -> Dict:
        """测试一组参数"""
        # 创建临时V5实例
        v5 = NanFengV5()
        v5.min_adx = params['min_adx']
        v5.min_ma20_slope = params['min_ma20_slope']
        v5.min_volume_ratio = params['min_volume_ratio']
        
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
        
        # 分析并计算收益
        results = []
        for code, df in all_data.items():
            try:
                signal = v5.analyze_stock(code, df, all_data)
                if signal and signal.total_score >= params['score_threshold']:
                    future_ret = self.get_future_return(code, test_date + 'T00:00:00', 5)
                    if future_ret is not None:
                        results.append({
                            'code': code,
                            'score': signal.total_score,
                            'return': future_ret
                        })
            except:
                continue
        
        if not results:
            return {'params': params, 'date': test_date, 'avg_return': -999, 'win_rate': 0, 'count': 0}
        
        returns = [r['return'] for r in results]
        avg_return = statistics.mean(returns)
        win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
        
        return {
            'params': params,
            'date': test_date,
            'avg_return': avg_return,
            'win_rate': win_rate,
            'count': len(results),
            'max_return': max(returns),
            'min_return': min(returns)
        }
    
    def grid_search(self):
        """网格搜索最佳参数"""
        logger.info("=" * 80)
        logger.info("🎯 南风V5参数优化 - 网格搜索")
        logger.info("=" * 80)
        
        # 生成所有参数组合
        keys = list(self.param_grid.keys())
        values = list(self.param_grid.values())
        param_combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        logger.info(f"参数组合数: {len(param_combinations)}")
        logger.info(f"测试日期: {self.test_dates}")
        logger.info(f"总测试次数: {len(param_combinations) * len(self.test_dates)}")
        
        # 收集所有测试结果
        all_results = []
        
        for date in self.test_dates:
            logger.info(f"\n📅 测试日期: {date}")
            
            for i, params in enumerate(param_combinations):
                result = self.test_params(params, date, max_stocks=150)
                all_results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"  进度: {i+1}/{len(param_combinations)} - "
                              f"收益: {result['avg_return']:+.2f}%, 胜率: {result['win_rate']:.1f}%")
        
        # 汇总分析
        self._analyze_results(all_results)
    
    def _analyze_results(self, results: List[Dict]):
        """分析所有测试结果"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 参数优化结果汇总")
        logger.info("=" * 80)
        
        # 按参数组合分组
        param_groups = {}
        for r in results:
            key = tuple(sorted(r['params'].items()))
            if key not in param_groups:
                param_groups[key] = []
            param_groups[key].append(r)
        
        # 计算每个参数组合的平均表现
        summary = []
        for key, group in param_groups.items():
            params = dict(key)
            avg_returns = [r['avg_return'] for r in group if r['avg_return'] > -900]
            avg_win_rates = [r['win_rate'] for r in group if r['avg_return'] > -900]
            total_count = sum(r['count'] for r in group)
            
            if avg_returns:
                summary.append({
                    'params': params,
                    'avg_return': statistics.mean(avg_returns),
                    'avg_win_rate': statistics.mean(avg_win_rates),
                    'min_return': min(avg_returns),
                    'total_signals': total_count
                })
        
        # 排序：优先胜率>50%，然后按收益排序
        summary.sort(key=lambda x: (x['avg_win_rate'] > 50, x['avg_return']), reverse=True)
        
        # 显示Top 10
        logger.info("\n🏆 Top 10 参数组合:")
        for i, s in enumerate(summary[:10], 1):
            logger.info(f"\n  {i}. 平均收益: {s['avg_return']:+.2f}%, 胜率: {s['avg_win_rate']:.1f}%, "
                       f"信号数: {s['total_signals']}")
            logger.info(f"     参数: ADX>={s['params']['min_adx']}, "
                       f"MA20斜率>={s['params']['min_ma20_slope']}, "
                       f"量比>={s['params']['min_volume_ratio']}, "
                       f"分数>={s['params']['score_threshold']}")
        
        # 保存结果
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/param_optimization.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'optimization_date': datetime.now().isoformat(),
                'top_params': summary[:10],
                'all_results': summary
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 结果已保存: {output_file}")
        
        # 返回最佳参数
        if summary:
            return summary[0]['params']
        return None


def main():
    """主函数"""
    optimizer = ParameterOptimizer()
    best_params = optimizer.grid_search()
    
    if best_params:
        log.info("\n" + "=" * 80)
        log.info("🎯 最佳参数组合:")
        log.info("=" * 80)
        for k, v in best_params.items():
            log.info(f"  {k}: {v}")
        log.info("=" * 80)


if __name__ == "__main__":
    main()
