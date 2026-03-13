#!/usr/bin/env python3
"""
判官 - 分钟数据深度检查
验证分钟数据连续性、拼接逻辑、数据结构完整性
"""

import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

class MinuteDataValidator:
    """分钟数据验证器"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.issues = []
    
    def check_minute_continuity(self, stock_code: str = 'sh600348', date: str = None) -> dict:
        """检查分钟数据连续性"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        
        # 获取分钟数据
        minute_data = pd.read_sql_query(f"""
            SELECT timestamp, open, high, low, close, volume
            FROM kline_data
            WHERE stock_code = '{stock_code}'
            AND data_type = '1min'
            AND date(timestamp) = '{date}'
            ORDER BY timestamp
        """, conn)
        
        conn.close()
        
        if len(minute_data) == 0:
            return {
                'status': 'MISSING',
                'count': 0,
                'message': f'{date} 无分钟数据',
                'gaps': []
            }
        
        # 检查时间连续性（每分钟应该有数据）
        timestamps = pd.to_datetime(minute_data['timestamp'])
        expected_minutes = set()
        
        # 生成交易时段所有分钟（9:30-11:30, 13:00-15:00）
        start_time = datetime.strptime(f"{date} 09:30:00", "%Y-%m-%d %H:%M:%S")
        for i in range(120):  # 上午2小时 = 120分钟
            expected_minutes.add(start_time + timedelta(minutes=i))
        
        start_time = datetime.strptime(f"{date} 13:00:00", "%Y-%m-%d %H:%M:%S")
        for i in range(120):  # 下午2小时 = 120分钟
            expected_minutes.add(start_time + timedelta(minutes=i))
        
        actual_minutes = set(timestamps.tolist())
        missing_minutes = expected_minutes - actual_minutes
        
        # 检查数据合理性
        issues = []
        
        # 1. 检查价格连续性
        for i in range(1, len(minute_data)):
            prev_close = minute_data.iloc[i-1]['close']
            curr_open = minute_data.iloc[i]['open']
            
            # 开盘价应该接近上一分钟收盘价
            if abs(curr_open - prev_close) / prev_close > 0.05:  # 5%差距
                issues.append(f"{minute_data.iloc[i]['timestamp']}: 价格跳空 {curr_open:.2f} vs {prev_close:.2f}")
        
        # 2. 检查成交量
        zero_volume = minute_data[minute_data['volume'] == 0]
        if len(zero_volume) > 10:
            issues.append(f"{len(zero_volume)} 分钟成交量为0")
        
        # 3. 检查OHLC合理性
        for i, row in minute_data.iterrows():
            if row['low'] > row['high']:
                issues.append(f"{row['timestamp']}: 最低价{row['low']} > 最高价{row['high']}")
            if row['close'] > row['high'] or row['close'] < row['low']:
                issues.append(f"{row['timestamp']}: 收盘价{row['close']} 超出高低价范围")
        
        status = 'OK' if len(missing_minutes) == 0 and len(issues) == 0 else 'WARNING'
        
        return {
            'status': status,
            'count': len(minute_data),
            'expected': len(expected_minutes),
            'missing': len(missing_minutes),
            'missing_samples': list(missing_minutes)[:5],
            'issues': issues[:5],
            'message': f'{len(minute_data)}条分钟数据，缺失{len(missing_minutes)}分钟，{len(issues)}个问题'
        }
    
    def check_daily_aggregation(self, stock_code: str = 'sh600348', date: str = None) -> dict:
        """检查分钟数据拼接成日线的逻辑"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        
        # 获取分钟数据
        minute_data = pd.read_sql_query(f"""
            SELECT open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = '{stock_code}'
            AND data_type = '1min'
            AND date(timestamp) = '{date}'
        """, conn)
        
        # 获取日线数据
        daily_data = pd.read_sql_query(f"""
            SELECT open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = '{stock_code}'
            AND data_type = 'daily'
            AND date(timestamp) = '{date}'
        """, conn)
        
        conn.close()
        
        if len(minute_data) == 0 or len(daily_data) == 0:
            return {
                'status': 'MISSING',
                'message': '分钟数据或日线数据缺失'
            }
        
        # 计算分钟数据聚合值
        calc_open = minute_data.iloc[0]['open']
        calc_high = minute_data['high'].max()
        calc_low = minute_data['low'].min()
        calc_close = minute_data.iloc[-1]['close']
        calc_volume = minute_data['volume'].sum()
        calc_amount = minute_data['amount'].sum()
        
        # 对比日线数据
        daily = daily_data.iloc[0]
        
        discrepancies = []
        
        if abs(calc_open - daily['open']) > 0.01:
            discrepancies.append(f"开盘价: 分钟{calc_open:.2f} vs 日线{daily['open']:.2f}")
        
        if abs(calc_high - daily['high']) > 0.01:
            discrepancies.append(f"最高价: 分钟{calc_high:.2f} vs 日线{daily['high']:.2f}")
        
        if abs(calc_low - daily['low']) > 0.01:
            discrepancies.append(f"最低价: 分钟{calc_low:.2f} vs 日线{daily['low']:.2f}")
        
        if abs(calc_close - daily['close']) > 0.01:
            discrepancies.append(f"收盘价: 分钟{calc_close:.2f} vs 日线{daily['close']:.2f}")
        
        volume_diff_pct = abs(calc_volume - daily['volume']) / daily['volume'] * 100 if daily['volume'] > 0 else 0
        if volume_diff_pct > 5:
            discrepancies.append(f"成交量: 分钟{calc_volume} vs 日线{daily['volume']} (差异{volume_diff_pct:.1f}%)")
        
        status = 'OK' if len(discrepancies) == 0 else 'WARNING'
        
        return {
            'status': status,
            'minute_count': len(minute_data),
            'discrepancies': discrepancies,
            'message': f'{len(minute_data)}条分钟数据，{len(discrepancies)}处差异' if discrepancies else '分钟数据聚合与日线一致'
        }
    
    def check_data_structure(self) -> dict:
        """检查数据结构完整性"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查表结构
        cursor.execute("PRAGMA table_info(kline_data)")
        columns = cursor.fetchall()
        
        required_columns = ['stock_code', 'data_type', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'amount']
        existing_columns = [col[1] for col in columns]
        
        missing_columns = [c for c in required_columns if c not in existing_columns]
        
        # 检查索引
        cursor.execute("PRAGMA index_list(kline_data)")
        indexes = cursor.fetchall()
        
        conn.close()
        
        status = 'OK' if len(missing_columns) == 0 else 'ERROR'
        
        return {
            'status': status,
            'columns': existing_columns,
            'missing_columns': missing_columns,
            'indexes': [idx[1] for idx in indexes],
            'message': f'{len(existing_columns)}个字段，缺失{len(missing_columns)}个' if missing_columns else '数据结构完整'
        }
    
    def run_full_validation(self, stock_code: str = 'sh600348') -> dict:
        """运行完整验证"""
        print("="*70)
        print(f"🔍 判官 - 分钟数据深度检查 ({stock_code})")
        print("="*70)
        
        # 1. 数据结构检查
        print("\n1️⃣ 数据结构完整性")
        structure = self.check_data_structure()
        print(f"   状态: {structure['status']}")
        print(f"   字段: {', '.join(structure['columns'])}")
        if structure['missing_columns']:
            print(f"   ❌ 缺失字段: {', '.join(structure['missing_columns'])}")
        
        # 2. 分钟数据连续性（最近有数据的一天）
        print("\n2️⃣ 分钟数据连续性")
        conn = sqlite3.connect(self.db_path)
        latest_date = pd.read_sql_query(f"""
            SELECT MAX(date(timestamp)) as latest
            FROM kline_data
            WHERE stock_code = '{stock_code}' AND data_type = '1min'
        """, conn).iloc[0]['latest']
        conn.close()
        
        if latest_date:
            continuity = self.check_minute_continuity(stock_code, latest_date)
            print(f"   检查日期: {latest_date}")
            print(f"   状态: {continuity['status']}")
            print(f"   数据条数: {continuity['count']}/{continuity['expected']}")
            print(f"   缺失: {continuity['missing']}分钟")
            if continuity['issues']:
                print(f"   ⚠️ 问题:")
                for issue in continuity['issues']:
                    print(f"      - {issue}")
        else:
            print(f"   ❌ 无分钟数据")
        
        # 3. 日线聚合检查
        print("\n3️⃣ 分钟数据拼接日线逻辑")
        if latest_date:
            aggregation = self.check_daily_aggregation(stock_code, latest_date)
            print(f"   状态: {aggregation['status']}")
            print(f"   {aggregation['message']}")
            if aggregation['discrepancies']:
                print(f"   ⚠️ 差异:")
                for disc in aggregation['discrepancies']:
                    print(f"      - {disc}")
        
        print("\n" + "="*70)
        
        return {
            'structure': structure,
            'continuity': continuity if latest_date else None,
            'aggregation': aggregation if latest_date else None
        }

if __name__ == '__main__':
    validator = MinuteDataValidator()
    validator.run_full_validation('sh600348')
    
    print("\n" + "="*70)
    print("🔍 检查其他样本股票...")
    print("="*70)
    
    for stock in ['sh600188', 'sh600127', 'sh600011']:
        print(f"\n{stock}:")
        result = validator.check_minute_continuity(stock)
        print(f"   状态: {result['status']}, {result['message']}")
    
    print("\n" + "="*70)
    print("✅ 分钟数据验证完成")
    print("="*70)
