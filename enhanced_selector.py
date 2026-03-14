#!/usr/bin/env python3
"""
强化联动选股系统 - 西风→东风→南风→红中
完整闭环：板块热点 → 活跃个股 → 策略评分 → 交易信号
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

log = get_logger("强化联动")
notifier = get_notifier()

# 导入各Agent
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/xifeng"))
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/dongfeng"))
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/hongzhong"))

from xifeng_v2_sector import XifengV2
from dongfeng_v21 import DongfengV21


class EnhancedStockSelector:
    """强化联动选股系统"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'hot_sectors': [],
            'active_stocks': {},
            'strategy_signals': {},
            'final_signals': []
        }
    
    def step1_xifeng(self) -> List[Dict]:
        """Step 1: 西风 - 发现热点板块"""
        print("\n" + "="*70)
        log.step("Step 1: 西风 - 发现热点板块")
        print("="*70)
        
        xifeng = XifengV2()
        
        # 获取板块数据
        sectors = xifeng.fetch_sector_data()
        if not sectors:
            log.error("西风: 获取板块数据失败")
            return []
        
        # 分析热点
        hot_sectors = xifeng.analyze_hot_sectors(sectors)
        
        # 过滤出真正热的板块
        hot_sectors = [s for s in hot_sectors if s.get('is_hot', False)]
        
        self.results['hot_sectors'] = hot_sectors
        
        log.success(f"西风: 发现 {len(hot_sectors)} 个热点板块")
        for s in hot_sectors[:3]:
            log.info(f"  🔥 {s['name']}: {s.get('change_pct', 0):+.2f}%")
        
        return hot_sectors
    
    def step2_dongfeng(self, hot_sectors: List[Dict]) -> Dict[str, List[Dict]]:
        """Step 2: 东风 - 在热点板块内筛选活跃个股"""
        print("\n" + "="*70)
        log.step("Step 2: 东风 - 板块内筛选活跃股")
        print("="*70)
        
        dongfeng = DongfengV21()
        active_stocks_map = {}
        
        # 对每个热点板块筛选活跃股
        for sector in hot_sectors[:3]:  # 只处理前3个热点板块
            sector_name = sector['name']
            log.info(f"\n分析板块: {sector_name}")
            
            # 在板块内筛选
            active_stocks = dongfeng.run(sector_name)
            
            if active_stocks:
                active_stocks_map[sector_name] = active_stocks
                log.success(f"  发现 {len(active_stocks)} 只活跃股")
            else:
                log.warning(f"  无活跃股票")
        
        self.results['active_stocks'] = active_stocks_map
        
        total = sum(len(stocks) for stocks in active_stocks_map.values())
        log.success(f"东风: 共筛选出 {total} 只活跃股票")
        
        return active_stocks_map
    
    def step3_nanfeng(self, active_stocks_map: Dict[str, List[Dict]]) -> List[Dict]:
        """Step 3: 南风 - 策略评分"""
        print("\n" + "="*70)
        log.step("Step 3: 南风 - 策略评分")
        print("="*70)
        
        all_signals = []
        
        # 合并所有活跃股票
        all_stocks = []
        for sector, stocks in active_stocks_map.items():
            for stock in stocks:
                stock['sector'] = sector
                all_stocks.append(stock)
        
        log.info(f"共 {len(all_stocks)} 只股票需要评分")
        
        # 简化版策略评分（实际应调用南风完整评分）
        for stock in all_stocks[:20]:  # 只评分前20只
            # 模拟评分
            score = 0
            
            # 涨幅评分
            if stock['change_pct'] > 5:
                score += 30
            elif stock['change_pct'] > 3:
                score += 20
            elif stock['change_pct'] > 0:
                score += 10
            
            # 振幅评分
            if stock['amplitude'] > 5:
                score += 20
            elif stock['amplitude'] > 3:
                score += 15
            
            # 板块热度加分
            score += 10
            
            signal = {
                'stock_code': stock['stock_code'],
                'price': stock['price'],
                'change_pct': stock['change_pct'],
                'amplitude': stock['amplitude'],
                'sector': stock['sector'],
                'score': min(score, 100),
                'strategy': '热点板块+活跃股'
            }
            
            all_signals.append(signal)
        
        # 按评分排序
        all_signals.sort(key=lambda x: x['score'], reverse=True)
        
        self.results['strategy_signals'] = all_signals
        
        log.success(f"南风: 生成 {len(all_signals)} 个信号")
        for s in all_signals[:5]:
            log.info(f"  {s['stock_code']}: {s['score']}分 (板块: {s['sector']})")
        
        return all_signals
    
    def step4_hongzhong(self, signals: List[Dict]) -> List[Dict]:
        """Step 4: 红中 - 生成交易信号"""
        print("\n" + "="*70)
        log.step("Step 4: 红中 - 生成交易信号")
        print("="*70)
        
        # 筛选高分信号（>=70分）
        final_signals = [s for s in signals if s['score'] >= 70]
        
        if not final_signals:
            log.warning("红中: 无满足条件的交易信号")
            return []
        
        # 添加交易参数
        for signal in final_signals:
            signal['entry_price'] = signal['price']
            signal['stop_loss'] = round(signal['price'] * 0.97, 2)
            signal['target_1'] = round(signal['price'] * 1.05, 2)
            signal['target_2'] = round(signal['price'] * 1.10, 2)
            signal['timestamp'] = datetime.now().isoformat()
        
        self.results['final_signals'] = final_signals
        
        log.success(f"红中: 生成 {len(final_signals)} 个交易信号")
        for s in final_signals[:5]:
            log.info(f"  🀄 {s['stock_code']}: 买入¥{s['entry_price']:.2f} | 止损¥{s['stop_loss']:.2f}")
        
        return final_signals
    
    def generate_combined_report(self) -> str:
        """生成合并报告"""
        report = ""
        report += "🎯 强化联动选股系统 - 完整报告\n"
        report += "="*70 + "\n"
        report += f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # Step 1: 热点板块
        report += "【Step 1: 西风 - 热点板块】\n"
        if self.results['hot_sectors']:
            for i, sector in enumerate(self.results['hot_sectors'][:5], 1):
                hot = "🔥" if sector.get('is_hot') else "  "
                report += f"{i}. {hot} {sector['name']}: {sector.get('change_pct', 0):+.2f}%\n"
        else:
            report += "无热点板块\n"
        report += "\n"
        
        # Step 2: 活跃股票
        report += "【Step 2: 东风 - 板块内活跃股】\n"
        total_active = sum(len(stocks) for stocks in self.results['active_stocks'].values())
        report += f"共筛选出 {total_active} 只活跃股票\n"
        for sector, stocks in list(self.results['active_stocks'].items())[:3]:
            report += f"\n{sector}:\n"
            for s in stocks[:3]:
                report += f"  - {s['stock_code']}: ¥{s['price']:.2f} ({s['change_pct']:+.2f}%)\n"
        report += "\n"
        
        # Step 3: 策略评分
        report += "【Step 3: 南风 - 策略评分】\n"
        if self.results['strategy_signals']:
            for i, signal in enumerate(self.results['strategy_signals'][:5], 1):
                report += f"{i}. {signal['stock_code']}: {signal['score']}分\n"
                report += f"   板块: {signal['sector']} | 涨幅: {signal['change_pct']:+.2f}%\n"
        report += "\n"
        
        # Step 4: 交易信号
        report += "【Step 4: 红中 - 交易信号】🀄\n"
        if self.results['final_signals']:
            report += f"✅ 生成 {len(self.results['final_signals'])} 个交易信号\n\n"
            for i, signal in enumerate(self.results['final_signals'][:5], 1):
                report += f"{i}. {signal['stock_code']} ({signal['sector']})\n"
                report += f"   买入: ¥{signal['entry_price']:.2f}\n"
                report += f"   止损: ¥{signal['stop_loss']:.2f}\n"
                report += f"   目标: ¥{signal['target_1']:.2f} / ¥{signal['target_2']:.2f}\n"
                report += f"   评分: {signal['score']}分\n\n"
        else:
            report += "⚠️ 无交易信号\n"
        
        report += "="*70 + "\n"
        report += "💡 流程: 西风(板块) → 东风(活跃股) → 南风(评分) → 红中(信号)\n"
        
        return report
    
    def send_combined_notification(self):
        """发送合并通知"""
        report = self.generate_combined_report()
        
        # Discord推送
        import requests
        DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
        
        try:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": report[:1900]},  # Discord限制
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            log.success("合并报告已推送Discord")
        except Exception as e:
            log.fail(f"Discord推送失败: {e}")
        
        # 统一通知
        final_count = len(self.results['final_signals'])
        notifier.trade(
            agent="强化联动",
            message=f"选股完成！发现 {len(self.results['hot_sectors'])} 个热点板块，生成 {final_count} 个交易信号",
            fields=[
                {"name": "热点板块", "value": str(len(self.results['hot_sectors'])), "inline": True},
                {"name": "活跃股票", "value": str(sum(len(s) for s in self.results['active_stocks'].values())), "inline": True},
                {"name": "交易信号", "value": str(final_count), "inline": True}
            ]
        )
    
    def run(self):
        """运行完整联动流程"""
        print("\n" + "="*70)
        print("🎯 强化联动选股系统")
        print("西风 → 东风 → 南风 → 红中")
        print("="*70)
        
        try:
            # Step 1: 西风 - 热点板块
            hot_sectors = self.step1_xifeng()
            if not hot_sectors:
                log.error("未发现热点板块，流程终止")
                return
            
            # Step 2: 东风 - 活跃股
            active_stocks = self.step2_dongfeng(hot_sectors)
            if not active_stocks:
                log.error("未发现活跃股票，流程终止")
                return
            
            # Step 3: 南风 - 策略评分
            signals = self.step3_nanfeng(active_stocks)
            if not signals:
                log.error("无策略信号，流程终止")
                return
            
            # Step 4: 红中 - 交易信号
            final_signals = self.step4_hongzhong(signals)
            
            # 发送合并报告
            self.send_combined_notification()
            
            # 打印完整报告
            print("\n" + self.generate_combined_report())
            
            log.success("强化联动选股系统执行完成！")
            
        except Exception as e:
            log.error(f"联动系统异常: {e}")
            import traceback
            traceback.print_exc()


def main():
    """主程序"""
    selector = EnhancedStockSelector()
    selector.run()


if __name__ == '__main__':
    main()
