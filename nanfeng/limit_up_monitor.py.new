#!/usr/bin/env python3
"""
涨停策略实时监控系统 - Limit Up Real-time Monitor
监控首板、二板机会，自动筛选最佳买点
"""

import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

sys.path.insert(0, str(Path(__file__).parent))
from strategy_15th_five_year import FifteenthFiveYearMonitor

log = get_logger("涨停监控")
notifier = get_notifier()

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


class LimitUpMonitor:
    """涨停实时监控器"""
    
    def __init__(self):
        self.sector_monitor = FifteenthFiveYearMonitor()
        self.priority_stocks = self.sector_monitor.get_priority_stocks(max_priority=3)
        self.signals = []
        
    def get_today_data(self) -> List[Dict]:
        """获取今日所有股票数据"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    stock_code,
                    open, high, low, close, volume,
                    (close - open) / open * 100 as change_pct,
                    (high - low) / open * 100 as amplitude,
                    close / open as limit_ratio
                FROM daily
                WHERE date(timestamp) = ?
                ORDER BY change_pct DESC
            """, (today,))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'code': row[0],
                    'open': row[1],
                    'high': row[2],
                    'low': row[3],
                    'close': row[4],
                    'volume': row[5],
                    'change_pct': round(row[6], 2),
                    'amplitude': round(row[7], 2),
                    'limit_ratio': row[8]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            log.error(f"获取今日数据失败: {e}")
            return []
    
    def get_yesterday_data(self) -> Dict[str, Dict]:
        """获取昨日数据（用于判断首板）"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
            
            cursor.execute("""
                SELECT 
                    stock_code,
                    close,
                    (close - open) / open * 100 as change_pct,
                    volume
                FROM daily
                WHERE date(timestamp) = ?
            """, (yesterday,))
            
            results = {}
            for row in cursor.fetchall():
                results[row[0]] = {
                    'close': row[1],
                    'change_pct': row[2],
                    'volume': row[3]
                }
            
            conn.close()
            return results
            
        except Exception as e:
            log.error(f"获取昨日数据失败: {e}")
            return {}
    
    def is_limit_up(self, change_pct: float) -> bool:
        """判断是否涨停（主板9.9%，创业板/科创板19.9%）"""
        return change_pct >= 9.9
    
    def scan_limit_up_stocks(self) -> Dict[str, List[Dict]]:
        """扫描涨停股票"""
        today_data = self.get_today_data()
        yesterday_data = self.get_yesterday_data()
        
        first_board = []    # 首板
        second_board = []   # 二板
        third_board = []    # 三板
        
        for stock in today_data:
            if not self.is_limit_up(stock['change_pct']):
                continue
            
            code = stock['code']
            
            # 检查是否是十五五重点股票
            sector_info = self.sector_monitor.get_sector_by_stock(code)
            if sector_info:
                stock['sector'] = sector_info['main_sector']
                stock['sub_sector'] = sector_info['sub_sector']
                stock['is_priority'] = True
            else:
                stock['is_priority'] = False
            
            # 判断是几板
            if code in yesterday_data:
                yest = yesterday_data[code]
                if yest['change_pct'] >= 9.9:  # 昨日也涨停
                    # 检查前天是否涨停（需要更多数据，简化处理）
                    second_board.append(stock)
                else:  # 昨日未涨停，今日首板
                    # 检查成交量放大
                    if code in yesterday_data:
                        vol_ratio = stock['volume'] / yest['volume'] if yest['volume'] > 0 else 0
                        stock['volume_ratio'] = round(vol_ratio, 2)
                        if vol_ratio >= 1.5:  # 成交量放大1.5倍以上
                            first_board.append(stock)
                        else:
                            stock['weak_reason'] = '成交量不足'
                            first_board.append(stock)  # 仍然加入，但标记弱势
            else:
                # 无昨日数据，无法判断，暂归为首板
                first_board.append(stock)
        
        return {
            'first_board': first_board,
            'second_board': second_board,
            'third_board': third_board
        }
    
    def score_stock(self, stock: Dict) -> int:
        """给涨停股打分（满分100）"""
        score = 0
        
        # 板块加分（十五五板块）
        if stock.get('is_priority'):
            score += 30
            if stock.get('sector') == '新质生产力':
                score += 10  # 最热点板块额外加分
        
        # 成交量加分
        vol_ratio = stock.get('volume_ratio', 1)
        if vol_ratio >= 3:
            score += 25
        elif vol_ratio >= 2:
            score += 20
        elif vol_ratio >= 1.5:
            score += 15
        else:
            score += 5
        
        # 封板强度（涨停时间越早越强，用振幅估算）
        if stock['amplitude'] <= 10:  # 开盘后很快封板
            score += 25
        elif stock['amplitude'] <= 15:
            score += 15
        else:
            score += 5
        
        # 股价（低价股更容易连板）
        if stock['close'] < 30:
            score += 15
        elif stock['close'] < 50:
            score += 10
        else:
            score += 5
        
        # 是否弱势
        if stock.get('weak_reason'):
            score -= 20
        
        return min(score, 100)
    
    def generate_report(self, limit_up_data: Dict[str, List[Dict]]) -> str:
        """生成涨停监控报告"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        report = f"""
