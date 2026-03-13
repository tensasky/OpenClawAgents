#!/usr/bin/env python3
"""
西风 V2.0 - 板块分析加强版 (简化版)
使用本地数据库分析板块表现，每2小时推送Discord
"""

import sqlite3
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# 配置
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Discord配置
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# 数据库路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class SectorAnalyzerV2:
    """板块分析器V2 - 简化版"""
    
    def analyze_from_db(self) -> List[Dict]:
        """从本地数据库分析板块表现"""
        print("🍃 西风V2: 从本地数据库分析板块...")
        
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            
            # 获取今日所有股票涨跌情况
            today = datetime.now().strftime('%Y-%m-%d')
            
            df = pd.read_sql_query(f"""
                SELECT stock_code, 
                       (close - open) / open * 100 as change_pct,
                       volume
                FROM daily
                WHERE date(timestamp) = '{today}'
            """, conn)
            
            conn.close()
            
            if len(df) == 0:
                return []
            
            # 统计涨跌分布
            up_count = len(df[df['change_pct'] > 0])
            down_count = len(df[df['change_pct'] < 0])
            flat_count = len(df[df['change_pct'] == 0])
            
            # 获取涨幅前列的股票
            top_gainers = df.nlargest(10, 'change_pct')
            
            sectors = []
            for _, row in top_gainers.iterrows():
                code = row['stock_code']
                # 简单分类（实际应该用板块映射表）
                sector = self.classify_stock(code)
                sectors.append({
                    'code': code,
                    'change': row['change_pct'],
                    'sector': sector
                })
            
            return {
                'up_count': up_count,
                'down_count': down_count,
                'flat_count': flat_count,
                'top_gainers': sectors
            }
            
        except Exception as e:
            print(f"分析失败: {e}")
            return {}
    
    def classify_stock(self, code: str) -> str:
        """简单股票分类（实际应该用板块映射表）"""
        # 这里简化处理，实际应该从数据库查询板块信息
        if code.startswith('sh60'):
            return '沪市主板'
        elif code.startswith('sz00'):
            return '深市主板'
        elif code.startswith('sz30'):
            return '创业板'
        elif code.startswith('sh68'):
            return '科创板'
        return '其他'
    
    def generate_report(self) -> str:
        """生成板块分析报告"""
        data = self.analyze_from_db()
        
        if not data:
            return "🍃 西风V2: 暂无数据"
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        total = data.get('up_count', 0) + data.get('down_count', 0) + data.get('flat_count', 0)
        
        if total == 0:
            return "🍃 西风V2: 暂无数据"
        
        up_ratio = data.get('up_count', 0) / total * 100
        
        report = f"""🍃 **西风板块分析报告** | {now}

📊 **市场情绪**
涨跌比: {data.get('up_count', 0)}:{data.get('down_count', 0)} (上涨{up_ratio:.1f}%)
总股票数: {total}

🔥 **涨幅前列**
"""
        
        for i, stock in enumerate(data.get('top_gainers', [])[:5], 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📈"
            report += f"{emoji} {stock['code']}: {stock['change']:+.2f}% ({stock['sector']})\n"
        
        report += f"""
💡 **投资建议**
• 关注涨幅前列板块的持续性
• 结合南风信号选择个股
• 注意市场整体情绪变化

⏰ 下次更新: {(datetime.now() + timedelta(hours=2)).strftime('%H:%M')}
"""
        
        return report
    
    def send_to_discord(self, message: str):
        """发送到Discord"""
        try:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": message},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            print("✅ Discord推送成功")
        except Exception as e:
            print(f"❌ Discord推送失败: {e}")
    
    def run(self):
        """运行分析"""
        print("="*70)
        print("🍃 西风V2.0 - 板块分析 (简化版)")
        print("="*70)
        
        report = self.generate_report()
        print(report)
        
        self.send_to_discord(report)
        
        # 保存报告
        report_file = DATA_DIR / f"sector_report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📄 报告已保存: {report_file}")
        print("="*70)


def main():
    """主程序"""
    analyzer = SectorAnalyzerV2()
    analyzer.run()


if __name__ == '__main__':
    main()
