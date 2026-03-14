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
        
        # 保存报告
        report_file = REPORT_DIR / f"judge_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        print(f"\n📄 报告已保存: {report_file}")
        print("="*70)
        
        return results


def main():
    """主程序"""
    judge = JudgeAgent()
    judge.run_full_validation()


if __name__ == '__main__':
    main()
