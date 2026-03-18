#!/usr/bin/env python3
"""
判官 - 数据校验与实时日线聚合
职责:
1. 校验实时数据新鲜度
2. 聚合minute数据为daily数据
3. 数据质量验证
4. 确保全量覆盖
"""

import sqlite3
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("判官")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class DataJudge:
    """判官 - 数据校验与聚合"""
    
    def __init__(self):
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.conn = sqlite3.connect(BEIFENG_DB)
        self.cursor = self.conn.cursor()
        self.issues = []
    
    def close(self):
        self.conn.close()
    
    def check_data_freshness(self) -> Dict:
        """检查数据新鲜度"""
        # 检查最新minute时间
        self.cursor.execute('SELECT MAX(timestamp) FROM minute')
        max_minute = self.cursor.fetchone()[0]
        
        # 检查15分钟内的数据
        time_15m = datetime.now() - timedelta(minutes=15)
        self.cursor.execute('SELECT COUNT(*) FROM minute WHERE timestamp > ?', (time_15m,))
        fresh_count = self.cursor.fetchone()[0]
        
        return {
            'max_minute': max_minute,
            'fresh_15m': fresh_count,
            'is_fresh': fresh_count > 0
        }
    
    def aggregate_minute_to_daily(self) -> int:
        """
        将minute数据聚合为daily数据
        返回: 聚合的股票数量
        """
        # 获取当日有minute数据的股票
        self.cursor.execute('''
            SELECT DISTINCT stock_code 
            FROM minute 
            WHERE timestamp LIKE ?
        ''', (f"{self.today}%",))
        
        stocks = [row[0] for row in self.cursor.fetchall()]
        aggregated = 0
        
        for stock_code in stocks:
            # 聚合OHLCV
            self.cursor.execute('''
                SELECT 
                    MIN(timestamp) as open_time,
                    MAX(high) as high,
                    MIN(low) as low,
                    MAX(close) as close,
                    SUM(volume) as volume,
                    MAX(timestamp) as latest_time
                FROM minute
                WHERE stock_code = ? AND timestamp LIKE ?
            ''', (stock_code, f"{self.today}%"))
            
            result = self.cursor.fetchone()
            if not result or not result[3]:
                continue
            
            open_time, high, low, close, volume, latest_time = result
            
            # 获取开盘价（第一条minute数据）
            self.cursor.execute('''
                SELECT open FROM minute 
                WHERE stock_code = ? AND timestamp LIKE ?
                ORDER BY timestamp ASC LIMIT 1
            ''', (stock_code, f"{self.today}%"))
            
            open_row = self.cursor.fetchone()
            open_price = open_row[0] if open_row else close
            
            # 获取昨日收盘价计算涨跌幅
            self.cursor.execute('''
                SELECT close FROM daily
                WHERE stock_code = ?
                ORDER BY timestamp DESC LIMIT 1
            ''', (stock_code,))
            
            prev_close_row = self.cursor.fetchone()
            prev_close = prev_close_row[0] if prev_close_row else open_price
            
            change_pct = ((close - prev_close) / prev_close * 100) if prev_close else 0
            
            # 插入/更新daily表
            try:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO daily
                    (stock_code, timestamp, open, high, low, close, volume, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'minute_aggregated')
                ''', (
                    stock_code,
                    self.today,
                    open_price,
                    high,
                    low,
                    close,
                    volume
                ))
                aggregated += 1
            except Exception as e:
                self.issues.append(f"{stock_code}: {e}")
        
        self.conn.commit()
        return aggregated
    
    def validate_aggregated_data(self, stock_code: str) -> Dict:
        """校验聚合后的数据质量"""
        self.cursor.execute('''
            SELECT open, high, low, close, volume
            FROM daily
            WHERE stock_code = ? AND timestamp = ?
        ''', (stock_code, self.today))
        
        data = self.cursor.fetchone()
        if not data:
            return {'valid': False, 'reason': '无数据'}
        
        open_p, high, low, close, volume = data
        
        # 校验逻辑
        issues = []
        
        # 1. OHLC关系
        if high < max(open_p, close) or low > min(open_p, close):
            issues.append('OHLC关系错误')
        
        # 2. 价格合理性
        if high > 100000 or low <= 0:
            issues.append('价格不合理')
        
        # 3. 量能合理性
        if volume <= 0:
            issues.append('成交量为0')
        
        return {
            'valid': len(issues) == 0,
            'issues': issues,
            'data': {'open': open_p, 'high': high, 'low': low, 'close': close, 'volume': volume}
        }
    
    def check_full_coverage(self) -> Dict:
        """检查全量覆盖"""
        # 获取master_stocks数量
        self.cursor.execute('SELECT COUNT(*) FROM master_stocks')
        total = self.cursor.fetchone()[0]
        
        # 获取有daily数据的股票数
        self.cursor.execute('SELECT COUNT(DISTINCT stock_code) FROM daily WHERE timestamp = ?', (self.today,))
        daily_count = self.cursor.fetchone()[0]
        
        # 获取有minute数据的股票数
        self.cursor.execute('SELECT COUNT(DISTINCT stock_code) FROM minute WHERE timestamp LIKE ?', (f"{self.today}%",))
        minute_count = self.cursor.fetchone()[0]
        
        return {
            'total_stocks': total,
            'daily_count': daily_count,
            'minute_count': minute_count,
            'coverage': f"{daily_count}/{total} ({daily_count*100//total}%)"
        }
    
    def validate_price_against_api(self, stock_code: str) -> Dict:
        """对比API验证价格准确性"""
        # 获取北风数据
        self.cursor.execute('''
            SELECT close FROM daily
            WHERE stock_code = ?
            ORDER BY timestamp DESC LIMIT 1
        ''', (stock_code,))
        
        local_row = self.cursor.fetchone()
        if not local_row:
            return {'valid': False, 'reason': '无本地数据'}
        
        local_price = local_row[0]
        
        # 获取腾讯实时价格
        try:
            url = f"https://qt.gtimg.cn/q={stock_code}"
            resp = requests.get(url, timeout=5)
            if '~' in resp.text:
                parts = resp.text.split('~')
                remote_price = float(parts[3])  # 当前价
                
                diff_pct = abs(remote_price - local_price) / remote_price * 100
                
                return {
                    'valid': diff_pct < 1,  # 1%以内视为准确
                    'local': local_price,
                    'remote': remote_price,
                    'diff_pct': diff_pct
                }
        except Exception as e:
            return {'valid': None, 'error': str(e)}
        
        return {'valid': False, 'reason': '无法获取远程数据'}


def run_full_validation():
    """运行完整的数据校验流程"""
    judge = DataJudge()
    
    print("=" * 50)
    print("🎯 判官数据校验")
    print("=" * 50)
    
    # 1. 检查新鲜度
    print("\n1. 数据新鲜度检查")
    freshness = judge.check_data_freshness()
    print(f"   最新minute: {freshness['max_minute']}")
    print(f"   15分钟内: {freshness['fresh_15m']} 只")
    print(f"   状态: {'✅ 正常' if freshness['is_fresh'] else '❌ 数据旧'}")
    
    # 2. 聚合minute到daily
    print("\n2. 聚合minute→daily")
    aggregated = judge.aggregate_minute_to_daily()
    print(f"   聚合: {aggregated} 只股票")
    
    # 3. 检查全量覆盖
    print("\n3. 全量覆盖检查")
    coverage = judge.check_full_coverage()
    print(f"   daily: {coverage['daily_count']}/{coverage['total_stocks']}")
    print(f"   minute: {coverage['minute_count']}/{coverage['total_stocks']}")
    
    # 4. 校验示例数据
    print("\n4. 数据质量校验")
    test_stocks = ['sh000001', 'sh600519', 'sz399001']
    for stock in test_stocks:
        result = judge.validate_aggregated_data(stock)
        status = "✅" if result['valid'] else "❌"
        print(f"   {stock}: {status}")
    
    judge.close()
    print("\n" + "=" * 50)


if __name__ == '__main__':
    run_full_validation()
