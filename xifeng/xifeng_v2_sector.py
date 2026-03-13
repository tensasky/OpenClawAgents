#!/usr/bin/env python3
"""
西风 V2.0 - 板块分析加强版
每2小时自动分析板块热度，推送Discord
"""

import sqlite3
import json
import requests
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict
import akshare as ak

# 配置
DATA_DIR = Path(__file__).parent / "data"
LOG_DIR = Path(__file__).parent / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Discord配置
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# 数据库路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class SectorAnalyzerV2:
    """板块分析器V2"""
    
    def __init__(self):
        self.hot_sectors = {}
        self.sector_stocks = {}
    
    def fetch_sector_data(self) -> pd.DataFrame:
        """获取板块数据"""
        try:
            # 使用akshare获取板块行情
            df = ak.stock_board_industry_name_em()
            return df
        except Exception as e:
            print(f"获取板块数据失败: {e}")
            return pd.DataFrame()
    
    def analyze_sector_performance(self) -> List[Dict]:
        """分析板块表现"""
        print("🍃 西风V2: 分析板块表现...")
        
        sectors = []
        
        try:
            # 获取行业板块涨幅排名
            df = ak.stock_board_industry_name_em()
            
            if len(df) > 0:
                # 按涨跌幅排序
                df = df.sort_values('涨跌幅', ascending=False)
                
                for _, row in df.head(10).iterrows():
                    sectors.append({
                        'name': row['板块名称'],
                        'change': row['涨跌幅'],
                        'volume': row.get('成交量', 0),
                        'leading_stocks': self.get_sector_leaders(row['板块名称'])
                    })
        except Exception as e:
            print(f"分析板块失败: {e}")
        
        return sectors
    
    def get_sector_leaders(self, sector_name: str) -> List[str]:
        """获取板块龙头股"""
        try:
            # 获取板块内股票
            df = ak.stock_board_industry_cons_em(symbol=sector_name)
            if len(df) > 0:
                # 按涨跌幅排序，取前3
                df = df.sort_values('涨跌幅', ascending=False)
                return df.head(3)['名称'].tolist()
        except:
            pass
        return []
    
    def analyze_market_sentiment(self) -> Dict:
        """分析市场情绪"""
        try:
            # 获取涨跌家数
            df = ak.stock_zh_index_daily_em(symbol="sh000001")
            if len(df) > 0:
                latest = df.iloc[-1]
                return {
                    'index_change': latest.get('涨跌幅', 0),
                    'index_name': '上证指数'
                }
        except:
            pass
        return {}
    
    def generate_report(self) -> str:
        """生成板块分析报告"""
        sectors = self.analyze_sector_performance()
        sentiment = self.analyze_market_sentiment()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        report = f"""🍃 **西风板块分析报告** | {now}

📊 **市场情绪**
上证指数: {sentiment.get('index_change', 0):+.2f}%

🔥 **热门板块Top10**
"""
        
        for i, sector in enumerate(sectors, 1):
            emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📈"
            report += f"""
{emoji} **{sector['name']}** ({sector['change']:+.2f}%)
   龙头股: {', '.join(sector['leading_stocks'][:3])}
"""
        
        report += f"""
💡 **投资建议**
• 关注涨幅前列板块的持续性
• 龙头股表现决定板块强度
• 结合南风信号选择个股

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
        print("🍃 西风V2.0 - 板块分析")
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
