#!/usr/bin/env python3
"""
红中V2.5 - 合并邮件版本
所有预警合并到一封邮件，使用昨日模板格式
"""

import json
import logging
import argparse
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import sys

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from stock_names import get_stock_name
from strategy_config import get_strategy

# 配置
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"hongzhong_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("红中V2.5")


class Notifier:
    """通知器 - Discord分开推送，邮件合并推送"""
    
    def __init__(self):
        config_file = Path.home() / ".openclaw/agents/hongzhong/config.json"
        with open(config_file) as f:
            config = json.load(f)
        
        self.discord_webhook = config.get('discord_webhook', '')
        self.qq_email = config.get('qq_email', '')
        self.qq_auth_code = config.get('qq_auth_code', '')
        self.email_recipients = config.get('email_recipients', [self.qq_email])
    
    async def send_discord(self, message: str) -> bool:
        """Discord推送"""
        if not self.discord_webhook:
            return False
        
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                payload = {"content": message}
                async with session.post(self.discord_webhook, json=payload) as resp:
                    return resp.status == 204
        except Exception as e:
            logger.error(f"Discord失败: {e}")
            return False
    
    async def send_email(self, message: str, subject: str) -> bool:
        """QQ邮箱推送"""
        if not self.qq_email or not self.qq_auth_code:
            return False
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.header import Header
            
            msg = MIMEText(message, 'plain', 'utf-8')
            msg['From'] = self.qq_email
            msg['To'] = ', '.join(self.email_recipients)
            msg['Subject'] = Header(subject, 'utf-8')
            
            server = smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=30)
            server.login(self.qq_email, self.qq_auth_code)
            server.sendmail(self.qq_email, self.email_recipients, msg.as_string())
            server.quit()
            
            logger.info(f"✅ 邮件推送成功 ({len(self.email_recipients)}个收件人)")
            return True
        except Exception as e:
            logger.error(f"邮件失败: {e}")
            return False


def format_single_stock(stock: Dict, rank: int, total: int) -> str:
    """格式化单只股票 - 使用昨日模板"""
    signals_str = ' | '.join(stock['signals'][:4])
    warnings_str = ' | '.join(stock['warnings'][:2]) if stock['warnings'] else '无'
    hot_tag = "🔥热点 " if stock['is_hot_sector'] else ""
    name_tag = f"({stock['name']}) " if stock.get('name') else ""
    
    config = stock.get('strategy_config', {})
    
    return f"""🚨 [财神爷量化预警] #{rank}/{total}

📈 **{stock['code']}** {name_tag}{hot_tag}
⭐ 综合评分: **{stock['score']:.1f}/10** | 置信度: {stock['confidence']:.0%}
🎯 策略: **{stock.get('strategy', '趋势跟踪')}** | 风险等级: {config.get('risk_level', '中等')}

📊 得分构成:
  ├─ 趋势: {stock.get('trend_score', 0) * 0.4:.1f}分
  ├─ 动量: {stock.get('momentum_score', 0) * 0.3:.1f}分
  ├─ 成交量: {stock.get('volume_score', 0) * 0.2:.1f}分
  └─ 质量: {stock.get('quality_score', 0) * 0.1:.1f}分

✅ 买入信号:
{signals_str}

⚠️ 风险提示:
{warnings_str}

💰 价格信息:
  当前: ¥{stock['price']} | 止损: ¥{stock['stop_loss']}
  目标: ¥{stock['take_profit_1']} (+4%) / ¥{stock['take_profit_2']} (+8%)

📈 技术指标:
 ADX: {stock['adx']} | RSI: {stock['rsi']:.0f} | 相对强度: 前{stock['relative_strength']:.0f}%

💡 交易建议:
 📅 持有周期: {config.get('holding_period', '5-10天')}
 ⏰ 入场时机: {config.get('entry_timing', '收盘前30分钟')}
 🚪 出场策略: {config.get('exit_strategy', '移动止损')}
 💼 最大仓位: {config.get('max_holding', '25%')}
 👤 适合人群: {config.get('suitable_for', '短线趋势交易者')}

{'='*60}
"""


