#!/usr/bin/env python3
"""
实时数据聚合器 - 将分钟数据汇总为当日实时日线
解决交易时段使用T-1数据的问题
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("南风")


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("实时数据聚合")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class RealtimeAggregator:
    """实时数据聚合器"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
    
    def get_today_minute_data(self, stock_code: str) -> Optional[pd.DataFrame]:
        """获取今日分钟数据 - 优先minute表，备选kline_data"""
        try:
            conn = sqlite3.connect(self.db_path)
            # 优先查minute表
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM minute
                WHERE stock_code = ?
                AND timestamp LIKE ?
                ORDER BY timestamp
            """
            today = datetime.now().strftime('%Y-%m-%d')
            df = pd.read_sql_query(query, conn, params=(stock_code, today + '%'))
            conn.close()
            
            if df is None or len(df) == 0:
                return None
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception as e:
            logger.debug(f"获取 {stock_code} 分钟数据失败: {e}")
            return None
    
    def aggregate_to_daily(self, stock_code: str) -> Optional[Dict]:
        """
        将今日分钟数据聚合为日线
        返回: {'open', 'high', 'low', 'close', 'volume', 'amount', 'timestamp'}
        """
        df = self.get_today_minute_data(stock_code)
        if df is None or len(df) == 0:
            return None
        
        # 聚合为日线
        daily = {
            'open': df['open'].iloc[0],
            'high': df['high'].max(),
            'low': df['low'].min(),
            'close': df['close'].iloc[-1],
            'volume': df['volume'].sum(),
            'amount': df['amount'].sum() if 'amount' in df.columns else 0,
            'timestamp': df['timestamp'].iloc[-1].strftime('%Y-%m-%dT00:00:00'),
            'minute_count': len(df),
            'last_update': df['timestamp'].iloc[-1].strftime('%H:%M:%S')
        }
        
        return daily
    
    def get_stock_data_with_realtime(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """
        获取股票数据，优先使用今日实时聚合数据
        返回包含历史日线 + 今日实时数据的DataFrame
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            # 1. 获取历史日线数据（不含今天）
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM daily WHERE stock_code = ?
                AND timestamp < DATE('now')
                ORDER BY timestamp DESC
                LIMIT ?
            """
            hist_df = pd.read_sql_query(query, conn, params=(stock_code, days))
            
            # 2. 获取今日实时聚合数据
            today_data = self.aggregate_to_daily(stock_code)
            
            conn.close()
            
            if hist_df.empty and today_data is None:
                return None
            
            # 合并数据
            if today_data:
                today_row = pd.DataFrame([{
                    'timestamp': today_data['timestamp'],
                    'open': today_data['open'],
                    'high': today_data['high'],
                    'low': today_data['low'],
                    'close': today_data['close'],
                    'volume': today_data['volume'],
                    'amount': today_data['amount']
                }])
                
                if not hist_df.empty:
                    df = pd.concat([hist_df, today_row], ignore_index=True)
                else:
                    df = today_row
            else:
                df = hist_df
            
            # 排序并返回
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # 标记是否有实时数据
            df['is_realtime'] = False
            if today_data:
                df.loc[df.index[-1], 'is_realtime'] = True
            
            return df
            
        except Exception as e:
            logger.error(f"获取 {stock_code} 数据失败: {e}")
            return None
    
    def check_data_freshness(self, stock_code: str) -> Dict:
        """检查数据新鲜度"""
        result = {
            'code': stock_code,
            'has_minute_today': False,
            'minute_count': 0,
            'last_minute_time': None,
            'aggregated_daily': None,
            'data_age_minutes': None
        }
        
        df = self.get_today_minute_data(stock_code)
        if df is not None and len(df) > 0:
            result['has_minute_today'] = True
            result['minute_count'] = len(df)
            result['last_minute_time'] = df['timestamp'].iloc[-1].strftime('%H:%M:%S')
            
            # 计算数据年龄（分钟）
            last_time = df['timestamp'].iloc[-1]
            now = datetime.now()
            result['data_age_minutes'] = (now - last_time).total_seconds() / 60
            
            # 聚合日线
            daily = self.aggregate_to_daily(stock_code)
            result['aggregated_daily'] = daily
        
        return result


def main():
    """测试"""
    aggregator = RealtimeAggregator()
    
    # 测试几只股票
    test_codes = ['sh600068', 'sh600310', 'sh000001']
    
    log.info("=" * 60)
    log.info("实时数据聚合测试")
    log.info("=" * 60)
    
    for code in test_codes:
        log.info(f"\n📊 {code}:")
        
        # 检查数据新鲜度
        freshness = aggregator.check_data_freshness(code)
        
        if freshness['has_minute_today']:
            log.info(f"  ✅ 有今日分钟数据")
            log.info(f"  📈 分钟条数: {freshness['minute_count']}")
            log.info(f"  ⏰ 最后更新: {freshness['last_minute_time']}")
            
            daily = freshness['aggregated_daily']
            if daily:
                log.info(f"  💰 实时价格: ¥{daily['close']:.2f}")
                log.info(f"  📊 今日涨跌: {(daily['close']/daily['open']-1)*100:+.2f}%")
                log.info(f"  💎 最高: ¥{daily['high']:.2f} / 最低: ¥{daily['low']:.2f}")
        else:
            log.info(f"  ❌ 无今日分钟数据，使用昨日收盘价")
    
    log.info("\n" + "=" * 60)


if __name__ == '__main__':
    main()
