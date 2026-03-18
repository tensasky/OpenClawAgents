#!/usr/bin/env python3
"""
重点股票专项监控系统 - Priority Stocks Monitor
监控核心股票的买入机会：价格突破、回调到位、涨停信号
"""

import sqlite3
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

log = get_logger("重点监控")
notifier = get_notifier()

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
CONFIG_FILE = Path(__file__).parent / "priority_stocks_config.json"


class PriorityStockMonitor:
    """重点股票监控器"""
    
    def __init__(self):
        self.config = self.load_config()
        self.watch_list = self.config.get('watch_list', [])
        self.alert_config = self.config.get('alert_config', {})
        self.signals = []
        
    def load_config(self) -> Dict:
        """加载配置文件"""
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def get_stock_data(self, stock_code: str, days: int = 20) -> List[Dict]:
        """获取股票近期数据"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            cursor.execute("""
                SELECT 
                    date(timestamp) as date,
                    open, high, low, close, volume,
                    (close - open) / open * 100 as change_pct
                FROM daily
                WHERE stock_code = ? 
                AND date(timestamp) >= ?
                ORDER BY timestamp DESC
            """, (stock_code, start_date.strftime('%Y-%m-%d')))
            
            results = []
            for row in cursor.fetchall():
                results.append({
                    'date': row[0],
                    'open': row[1],
                    'high': row[2],
                    'low': row[3],
                    'close': row[4],
                    'volume': row[5],
                    'change_pct': row[6]
                })
            
            conn.close()
            return results
            
        except Exception as e:
            log.error(f"获取 {stock_code} 数据失败: {e}")
            return []
    
    def calculate_ma(self, data: List[Dict], period: int) -> float:
        """计算均线"""
        if len(data) < period:
            return None
        closes = [d['close'] for d in data[:period]]
        return sum(closes) / len(closes)
    
    def analyze_stock(self, stock_config: Dict) -> Dict:
        """分析单只股票"""
        code = stock_config['code']
        name = stock_config['name']
        buy_conditions = stock_config['buy_conditions']
        
        data = self.get_stock_data(code)
        if not data or len(data) < 5:
            return None
        
        latest = data[0]
        prev = data[1] if len(data) > 1 else None
        
        result = {
            'code': code,
            'name': name,
            'sector': stock_config['sector'],
            'strategy': stock_config['strategy'],
            'priority': stock_config['priority'],
            'latest_price': latest['close'],
            'change_pct': latest['change_pct'],
            'volume': latest['volume'],
            'signals': []
        }
        
        # 计算均线
        ma5 = self.calculate_ma(data, 5)
        ma10 = self.calculate_ma(data, 10)
        ma20 = self.calculate_ma(data, 20)
        
        result['ma5'] = ma5
        result['ma10'] = ma10
        result['ma20'] = ma20
        
        # 计算量比（今日 vs 前5日平均）
        if len(data) >= 6:
            avg_volume = sum(d['volume'] for d in data[1:6]) / 5
            volume_ratio = latest['volume'] / avg_volume if avg_volume > 0 else 0
            result['volume_ratio'] = round(volume_ratio, 2)
        else:
            result['volume_ratio'] = 1.0
        
        # 信号检测
        
        # 1. 价格突破信号
        breakout_price = buy_conditions.get('breakout_above')
        if breakout_price and latest['close'] > breakout_price:
            if result['volume_ratio'] >= buy_conditions.get('volume_ratio_min', 1.5):
                result['signals'].append({
                    'type': '突破买入',
                    'strength': '强' if result['volume_ratio'] > 2 else '中',
                    'price': latest['close'],
                    'message': f'突破¥{breakout_price}，量比{result["volume_ratio"]}'
                })
        
        # 2. 回调买入信号
        price_below = buy_conditions.get('price_below')
        if price_below and latest['close'] <= price_below:
            result['signals'].append({
                'type': '回调买入',
                'strength': '中',
                'price': latest['close'],
                'message': f'价格跌至¥{latest["close"]:.2f}，低于目标价¥{price_below}'
            })
        
        # 3. 支撑位反弹
        support_level = buy_conditions.get('support_level')
        if support_level:
            if latest['low'] <= support_level * 1.02 and latest['close'] > latest['open']:
                result['signals'].append({
                    'type': '支撑反弹',
                    'strength': '中',
                    'price': latest['close'],
                    'message': f'触及支撑位¥{support_level}后反弹'
                })
        
        # 4. 涨停信号
        if latest['change_pct'] >= 9.9:
            result['signals'].append({
                'type': '涨停',
                'strength': '强',
                'price': latest['close'],
                'message': '当日涨停，次日可关注二板机会'
            })
        
        # 5. 成交量异常
        volume_threshold = self.alert_config.get('volume_spike_threshold', 2.0)
        if result['volume_ratio'] >= volume_threshold:
            result['signals'].append({
                'type': '量能异动',
                'strength': '中',
                'price': latest['close'],
                'message': f'成交量放大{result["volume_ratio"]:.1f}倍'
            })
        
        # 6. 价格大幅波动
        price_change_threshold = self.alert_config.get('price_change_threshold', 3.0)
        if abs(latest['change_pct']) >= price_change_threshold:
            direction = "大涨" if latest['change_pct'] > 0 else "大跌"
            result['signals'].append({
                'type': f'{direction} alert',
                'strength': '中',
                'price': latest['close'],
                'message': f'当日{direction}{latest["change_pct"]:.2f}%'
            })
        
        return result
    
    def scan_all_stocks(self) -> List[Dict]:
        """扫描所有重点股票"""
        log.step(f"扫描 {len(self.watch_list)} 只重点股票")
        
        results = []
        for stock_config in self.watch_list:
            result = self.analyze_stock(stock_config)
            if result:
                results.append(result)
        
        # 按优先级排序
        results.sort(key=lambda x: (x['priority'], len(x['signals'])), reverse=True)
        
        return results
    
    def generate_report(self, results: List[Dict]) -> str:
        """生成监控报告"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # 统计有信号的股票
        stocks_with_signals = [r for r in results if r['signals']]
        
        report = f"""
🎯 重点股票监控报告
⏰ 时间: {now}

📊 监控概况:
  监控总数: {len(results)}只
  有信号: {len(stocks_with_signals)}只
  无信号: {len(results) - len(stocks_with_signals)}只

"""
        
        # 买入信号
        if stocks_with_signals:
            report += "🔥 买入信号:\n"
            report += "-" * 60 + "\n"
            
            for stock in stocks_with_signals[:5]:  # 只显示前5个
                priority_emoji = "⭐" * stock['priority']
                report += f"\n{priority_emoji} {stock['name']} ({stock['code']})\n"
                report += f"   板块: {stock['sector']} | 策略: {stock['strategy']}\n"
                report += f"   现价: ¥{stock['latest_price']:.2f} ({stock['change_pct']:+.2f}%)\n"
                
                if stock.get('volume_ratio'):
                    report += f"   量比: {stock['volume_ratio']} | "
                if stock.get('ma5'):
                    report += f"MA5: ¥{stock['ma5']:.2f}\n"
                
                report += "   信号:\n"
                for signal in stock['signals'][:3]:  # 最多显示3个信号
                    strength_emoji = "🔴" if signal['strength'] == '强' else "🟡"
                    report += f"      {strength_emoji} [{signal['type']}] {signal['message']}\n"
        
        else:
            report += "⏸️ 暂无买入信号\n"
        
        # 持仓建议
        report += f"\n💡 持仓建议:\n"
        report += "-" * 60 + "\n"
        
        priority1_stocks = [r for r in results if r['priority'] == 1]
        if priority1_stocks:
            report += f"   高优先级标的 ({len(priority1_stocks)}只):\n"
            for s in priority1_stocks[:3]:
                has_signal = "🔥有信号" if s['signals'] else "⏸️观望"
                report += f"      • {s['name']}: ¥{s['latest_price']:.2f} {has_signal}\n"
        
        report += f"\n   操作建议:\n"
        report += f"      1. 优先关注有买入信号的股票\n"
        report += f"      2. 突破信号需配合成交量确认\n"
        report += f"      3. 回调买入需等待企稳\n"
        report += f"      4. 严格止损，单票不超过20%\n"
        
        return report
    
    def send_notifications(self, results: List[Dict]):
        """发送通知"""
        # 只发送强信号（突破买入、涨停）
        strong_signals = []
        for stock in results:
            for signal in stock['signals']:
                if signal['strength'] == '强' and signal['type'] in ['突破买入', '涨停']:
                    strong_signals.append({
                        'stock': stock['name'],
                        'code': stock['code'],
                        'signal': signal['type'],
                        'price': signal['price'],
                        'message': signal['message']
                    })
        
        if not strong_signals:
            log.info("无强信号，静默模式")
            return
        
        # Discord通知
        for sig in strong_signals[:3]:  # 最多推送3个
            notifier.trade(
                agent="重点监控",
                message=f"🚨 {sig['stock']} - {sig['signal']}",
                fields=[
                    {"name": "股票代码", "value": sig['code'], "inline": True},
                    {"name": "当前价格", "value": f"¥{sig['price']:.2f}", "inline": True},
                    {"name": "信号详情", "value": sig['message'], "inline": False}
                ]
            )
        
        log.success(f"发送 {len(strong_signals)} 个强信号通知")
    
    def run(self):
        """运行监控"""
        log.step("重点股票监控启动")
        
        # 扫描所有股票
        results = self.scan_all_stocks()
        
        # 生成报告
        report = self.generate_report(results)
        print(report)
        
        # 发送通知
        self.send_notifications(results)
        
        log.success("重点股票监控完成")


def main():
    """主程序"""
    monitor = PriorityStockMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
