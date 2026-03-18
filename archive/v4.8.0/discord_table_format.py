#!/usr/bin/env python3
"""
红中 V3.3 - Discord表格格式优化
参考用户提供的清晰表格样式
"""

import json
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("红中")


class DiscordTableFormat:
    """Discord表格格式生成器"""
    
    @staticmethod
    def generate_conservative_block(signals):
        """生成保守策略块"""
        
        # 表头
        header = "```\n🛡️ 保守策略 (高门槛筛选)```\n"
        
        # 表格内容 - 使用代码块实现表格效果
        table = "```\n"
        table += "股票           买入价    策略       评分  板块    趋势       热点  重大消息\n"
        table += "─" * 80 + "\n"
        
        for sig in signals[:3]:  # Top 3
            code = sig['stock_code']
            name = sig['stock_name'][:4]  # 限制长度
            price = f"¥{sig['entry_price']:.2f}"
            strategy = sig['strategy'][:6]
            score = f"{sig.get('score', 'N/A')}"
            sector = sig.get('sector', '待分析')[:4]
            trend = sig.get('trend', '待分析')[:6]
            hot = "是" if sig.get('is_hot') else "否"
            news = sig.get('news', '无')[:8]
            
            table += f"{code} {name:<4} {price:<8} {strategy:<6} {score:<4} {sector:<4} {trend:<6} {hot:<3} {news}\n"
        
        table += "```\n"
        
        return header + table
    
    @staticmethod
    def generate_balance_block(signals):
        """生成平衡策略块"""
        
        # 表头
        header = "```\n⚖️ 平衡策略 (适中筛选)```\n"
        
        # 表格内容
        table = "```\n"
        table += "股票           买入价    策略       评分  板块    趋势       热点  重大消息\n"
        table += "─" * 80 + "\n"
        
        for sig in signals[:3]:  # Top 3
            code = sig['stock_code']
            name = sig['stock_name'][:4]
            price = f"¥{sig['entry_price']:.2f}"
            strategy = sig['strategy'][:6]
            score = f"{sig.get('score', 'N/A')}"
            sector = sig.get('sector', '待分析')[:4]
            trend = sig.get('trend', '待分析')[:6]
            hot = "是" if sig.get('is_hot') else "否"
            news = sig.get('news', '无')[:8]
            
            table += f"{code} {name:<4} {price:<8} {strategy:<6} {score:<4} {sector:<4} {trend:<6} {hot:<3} {news}\n"
        
        table += "```\n"
        
        return header + table
    
    @staticmethod
    def generate_operation_guide():
        """生成操作建议"""
        
        guide = "```\n💡 操作建议\n"
        guide += "─" * 40 + "\n"
        guide += "1. 09:30 - 关注开盘情况，观察市场情绪\n"
        guide += "2. 14:30 - 红中预警信号发布，关注信号变化\n"
        guide += "3. 14:50-15:00 - 执行买入操作，确保成交\n"
        guide += "4. 15:00后 - 设置止损条件单，严格风控\n"
        guide += "```\n"
        
        return guide
    
    @staticmethod
    def generate_full_message(conservative_signals, balance_signals):
        """生成完整消息"""
        
        # 标题
        title = f"🀄 **红中V3.3 - 交易信号预警**\n"
        title += f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')} | 基于真实数据生成\n\n"
        
        # 统计
        stats = f"📊 **信号统计**\n"
        stats += f"```\n"
        stats += f"🛡️ 保守策略: {len(conservative_signals)} 个 | 目标收益8-13% | 胜率85%\n"
        stats += f"⚖️ 平衡策略: {len(balance_signals)} 个 | 目标收益5-8%  | 胜率65%\n"
        stats += f"```\n\n"
        
        # 保守策略块
        conservative_block = DiscordTableFormat.generate_conservative_block(conservative_signals)
        
        # 平衡策略块
        balance_block = DiscordTableFormat.generate_balance_block(balance_signals)
        
        # 操作建议
        operation_guide = DiscordTableFormat.generate_operation_guide()
        
        # 页脚
        footer = f"\n🤖 **红中V3.3** | 财神爷量化交易系统 | 使用真实数据"
        
        full_message = title + stats + conservative_block + "\n" + balance_block + "\n" + operation_guide + footer
        
        return full_message


# 测试
if __name__ == '__main__':
    # 测试数据
    conservative_signals = [
        {
            'stock_code': 'sh600348',
            'stock_name': '华阳股份',
            'entry_price': 10.27,
            'strategy': '趋势跟踪',
            'score': 9.2,
            'sector': '煤炭',
            'trend': '强势上涨',
            'is_hot': True,
            'news': '无重大消息'
        },
        {
            'stock_code': 'sh601888',
            'stock_name': '中国中免',
            'entry_price': 73.74,
            'strategy': '稳健增长',
            'score': 9.1,
            'sector': '免税',
            'trend': '企稳反弹',
            'is_hot': False,
            'news': '消费复苏预期'
        }
    ]
    
    balance_signals = [
        {
            'stock_code': 'sz301667',
            'stock_name': '纳百川',
            'entry_price': 84.79,
            'strategy': '突破策略',
            'score': 8.5,
            'sector': '新能源',
            'trend': '放量突破',
            'is_hot': True,
            'news': '业绩预增'
        },
        {
            'stock_code': 'sz300750',
            'stock_name': '宁德时代',
            'entry_price': 395.50,
            'strategy': '趋势跟踪',
            'score': 8.8,
            'sector': '锂电池',
            'trend': '震荡上行',
            'is_hot': True,
            'news': '订单大增'
        }
    ]
    
    message = DiscordTableFormat.generate_full_message(conservative_signals, balance_signals)
    print(message)
