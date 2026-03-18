#!/usr/bin/env python3
"""
判官 (Judge) - 数据验证Agent V1.0
职责: 验证北风数据准确性，确保数据质量
"""

import sqlite3
import requests
import json
import sys
from datetime import datetime
from pathlib import Path

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("判官")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
REPORT_DIR = Path(__file__).parent / "reports"
REPORT_DIR.mkdir(exist_ok=True)

class JudgeAgent:
    """判官Agent - 数据验证"""
    
    def __init__(self):
        self.issues = []
        self.validations = []
    
    def validate_daily_coverage(self) -> dict:
        """验证日线数据覆盖率"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(f"""
            SELECT COUNT(DISTINCT stock_code) 
            FROM daily 
            WHERE date(timestamp) = '{today}'
        """)
        
        count = cursor.fetchone()[0]
        conn.close()
        
        status = "✅" if count >= 5000 else "❌"
        return {
            'check': '日线覆盖率',
            'count': count,
            'status': status,
            'threshold': 5000
        }
    
    def validate_minute_coverage(self) -> dict:
        """验证分钟数据覆盖率"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute(f"""
            SELECT COUNT(DISTINCT stock_code) 
            FROM minute 
            WHERE date(timestamp) = '{today}'
        """)
        
        count = cursor.fetchone()[0]
        conn.close()
        
        status = "✅" if count >= 5000 else "⚠️"
        return {
            'check': '分钟覆盖率',
            'count': count,
            'status': status,
            'threshold': 5000
        }
    
    def validate_price_accuracy(self, stock_code: str = 'sh600348') -> dict:
        """验证价格准确性（对比新浪）"""
        try:
            # 获取北风数据
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute(f"""
                SELECT close FROM daily 
                WHERE stock_code = '{stock_code}' 
                AND date(timestamp) = '{today}'
            """)
            
            local_price = cursor.fetchone()
            conn.close()
            
            if not local_price:
                return {'check': f'{stock_code}价格', 'status': '❌', 'error': '无本地数据'}
            
            local_price = local_price[0]
            
            # 获取新浪数据
            url = f"https://hq.sinajs.cn/list={stock_code}"
            response = requests.get(url, headers={
                'User-Agent': 'Mozilla/5.0',
                'Referer': 'https://finance.sina.com.cn'
            }, timeout=10)
            response.encoding = 'gb2312'
            
            data = response.text.split('"')[1].split(',')
            sina_price = float(data[3])
            
            diff = abs(local_price - sina_price) / sina_price * 100
            status = "✅" if diff < 1 else "❌"
            
            return {
                'check': f'{stock_code}价格准确性',
                'local': local_price,
                'sina': sina_price,
                'diff': f"{diff:.2f}%",
                'status': status
            }
            
        except Exception as e:
            return {'check': f'{stock_code}价格', 'status': '❌', 'error': str(e)}
    
    def validate_data_consistency(self) -> dict:
        """验证日线和分钟数据一致性"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 随机抽查5只股票
        cursor.execute(f"""
            SELECT d.stock_code, d.close as daily_close,
                   (SELECT close FROM minute m 
                    WHERE m.stock_code = d.stock_code 
                    AND date(m.timestamp) = '{today}'
                    ORDER BY m.timestamp DESC LIMIT 1) as minute_close
            FROM daily d
            WHERE date(d.timestamp) = '{today}'
            ORDER BY RANDOM()
            LIMIT 5
        """)
        
        mismatches = []
        for row in cursor.fetchall():
            code, d_close, m_close = row
            if m_close and abs(d_close - m_close) / d_close > 0.02:
                mismatches.append(f"{code}: {d_close:.2f} vs {m_close:.2f}")
        
        conn.close()
        
        status = "✅" if len(mismatches) == 0 else "⚠️"
        return {
            'check': '数据一致性',
            'mismatches': mismatches,
            'status': status
        }
    
    def validate_data_freshness(self, max_delay_minutes: int = 30) -> dict:
        """验证数据时效性 - 确保数据延迟不超过30分钟"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        now = datetime.now()
        today = now.strftime('%Y-%m-%d')
        
        # 获取daily表最新数据时间
        cursor.execute("""
            SELECT MAX(timestamp) as latest_ts, COUNT(*) as count
            FROM daily
            WHERE date(timestamp) = ?
        """, (today,))
        
        daily_result = cursor.fetchone()
        daily_latest = daily_result[0] if daily_result else None
        daily_count = daily_result[1] if daily_result else 0
        
        # 获取minute表最新数据时间
        cursor.execute("""
            SELECT MAX(timestamp) as latest_ts, COUNT(*) as count
            FROM minute
            WHERE date(timestamp) = ?
        """, (today,))
        
        minute_result = cursor.fetchone()
        minute_latest = minute_result[0] if minute_result else None
        minute_count = minute_result[1] if minute_result else 0
        
        conn.close()
        
        # 计算延迟
        daily_delay_minutes = None
        minute_delay_minutes = None
        
        if daily_latest:
            try:
                # 处理带T的ISO格式
                latest_ts = daily_latest.replace('T', ' ').replace('Z', '')
                latest_dt = datetime.strptime(latest_ts[:19], '%Y-%m-%d %H:%M:%S')
                daily_delay_minutes = (now - latest_dt).total_seconds() / 60
            except Exception as e:
                log.warning(f"解析daily时间戳失败: {daily_latest}, 错误: {e}")
                daily_delay_minutes = None
        
        if minute_latest:
            try:
                latest_ts = minute_latest.replace('T', ' ').replace('Z', '')
                latest_dt = datetime.strptime(latest_ts[:19], '%Y-%m-%d %H:%M:%S')
                minute_delay_minutes = (now - latest_dt).total_seconds() / 60
            except Exception as e:
                log.warning(f"解析minute时间戳失败: {minute_latest}, 错误: {e}")
                minute_delay_minutes = None
        
        # 判断状态
        daily_status = "❌"
        minute_status = "❌"
        
        if daily_delay_minutes is not None:
            if daily_delay_minutes <= 5:
                daily_status = "✅"
            elif daily_delay_minutes <= max_delay_minutes:
                daily_status = "⚠️"
        
        if minute_delay_minutes is not None:
            if minute_delay_minutes <= 5:
                minute_status = "✅"
            elif minute_delay_minutes <= max_delay_minutes:
                minute_status = "⚠️"
        
        # 整体状态: 任一超过30分钟则为❌
        overall_status = "✅"
        if (daily_delay_minutes is not None and daily_delay_minutes > max_delay_minutes) or \
           (minute_delay_minutes is not None and minute_delay_minutes > max_delay_minutes):
            overall_status = "❌"
        elif daily_status == "⚠️" or minute_status == "⚠️":
            overall_status = "⚠️"
        
        return {
            'check': '数据时效性',
            'status': overall_status,
            'daily': {
                'latest_ts': daily_latest,
                'delay_minutes': round(daily_delay_minutes, 1) if daily_delay_minutes else None,
                'count': daily_count,
                'status': daily_status
            },
            'minute': {
                'latest_ts': minute_latest,
                'delay_minutes': round(minute_delay_minutes, 1) if minute_delay_minutes else None,
                'count': minute_count,
                'status': minute_status
            },
            'threshold_minutes': max_delay_minutes,
            'is_valid': overall_status != "❌"
        }
    
    def run_full_validation(self) -> dict:
        """运行完整验证"""
        print("="*70)
        print("⚖️ 判官 - 数据验证报告")
        print("="*70)
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        results = []
        
        # 1. 日线覆盖率
        r1 = self.validate_daily_coverage()
        results.append(r1)
        print(f"{r1['status']} {r1['check']}: {r1['count']}/{r1['threshold']}")
        
        # 2. 分钟覆盖率
        r2 = self.validate_minute_coverage()
        results.append(r2)
        print(f"{r2['status']} {r2['check']}: {r2['count']}/{r2['threshold']}")
        
        # 3. 价格准确性
        r3 = self.validate_price_accuracy('sh600348')
        results.append(r3)
        if 'diff' in r3:
            print(f"{r3['status']} {r3['check']}: 差异{r3['diff']}")
        else:
            print(f"{r3['status']} {r3['check']}: {r3.get('error', '')}")
        
        # 4. 数据一致性
        r4 = self.validate_data_consistency()
        results.append(r4)
        print(f"{r4['status']} {r4['check']}: {len(r4['mismatches'])}处不一致")
        
        # 5. 数据时效性 (新增)
        r5 = self.validate_data_freshness(max_delay_minutes=30)
        results.append(r5)
        daily_delay = r5['daily']['delay_minutes']
        minute_delay = r5['minute']['delay_minutes']
        daily_status_str = f"{daily_delay}分钟" if daily_delay else "无数据"
        minute_status_str = f"{minute_delay}分钟" if minute_delay else "无数据"
        print(f"{r5['status']} {r5['check']}: 日线延迟{daily_status_str}, 分钟延迟{minute_status_str}")
        
        # 如果数据时效性不通过, 发出警告
        if not r5['is_valid']:
            print(f"\n🚨 警告: 数据时效性检查未通过! 延迟超过{r5['threshold_minutes']}分钟")
            print("   请检查北风数据采集器是否正常运行。")
        
        # 保存报告
        report_file = REPORT_DIR / f"judge_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存: {report_file}")
        print("="*70)
        
        return results
    
    def validate_before_send(self, data_timestamp: str = None, max_delay_minutes: int = 30) -> dict:
        """
        发送前数据验证 - 确保数据时效性
        
        返回:
            {
                'can_send': bool,      # 是否可以发送
                'status': str,         # '✅'/'⚠️'/'❌'
                'message': str,        # 状态说明
                'delay_minutes': float # 延迟分钟数
            }
        """
        now = datetime.now()
        
        # 如果没有提供时间戳, 使用daily表最新时间
        if data_timestamp is None:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            today = now.strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT MAX(timestamp) FROM daily WHERE date(timestamp) = ?
            """, (today,))
            result = cursor.fetchone()
            conn.close()
            data_timestamp = result[0] if result and result[0] else None
        
        if not data_timestamp:
            return {
                'can_send': False,
                'status': '❌',
                'message': '无法获取数据时间戳',
                'delay_minutes': None
            }
        
        # 计算延迟
        try:
            # 处理各种时间格式
            ts = data_timestamp.replace('T', ' ').replace('Z', '')
            data_dt = datetime.strptime(ts[:19], '%Y-%m-%d %H:%M:%S')
            delay_minutes = (now - data_dt).total_seconds() / 60
        except Exception as e:
            log.error(f"解析时间戳失败: {data_timestamp}, 错误: {e}")
            return {
                'can_send': False,
                'status': '❌',
                'message': f'时间戳解析失败: {e}',
                'delay_minutes': None
            }
        
        # 判断状态
        if delay_minutes <= 5:
            return {
                'can_send': True,
                'status': '✅',
                'message': f'数据时效性良好 (延迟{delay_minutes:.1f}分钟)',
                'delay_minutes': delay_minutes
            }
        elif delay_minutes <= max_delay_minutes:
            return {
                'can_send': True,
                'status': '⚠️',
                'message': f'数据有延迟但可接受 (延迟{delay_minutes:.1f}分钟)',
                'delay_minutes': delay_minutes
            }
        else:
            return {
                'can_send': False,
                'status': '❌',
                'message': f'数据延迟超过{max_delay_minutes}分钟 (延迟{delay_minutes:.1f}分钟), 禁止发送',
                'delay_minutes': delay_minutes
            }


def main():
    """主程序"""
    judge = JudgeAgent()
    judge.run_full_validation()


if __name__ == '__main__':
    main()