def format_merged_email(stocks: List[Dict], strategy_name: str) -> str:
    """格式化合并邮件 - 所有预警在一封邮件"""
    time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
    
    email_header = f"""🧧 财神爷量化预警报告
{'='*60}
📅 报告时间: {time_str}
🎯 策略: {strategy_name}
📊 今日选出: {len(stocks)} 只股票

"""
    
    # 合并所有股票
    stocks_content = ""
    for i, stock in enumerate(stocks, 1):
        stocks_content += format_single_stock(stock, i, len(stocks))
    
    # 邮件尾部
    email_footer = f"""
{'='*60}
⚠️ 风险提示:
• 以上建议仅供参考，不构成投资建议
• 股市有风险，投资需谨慎
• 请根据自身风险承受能力决策

💰 财神爷量化系统 | 8-Agent智能选股
⏰ 每日14:45自动预警 | 5策略综合评分
{'='*60}
"""
    
    return email_header + stocks_content + email_footer


async def main():
    """主函数"""
    parser = argparse.ArgumentParser()
    parser.add_argument('--strategy', default='趋势跟踪')
    parser.add_argument('--test', action='store_true')
    args = parser.parse_args()
    
    logger.info(f"🀄 红中V2.5启动 - 策略: {args.strategy}")
    
    # 导入南风
    sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
    from nanfeng_v5_1 import NanFengV5_1
    
    # 获取信号
    nanfeng = NanFengV5_1(strategy_name=args.strategy)
    strategy = get_strategy(args.strategy)
    
    market_ok, market_msg = nanfeng.check_market_environment()
    logger.info(f"市场环境: {market_msg}")
    
    signals = nanfeng.scan_signals(max_stocks=300)
    top3 = signals[:3]
    
    if not top3:
        logger.warning("没有符合条件的股票")
        return
    
    # 转换为字典格式
    stocks = []
    for s in top3:
        stock_name = get_stock_name(s.stock_code)
        stocks.append({
            'code': s.stock_code,
            'name': stock_name,
            'score': s.total_score,
            'trend_score': s.trend_score,
            'momentum_score': s.momentum_score,
            'volume_score': s.volume_score,
            'quality_score': s.quality_score,
            'price': round(s.current_price, 2),
            'stop_loss': round(s.stop_loss, 2),
            'take_profit_1': round(s.take_profit_1, 2),
            'take_profit_2': round(s.take_profit_2, 2),
            'signals': s.signals,
            'warnings': s.warnings,
            'is_hot_sector': s.is_hot_sector,
            'adx': round(s.adx, 1),
            'rsi': round(s.rsi, 0),
            'relative_strength': round(s.relative_strength * 100, 0),
            'confidence': s.confidence,
            'strategy': args.strategy,
            'strategy_config': {
                'holding_period': strategy.holding_period,
                'entry_timing': strategy.entry_timing,
                'exit_strategy': strategy.exit_strategy,
                'max_holding': strategy.max_holding,
                'risk_level': strategy.risk_level,
                'suitable_for': strategy.suitable_for
            }
        })
    
    # 格式化合并邮件
    merged_email = format_merged_email(stocks, args.strategy)
    
    # 初始化通知器
    notifier = Notifier()
    
    if args.test:
        print("\n" + merged_email)
        return
    
    # Discord分开推送（3条消息）
    for i, stock in enumerate(stocks, 1):
        discord_msg = format_single_stock(stock, i, len(stocks))
        await notifier.send_discord(discord_msg)
        logger.info(f"Discord推送 #{i} 完成")
    
    # 邮件合并推送（1封邮件包含所有）
    subject = f"🧧 财神爷量化预警 | {args.strategy} | {datetime.now().strftime('%m-%d %H:%M')}"
    email_ok = await notifier.send_email(merged_email, subject)
    
    if email_ok:
        logger.info(f"✅ 合并邮件发送成功，包含{len(stocks)}只股票")
    else:
        logger.error("❌ 合并邮件发送失败")


if __name__ == '__main__':
    asyncio.run(main())
