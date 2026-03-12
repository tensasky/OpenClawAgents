#!/usr/bin/env python3
"""
判官 (Judge) - 数据有效性验证Agent
专门验证北风数据质量，确保分析基础可靠
"""

import sqlite3
import pandas as pd
import requests
from pathlib import Path
from datetime import datetime, timedelta
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("判官")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

class DataJudge:
    """数据判官 - 验证北风数据有效性"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.validation_results = []
        
    def validate_all(self, date: str = None) -> dict:
        """全盘验证"""
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        logger.info(f"🔍 判官开始验证 {date} 数据...")
        
        results = {
            'date': date,
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'passed': True,
            'warnings': [],
            'errors': []
        }
        
        # 1. 日线数据覆盖度
        results['checks']['daily_coverage'] = self.check_daily_coverage(date)
        
        # 2. 分钟数据覆盖度
        results['checks']['minute_coverage'] = self.check_minute_coverage(date)
        
        # 3. 数据连续性
        results['checks']['continuity'] = self.check_continuity(date)
        
        # 4. 异常成交量检测
        results['checks']['volume_anomaly'] = self.check_volume_anomaly(date)
        
        # 5. 价格合理性
        results['checks']['price_sanity'] = self.check_price_sanity(date)
        
        # 汇总
        for check_name, check_result in results['checks'].items():
            if check_result['status'] == 'ERROR':
                results['passed'] = False
                results['errors'].append(f"{check_name}: {check_result['message']}")
            elif check_result['status'] == 'WARNING':
                results['warnings'].append(f"{check_name}: {check_result['message']}")
        
        return results
    
    def check_daily_coverage(self, date: str) -> dict:
        """检查日线数据覆盖度"""
        conn = sqlite3.connect(self.db_path)
        
        today_count = pd.read_sql_query(f"""
            SELECT COUNT(DISTINCT stock_code) as count
            FROM kline_data
            WHERE data_type = 'daily' AND date(timestamp) = '{date}'
        """, conn).iloc[0]['count']
        
        total_count = pd.read_sql_query("""
            SELECT COUNT(DISTINCT stock_code) as count
            FROM kline_data
            WHERE data_type = 'daily'
        """, conn).iloc[0]['count']
        
        conn.close()
        
        coverage = today_count / total_count * 100
        
        if coverage >= 95:
            return {'status': 'OK', 'coverage': coverage, 'message': f'覆盖率{coverage:.1f}%'}
        elif coverage >= 80:
            return {'status': 'WARNING', 'coverage': coverage, 'message': f'覆盖率{coverage:.1f}%，偏低'}
        else:
            return {'status': 'ERROR', 'coverage': coverage, 'message': f'覆盖率{coverage:.1f}%，严重不足'}
    
    def check_minute_coverage(self, date: str) -> dict:
        """检查分钟数据覆盖度"""
        conn = sqlite3.connect(self.db_path)
        
        minute_data = pd.read_sql_query(f"""
            SELECT COUNT(DISTINCT stock_code) as stock_count,
                   COUNT(*) as record_count,
                   MIN(timestamp) as first_time,
                   MAX(timestamp) as last_time
            FROM kline_data
            WHERE data_type = '1min' AND date(timestamp) = '{date}'
        """, conn)
        
        conn.close()
        
        stock_count = minute_data.iloc[0]['stock_count']
        
        if stock_count == 0 or pd.isna(stock_count):
            return {'status': 'ERROR', 'stock_count': 0, 'message': '今日分钟数据完全缺失！'}
        elif stock_count < 100:
            return {'status': 'WARNING', 'stock_count': stock_count, 'message': f'仅{stock_count}只股票有分钟数据'}
        else:
            return {'status': 'OK', 'stock_count': stock_count, 'message': f'{stock_count}只股票有分钟数据'}
    
    def check_continuity(self, date: str) -> dict:
        """检查数据连续性"""
        conn = sqlite3.connect(self.db_path)
        
        recent_dates = pd.read_sql_query("""
            SELECT DISTINCT date(timestamp) as dt
            FROM kline_data
            WHERE data_type = 'daily'
            ORDER BY dt DESC
            LIMIT 5
        """, conn)
        
        conn.close()
        
        dates = [d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10] 
                 for d in recent_dates['dt'].tolist()]
        
        # 检查是否有缺失
        expected = pd.date_range(end=date, periods=5, freq='B')
        expected_str = [d.strftime('%Y-%m-%d') for d in expected]
        
        missing = [d for d in expected_str if d not in dates]
        
        if missing:
            return {'status': 'WARNING', 'missing': missing, 'message': f'缺失{len(missing)}天: {", ".join(missing)}'}
        else:
            return {'status': 'OK', 'message': '最近5个交易日数据完整'}
    
    def check_volume_anomaly(self, date: str) -> dict:
        """检查异常成交量"""
        conn = sqlite3.connect(self.db_path)
        
        # 找出今日量比>50的股票
        anomaly_stocks = pd.read_sql_query(f"""
            SELECT stock_code, volume,
                   (SELECT AVG(volume) FROM kline_data t2 
                    WHERE t2.stock_code = t1.stock_code 
                    AND t2.data_type = 'daily'
                    AND date(t2.timestamp) < '{date}'
                    ORDER BY t2.timestamp DESC LIMIT 5) as avg_volume
            FROM kline_data t1
            WHERE data_type = 'daily' AND date(timestamp) = '{date}'
            AND volume > 100000000  -- >1亿股
        """, conn)
        
        conn.close()
        
        if len(anomaly_stocks) > 0:
            anomaly_stocks['vol_ratio'] = anomaly_stocks['volume'] / anomaly_stocks['avg_volume']
            top_anomaly = anomaly_stocks.nlargest(3, 'vol_ratio')
            
            stocks = []
            for _, row in top_anomaly.iterrows():
                if row['avg_volume'] > 0:
                    ratio = row['volume'] / row['avg_volume']
                    stocks.append(f"{row['stock_code']}({ratio:.1f}倍)")
            
            return {'status': 'WARNING', 'count': len(stocks), 'stocks': stocks, 
                    'message': f'发现{len(stocks)}只异常放量股: {", ".join(stocks[:3])}'}
        else:
            return {'status': 'OK', 'message': '无异常放量'}
    
    def check_price_sanity(self, date: str) -> dict:
        """检查价格合理性"""
        conn = sqlite3.connect(self.db_path)
        
        # 检查涨跌幅超过15%的股票
        extreme = pd.read_sql_query(f"""
            SELECT stock_code, 
                   (close - (SELECT close FROM kline_data t2 
                             WHERE t2.stock_code = t1.stock_code 
                             AND t2.data_type = 'daily'
                             AND date(t2.timestamp) < '{date}'
                             ORDER BY t2.timestamp DESC LIMIT 1)) / 
                   (SELECT close FROM kline_data t2 
                    WHERE t2.stock_code = t1.stock_code 
                    AND t2.data_type = 'daily'
                    AND date(t2.timestamp) < '{date}'
                    ORDER BY t2.timestamp DESC LIMIT 1) * 100 as change_pct
            FROM kline_data t1
            WHERE data_type = 'daily' AND date(timestamp) = '{date}'
            AND (close > 1.15 * (SELECT close FROM kline_data t2 
                                 WHERE t2.stock_code = t1.stock_code 
                                 AND t2.data_type = 'daily'
                                 AND date(t2.timestamp) < '{date}'
                                 ORDER BY t2.timestamp DESC LIMIT 1)
                 OR close < 0.85 * (SELECT close FROM kline_data t2 
                                    WHERE t2.stock_code = t1.stock_code 
                                    AND t2.data_type = 'daily'
                                    AND date(t2.timestamp) < '{date}'
                                    ORDER BY t2.timestamp DESC LIMIT 1))
        """, conn)
        
        conn.close()
        
        if len(extreme) > 0:
            stocks = [f"{row['stock_code']}({row['change_pct']:+.1f}%)" for _, row in extreme.head(5).iterrows()]
            return {'status': 'WARNING', 'count': len(extreme), 
                    'message': f'发现{len(extreme)}只极端涨跌: {", ".join(stocks)}'}
        else:
            return {'status': 'OK', 'message': '价格波动正常'}
    
    def verify_with_sina(self, stock_code: str) -> dict:
        """用新浪财经验证数据"""
        try:
            # 新浪实时接口
            url = f"https://hq.sinajs.cn/list={stock_code}"
            response = requests.get(url, headers={'Referer': 'https://finance.sina.com.cn'}, timeout=10)
            response.encoding = 'gb2312'
            
            data = response.text.split('"')[1].split(',')
            if len(data) >= 33:
                sina_volume = int(data[8])  # 成交量
                sina_close = float(data[3])  # 当前价
                
                # 对比数据库
                conn = sqlite3.connect(self.db_path)
                db_data = pd.read_sql_query(f"""
                    SELECT volume, close
                    FROM kline_data
                    WHERE stock_code = '{stock_code}'
                    AND data_type = 'daily'
                    AND date(timestamp) = date('now')
                """, conn)
                conn.close()
                
                if len(db_data) > 0:
                    db_volume = db_data.iloc[0]['volume']
                    db_close = db_data.iloc[0]['close']
                    
                    volume_diff = abs(sina_volume - db_volume) / db_volume * 100
                    price_diff = abs(sina_close - db_close) / db_close * 100
                    
                    return {
                        'sina_volume': sina_volume,
                        'db_volume': db_volume,
                        'volume_diff': volume_diff,
                        'sina_close': sina_close,
                        'db_close': db_close,
                        'price_diff': price_diff,
                        'match': volume_diff < 5 and price_diff < 1
                    }
            
            return {'error': '无法获取新浪数据'}
        except Exception as e:
            return {'error': str(e)}


def main():
    """判官主程序"""
    judge = DataJudge()
    
    print("="*70)
    print("🔍 判官数据验证报告")
    print("="*70)
    
    results = judge.validate_all()
    
    print(f"\n📅 验证日期: {results['date']}")
    print(f"⏰ 验证时间: {results['timestamp']}")
    print(f"✅ 整体状态: {'通过' if results['passed'] else '未通过'}")
    
    print("\n📋 详细检查结果:")
    for check_name, check_result in results['checks'].items():
        status_emoji = {'OK': '✅', 'WARNING': '⚠️', 'ERROR': '❌'}.get(check_result['status'], '❓')
        print(f"  {status_emoji} {check_name}: {check_result['message']}")
    
    if results['errors']:
        print("\n❌ 严重错误:")
        for error in results['errors']:
            print(f"  • {error}")
    
    if results['warnings']:
        print("\n⚠️ 警告:")
        for warning in results['warnings']:
            print(f"  • {warning}")
    
    # 验证华阳股份
    print("\n" + "="*70)
    print("🔍 华阳股份(sh600348) 新浪验证")
    print("="*70)
    
    verify = judge.verify_with_sina('sh600348')
    if 'error' not in verify:
        print(f"新浪数据: 成交量{verify['sina_volume']/10000:.0f}万股, 收盘价¥{verify['sina_close']:.2f}")
        print(f"本地数据: 成交量{verify['db_volume']/10000:.0f}万股, 收盘价¥{verify['db_close']:.2f}")
        print(f"成交量差异: {verify['volume_diff']:.1f}%")
        print(f"价格差异: {verify['price_diff']:.2f}%")
        print(f"数据一致性: {'✅ 一致' if verify['match'] else '❌ 不一致'}")
    else:
        print(f"验证失败: {verify['error']}")
    
    print("="*70)
    
    # 保存报告
    report_file = Path.home() / f".openclaw/workspace/memory/judge_report_{results['date']}.json"
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n📄 报告已保存: {report_file}")


if __name__ == '__main__':
    main()