🎯 涨停策略实时监控
⏰ 时间: {now}

📊 涨停概况:
"""
        
        total = len(limit_up_data['first_board']) + len(limit_up_data['second_board']) + len(limit_up_data['third_board'])
        report += f"  总涨停: {total}只\n"
        report += f"  🔥 首板: {len(limit_up_data['first_board'])}只\n"
        report += f"  🚀 二板: {len(limit_up_data['second_board'])}只\n"
        report += f"  👑 三板+: {len(limit_up_data['third_board'])}只\n\n"
        
        # 首板分析
        if limit_up_data['first_board']:
            report += "🔥 首板机会（按质量排序）:\n"
            
            # 打分排序
            scored_stocks = [(s, self.score_stock(s)) for s in limit_up_data['first_board']]
            scored_stocks.sort(key=lambda x: x[1], reverse=True)
            
            for i, (stock, score) in enumerate(scored_stocks[:10], 1):
                quality = "⭐⭐⭐" if score >= 80 else "⭐⭐" if score >= 60 else "⭐"
                sector_tag = f"[{stock.get('sub_sector', '其他')}]" if stock.get('is_priority') else ""
                
                report += f"{i}. {stock['code']} {sector_tag} {quality}\n"
                report += f"   价格: ¥{stock['close']:.2f} | 评分: {score}/100\n"
                report += f"   量比: {stock.get('volume_ratio', '-')} | 振幅: {stock['amplitude']:.1f}%\n"
                
                if stock.get('weak_reason'):
                    report += f"   ⚠️ 弱势: {stock['weak_reason']}\n"
                report += "\n"
        
        # 二板分析
        if limit_up_data['second_board']:
            report += "🚀 二板龙头:\n"
            for stock in limit_up_data['second_board'][:5]:
                sector_tag = f"[{stock.get('sub_sector', '其他')}]" if stock.get('is_priority') else ""
                report += f"  • {stock['code']} {sector_tag} - ¥{stock['close']:.2f}\n"
            report += "\n"
        
        # 操作建议
        if limit_up_data['first_board']:
            best = max(limit_up_data['first_board'], key=lambda x: self.score_stock(x))
            best_score = self.score_stock(best)
            
            if best_score >= 80:
                report += f"💡 强烈推荐: {best['code']} (评分{best_score})\n"
                report += f"   建议买点: 打板买入或隔夜委托\n\n"
            elif best_score >= 60:
                report += f"💡 建议关注: {best['code']} (评分{best_score})\n"
                report += f"   建议买点: 等待二板确认\n\n"
        
        report += "⚠️ 风险提示: 涨停策略高风险，严格止损！"
        
        return report
    
    def send_signals(self, limit_up_data: Dict[str, List[Dict]]):
        """发送交易信号"""
        # 只发送高质量首板信号（评分>=70）
        high_quality_first = [
            (s, self.score_stock(s)) for s in limit_up_data['first_board']
            if self.score_stock(s) >= 70
        ]
        
        if not high_quality_first:
            return
        
        high_quality_first.sort(key=lambda x: x[1], reverse=True)
        
        # Discord通知
        top_stocks = [f"{s['code']}(评分{score})" for s, score in high_quality_first[:3]]
        
        notifier.trade(
            agent="涨停监控",
            message=f"发现 {len(high_quality_first)} 只高质量首板",
            fields=[
                {"name": "涨停统计", "value": f"首板{len(limit_up_data['first_board'])} 二板{len(limit_up_data['second_board'])}", "inline": True},
                {"name": "TOP3", "value": ", ".join(top_stocks), "inline": False}
            ]
        )
        
        log.success(f"发送 {len(high_quality_first)} 个高质量信号")
    
    def run(self):
        """运行监控"""
        log.step("涨停策略监控启动")
        
        # 扫描涨停股
        limit_up_data = self.scan_limit_up_stocks()
        
        # 生成报告
        report = self.generate_report(limit_up_data)
        print(report)
        
        # 发送信号
        self.send_signals(limit_up_data)
        
        log.success("涨停策略监控完成")


def main():
    """主程序"""
    monitor = LimitUpMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
