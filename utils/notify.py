#!/usr/bin/env python3
"""
通知系统 - 统一通知模板
支持: Discord, Email, 终端
"""

import os
import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from datetime import datetime
from typing import List

# 配置文件（从hongzhong配置读取）
# 默认使用dongfeng的Discord webhook
DISCORD_WEBHOOK = os.environ.get('HONGZHONG_DISCORD_WEBHOOK', 
    'https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48')

# 尝试读取配置文件
CONFIG_PATH = Path.home() / "Documents/OpenClawAgents/hongzhong/config.yaml"
if CONFIG_PATH.exists():
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        
        email_cfg = config.get('notification', {}).get('email', {})
        discord_cfg = config.get('notification', {}).get('discord', {})
        
        EMAIL_CONFIG = {
            'smtp_server': email_cfg.get('smtp_server', 'smtp.qq.com'),
            'smtp_port': email_cfg.get('smtp_port', 465),
            'sender': email_cfg.get('username', '3823810468@qq.com'),
            'password': 'yodqmyrlygqecgaj',
            'receivers': [email_cfg.get('to', '3823810468@qq.com')]
        }
        
        if not DISCORD_WEBHOOK:
            DISCORD_WEBHOOK = discord_cfg.get('webhook_url', '')
        
    except:
        EMAIL_CONFIG = {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 465,
            'sender': '3823810468@qq.com',
            'password': 'yodqmyrlygqecgaj',
            'receivers': ['3823810468@qq.com']
        }
else:
    EMAIL_CONFIG = {
        'smtp_server': 'smtp.qq.com',
        'smtp_port': 465,
        'sender': '3823810468@qq.com',
        'password': 'yodqmyrlygqecgaj',
        'receivers': ['3823810468@qq.com']
    }


def send_discord(message: str, webhook: str = None) -> bool:
    """发送Discord通知"""
    import requests
    
    if not webhook:
        webhook = DISCORD_WEBHOOK
    
    if not webhook:
        return False
    
    try:
        data = {
            'content': message,
            'username': '发财交易助手'
        }
        requests.post(webhook, json=data, timeout=10)
        return True
    except Exception as e:
        print(f"Discord发送失败: {e}")
        return False


def send_email(subject: str, content: str, config: dict = None) -> bool:
    """发送邮件通知"""
    if not config:
        config = EMAIL_CONFIG
    
    if not config.get('password'):
        print("未配置邮件密码")
        return False
    
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = config['sender']
        msg['To'] = ', '.join(config['receivers'])
        
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['sender'], config['password'])
        server.sendmail(config['sender'], config['receivers'], msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def notify_trade(action: str, stock_code: str, stock_name: str, 
                 price: float, quantity: int, reason: str = "",
                 config: dict = None):
    """
    发送交易通知
    
    Args:
        action: BUY/SELL
        stock_code: 股票代码
        stock_name: 股票名称
        price: 成交价格
        quantity: 成交数量
        reason: 交易原因
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    emoji = "🟢" if action == "BUY" else "🔴"
    
    message = f"""
{emoji} **{action} 交易通知**
━━━━━━━━━━━━━━━━━━━━
时间: {timestamp}
股票: {stock_code} {stock_name}
价格: ¥{price:.2f}
数量: {quantity}股
金额: ¥{price * quantity:.2f}
原因: {reason}
━━━━━━━━━━━━━━━━━━━━
"""
    
    # 打印到终端
    print(message)
    
    # 发送Discord
    send_discord(message)
    
    # 发送邮件
    html_content = f"""
<h2>{emoji} {action} 交易通知</h2>
<p><b>时间:</b> {timestamp}</p>
<p><b>股票:</b> {stock_code} {stock_name}</p>
<p><b>价格:</b> ¥{price:.2f}</p>
<p><b>数量:</b> {quantity}股</p>
<p><b>金额:</b> ¥{price * quantity:.2f}</p>
<p><b>原因:</b> {reason}</p>
"""
    send_email(f"🎯 {action} {stock_code}", html_content, config)


def notify_alert(level: str, title: str, content: str):
    """发送告警通知"""
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
    
    message = f"{emoji} **{title}**\n{content}"
    print(message)
    send_discord(message)


if __name__ == '__main__':
    # 测试
    notify_trade("BUY", "sh600519", "贵州茅台", 1850.0, 100, "南风V5.1评分85分")
