#!/usr/bin/env python3
"""
十五五板块实时监控 - 15th Five-Year Real-time Monitor
监控重点板块涨跌，筛选活跃股票
"""

import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

log = get_logger("十五五监控")
notifier = get_notifier()

from strategy_15th_five_year import FifteenthFiveYearMonitor, FIFTEENTH_FIVE_YEAR_SECTORS

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class SectorMonitor:
    """板块实时监控器"""
    
    def __init__(self):
        self.strategy = FifteenthFiveYearMonitor()
        self.priority_stocks = self.strategy.get_priority_stocks(max_priority=3)
        
    def get_stock_performance(self, stock_code: str) -> Dict:
        """获取单只股票今日表现"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT close, open, high, low, volume,
                       (close - open) / open * 100 as change_pct,
                       (high - low) / open * 100 as amplitude
                FROM daily
                WHERE stock_code = ? AND date(timestamp) = ?
            """, (stock_code, today))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'code': stock_code,
                    'close': result[0],
                    'open': result[1],
                    'high': result[2],
                    'low': result[3],
                    'volume': result[4],
                    'change_pct': round(result[5], 2),
                    'amplitude': round(result[6], 2)
                }
            return None
            
        except Exception as e:
            log.warning(f"获取 {stock_code} 数据失败: {e}")
            return None
    
    def scan_priority_stocks(self) -> List[Dict]:
        """扫描高优先级股票"""
        log.step(f"扫描 {len(self.priority_stocks)} 只高优先级股票")
        
        active_stocks = []
        
        for stock in self.priority_stocks[:20]:  # 先扫描前20只
            perf = self.get_stock_performance(stock)
            
            if perf:
                # 筛选活跃股票（涨幅>2% 或 振幅>5%）
                if perf['change_pct'] > 2 or perf['amplitude'] > 5:
                    # 获取板块信息
                    sector_info = self.strategy.get_sector_by_stock(stock)
                    if sector_info:
                        perf.update(sector_info)
                    active_stocks.append(perf)
        
        # 按涨幅排序
        active_stocks.sort(key=lambda x: x['change_pct'], reverse=True)
        
        return active_stocks
    
    def generate_sector_report(self, active_stocks: List[Dict]) -> str:
        """生成板块监控报告"""
        today = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        report = f"""
🎯 十五五板块实时监控
⏰ 时间: {today}

📊 重点监控板块:
🔥 新质生产力 | 🌱 绿色低碳 | ⚙️ 高端制造
💻 数字经济 | 💊 生物医药 | 🛡️ 自主可控

"""
        
        if active_stocks:
            report += f"📈 活跃股票: {len(active_stocks)} 只\n\n"
            
            for i, stock in enumerate(active_stocks[:10], 1):
                change_emoji = "🚀" if stock['change_pct'] > 5 else "📈" if stock['change_pct'] > 0 else "📉"
                sector_tag = stock.get('sub_sector', '未知板块')
                
                report += f"{i}. {stock['code']} ({sector_tag})\n"
                report += f"   现价: ¥{stock['close']:.2f} | 涨跌: {stock['change_pct']:+.2f}% {change_emoji}\n"
                report += f"   振幅: {stock['amplitude']:.2f}% | 成交量: {stock['volume']:,}\n\n"
        else:
            report += "⏸️ 暂无活跃股票\n"
        
        report += "\n💡 策略: 关注涨幅>2%且板块龙头的股票"
        
        return report
    
    def send_notification(self, active_stocks: List[Dict]):
        """发送通知"""
        if not active_stocks:
            return
        
        # 统一通知
        top_stocks = ', '.join([s['code'] for s in active_stocks[:3]])
        
        notifier.trade(
            agent="十五五板块监控",
            message=f"发现 {len(active_stocks)} 只重点板块活跃股票",
            fields=[
                {"name": "活跃股票", "value": str(len(active_stocks)), "inline": True},
                {"name": "TOP3", "value": top_stocks, "inline": False}
            ]
        )
        
        log.success(f"通知已发送: {len(active_stocks)} 只活跃股票")
    
    def run(self):
        """运行监控"""
        log.step("十五五板块监控启动")
        
        # 扫描活跃股票
        active_stocks = self.scan_priority_stocks()
        
        # 生成报告
        report = self.generate_sector_report(active_stocks)
        print(report)
        
        # 发送通知（如果有活跃股票）
        if active_stocks:
            self.send_notification(active_stocks)
        else:
            log.info("无活跃股票，静默模式")
        
        log.success("十五五板块监控完成")


def main():
    """主程序"""
    monitor = SectorMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
