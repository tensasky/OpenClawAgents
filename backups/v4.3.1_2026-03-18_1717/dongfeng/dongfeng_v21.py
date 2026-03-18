#!/usr/bin/env python3
"""
东风 V2.1 - 板块内活跃股筛选（联动版）
在指定板块内筛选活跃个股，支持Discord推送
"""

import sqlite3
import requests
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

log = get_logger("东风")
notifier = get_notifier()

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_DB = Path.home() / "Documents/OpenClawAgents/xifeng/data/xifeng.db"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"


class DongfengV21:
    """东风V2.1 - 板块内活跃股筛选"""
    
    def __init__(self, sector_name: str = None):
        self.sector_name = sector_name
        
    def get_sector_stocks(self, sector_name: str) -> List[str]:
        """获取板块内的股票列表"""
        try:
            conn = sqlite3.connect(XIFENG_DB)
            cursor = conn.cursor()
            
            # 从西风数据库获取板块股票
            cursor.execute("""
                SELECT leading_stocks FROM sectors 
                WHERE sector_name = ? 
                AND date(timestamp) = date('now')
                ORDER BY timestamp DESC
                LIMIT 1
            """, (sector_name,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                # 解析股票代码列表
                stocks = [s.strip() for s in result[0].split(',') if s.strip()]
                log.info(f"板块 [{sector_name}] 包含 {len(stocks)} 只股票")
                return stocks
            else:
                log.warning(f"未找到板块 [{sector_name}] 的股票数据")
                return []
                
        except Exception as e:
            log.error(f"获取板块股票失败: {e}")
            return []
    
    def scan_active_in_sector(self, stocks: List[str]) -> List[Dict]:
        """在指定股票列表中筛选活跃股"""
        if not stocks:
            return []
        
        log.step(f"在 {len(stocks)} 只股票中筛选活跃股")
        
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 构建IN查询
        placeholders = ','.join(['?' for _ in stocks])
        
        # 查询这些股票的今日表现
        cursor.execute(f"""
            SELECT 
                stock_code,
                close,
                (high - low) / open * 100 as amplitude,
                volume,
                (close - open) / open * 100 as change_pct
            FROM daily
            WHERE date(timestamp) = ?
            AND stock_code IN ({placeholders})
            AND volume > 1000000
            AND (high - low) / open > 0.03
            ORDER BY (high - low) / open DESC
        """, [today] + stocks)
        
        active_stocks = []
        for row in cursor.fetchall():
            active_stocks.append({
                'stock_code': row[0],
                'price': row[1],
                'amplitude': round(row[2], 2),
                'volume': row[3],
                'change_pct': round(row[4], 2)
            })
        
        conn.close()
        
        log.info(f"发现 {len(active_stocks)} 只活跃股票")
        return active_stocks
    
    def generate_report(self, sector_name: str, active_stocks: List[Dict]) -> str:
        """生成报告"""
        report = f"🌸 东风V2.1 - 板块内活跃股筛选\n\n"
        report += f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"🏭 板块: {sector_name}\n"
        report += f"📊 活跃股票: {len(active_stocks)} 只\n\n"
        
        if active_stocks:
            report += "🔥 活跃股票列表:\n"
            for i, stock in enumerate(active_stocks[:10], 1):
                change_emoji = "📈" if stock['change_pct'] > 0 else "📉"
                report += f"{i}. {stock['stock_code']}\n"
                report += f"   价格: ¥{stock['price']:.2f} | 涨幅: {stock['change_pct']:+.2f}% {change_emoji}\n"
                report += f"   振幅: {stock['amplitude']:.2f}% | 成交量: {stock['volume']:,}\n"
        else:
            report += "⚠️ 未发现活跃股票\n"
        
        return report
    
    def send_discord(self, report: str):
        """发送Discord"""
        try:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": report},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            log.success("Discord已发送")
        except Exception as e:
            log.fail(f"Discord失败: {e}")
    
    def send_notification(self, sector_name: str, active_stocks: List[Dict]):
        """发送统一通知"""
        fields = [
            {"name": "板块", "value": sector_name, "inline": True},
            {"name": "活跃股", "value": str(len(active_stocks)), "inline": True}
        ]
        
        if active_stocks:
            top3 = ', '.join([s['stock_code'] for s in active_stocks[:3]])
            fields.append({"name": "TOP3", "value": top3, "inline": False})
        
        notifier.report(
            agent="东风",
            message=f"板块 [{sector_name}] 筛选出 {len(active_stocks)} 只活跃股",
            fields=fields
        )
    
    def run(self, sector_name: str = None) -> List[Dict]:
        """运行筛选"""
        sector = sector_name or self.sector_name
        
        if not sector:
            log.error("未指定板块名称")
            return []
        
        log.step(f"东风V2.1 开始分析板块: {sector}")
        
        # 获取板块股票
        sector_stocks = self.get_sector_stocks(sector)
        if not sector_stocks:
            log.warning(f"板块 [{sector}] 无股票数据")
            return []
        
        # 筛选活跃股
        active_stocks = self.scan_active_in_sector(sector_stocks)
        
        # 生成报告
        report = self.generate_report(sector, active_stocks)
        
        # 发送通知
        self.send_discord(report)
        self.send_notification(sector, active_stocks)
        
        log.success("东风V2.1 分析完成")
        
        return active_stocks


def main():
    """主程序"""
    import argparse
    
    parser = argparse.ArgumentParser(description='东风V2.1 - 板块内活跃股筛选')
    parser.add_argument('--sector', type=str, help='板块名称')
    args = parser.parse_args()
    
    # 默认使用"人工智能"作为示例
    sector = args.sector or "人工智能"
    
    dongfeng = DongfengV21()
    result = dongfeng.run(sector)
    
    print(f"\n✅ 筛选完成: {len(result)} 只活跃股票")


if __name__ == '__main__':
    main()
