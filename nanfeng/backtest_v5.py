#!/usr/bin/env python3
"""
南风V5回测 - 验证新策略准确度
对比V4和V5的表现
"""

import sqlite3
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import statistics

# 添加nanfeng目录到路径
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5 import NanFengV5, TradeSignal

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"backtest_v5_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风回测V5")


class NanFengV5Backtest:
    """V5回测器"""
    
    def __init__(self):
        self.v5 = NanFengV5()
        self.db_path = BEIFENG_DB
    
    def get_stock_data_historical(self, stock_code: str, end_date: str, days: int = 60) -> Optional[object]:
        """获取历史数据（用于回测）"""
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
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            return df
        except Exception as e:
            logger.debug(f"获取 {stock_code} 历史数据失败: {e}")
            return None
    
    def get_future_return(self, stock_code: str, entry_date: str, hold_days: int = 5) -> Optional[float]:
        """获取未来N日收益率"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取入场日收盘价
            cursor.execute("""
                SELECT close FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                AND timestamp = ?
            """, (stock_code, entry_date))
            row = cursor.fetchone()
            if not row:
                return None
            entry_price = row[0]
            
            # 获取N日后的收盘价
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
            exit_price = row[0]
            
            return (exit_price / entry_price - 1) * 100
        except Exception as e:
            logger.debug(f"获取 {stock_code} 未来收益失败: {e}")
            return None
    
    def run_backtest(self, test_date: str = None, hold_days: int = 5, max_stocks: int = 200):
        """运行回测"""
        if test_date is None:
            # 使用最近有数据的日期
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(timestamp) FROM kline_data WHERE data_type='daily'")
            test_date = cursor.fetchone()[0]
            conn.close()
        
        logger.info("=" * 80)
        logger.info(f"🌬️ 南风V5回测 - 测试日期: {test_date}")
        logger.info(f"持有期: {hold_days}天 | 扫描股票数: {max_stocks}")
        logger.info("=" * 80)
        
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
        
        logger.info(f"测试股票数: {len(stock_codes)}")
        
        # 预加载数据
        all_data = {}
        for code in stock_codes:
            df = self.get_stock_data_historical(code, test_date, days=40)
            if df is not None:
                all_data[code] = df
        
        logger.info(f"成功加载 {len(all_data)} 只股票数据")
        
        # 分析每只股票
        results = []
        for i, (code, df) in enumerate(all_data.items()):
            try:
                signal = self.v5.analyze_stock(code, df, all_data)
                if signal:
                    # 获取未来收益
                    future_return = self.get_future_return(code, test_date, hold_days)
                    
                    results.append({
                        'code': code,
                        'score': signal.total_score,
                        'trend_score': signal.trend_score,
                        'momentum_score': signal.momentum_score,
                        'volume_score': signal.volume_score,
                        'adx': signal.adx,
                        'rsi': signal.rsi,
                        'ma20_slope': signal.ma20_slope,
                        'relative_strength': signal.relative_strength,
                        'price': signal.current_price,
                        'signals': signal.signals,
                        'warnings': signal.warnings,
                        'future_return': future_return
                    })
                
                if (i + 1) % 50 == 0:
                    logger.info(f"进度: {i+1}/{len(all_data)}")
                    
            except Exception as e:
                logger.debug(f"分析 {code} 失败: {e}")
                continue
        
        # 分析结果
        self._analyze_results(results, hold_days)
        return results
    
    def _analyze_results(self, results: List[Dict], hold_days: int):
        """分析回测结果"""
        if not results:
            logger.warning("无回测结果")
            return
        
        logger.info("=" * 80)
        logger.info("📊 V5回测结果分析")
        logger.info("=" * 80)
        
        # 按分数分组
        score_thresholds = [8.5, 8.0, 7.5, 7.0]
        
        for threshold in score_thresholds:
            selected = [r for r in results if r['score'] >= threshold and r['future_return'] is not None]
            not_selected = [r for r in results if r['score'] < threshold and r['future_return'] is not None]
            
            logger.info(f"\n🎯 门槛: {threshold}分")
            logger.info(f"  选中数: {len(selected)} | 未选中: {len(not_selected)}")
            
            if selected:
                returns = [r['future_return'] for r in selected]
                avg_return = statistics.mean(returns)
                win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
                max_return = max(returns)
                min_return = min(returns)
                
                logger.info(f"  ✅ 选中股票: 平均收益 {avg_return:+.2f}%, 胜率 {win_rate:.1f}%")
                logger.info(f"     最高: {max_return:+.2f}% | 最低: {min_return:+.2f}%")
            
            if not_selected:
                returns = [r['future_return'] for r in not_selected]
                avg_return = statistics.mean(returns)
                win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
                
                logger.info(f"  ❌ 未选中: 平均收益 {avg_return:+.2f}%, 胜率 {win_rate:.1f}%")
        
        # 详细分析高分股票
        high_score = [r for r in results if r['score'] >= 8.0]
        if high_score:
            logger.info(f"\n📈 高分股票详情 (>=8.0分):")
            sorted_results = sorted(high_score, key=lambda x: x['score'], reverse=True)
            for i, r in enumerate(sorted_results[:10], 1):
                ret_str = f"{r['future_return']:+.2f}%" if r['future_return'] is not None else "N/A"
                logger.info(f"  {i}. {r['code']}: {r['score']:.1f}分 | ADX={r['adx']:.1f} | RS={r['relative_strength']:.0%} | 收益: {ret_str}")
        
        # 保存结果
        self._save_results(results)
    
    def _save_results(self, results: List[Dict]):
        """保存回测结果"""
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/backtest_v5_results.json"
        output_file.parent.mkdir(exist_ok=True)
        
        output = {
            'backtest_date': datetime.now().isoformat(),
            'version': 'V5',
            'config': {
                'min_adx': self.v5.min_adx,
                'min_ma20_slope': self.v5.min_ma20_slope,
                'weights': self.v5.weights
            },
            'total_stocks': len(results),
            'results': sorted(results, key=lambda x: x['score'], reverse=True)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 结果已保存: {output_file}")


def main():
    """主函数"""
    backtest = NanFengV5Backtest()
    
    # 使用历史日期进行回测（确保有未来数据）
    # 数据库最新是2026-03-10，我们用2026-03-03测试，持有5天到2026-03-10
    test_date = "2026-03-03T00:00:00"
    
    # 运行回测
    results = backtest.run_backtest(test_date=test_date, hold_days=5, max_stocks=200)
    
    print("\n" + "=" * 80)
    print("🌬️ 南风V5回测完成")
    print("=" * 80)


if __name__ == "__main__":
    main()
