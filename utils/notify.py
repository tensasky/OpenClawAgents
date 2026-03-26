#!/usr/bin/env python3
"""统一通知系统 - Gmail SMTP"""

import smtplib
import requests
import json
from email.mime.text import MIMEText
from email.header import Header
from datetime import datetime

def load_config():
    try:
        with open('utils/email_config.json', 'r') as f:
            return json.load(f)
    except:
        return {}

EMAIL_CONFIG = load_config()

def send_discord(message: str, webhook: str = None) -> bool:
    """发送Discord"""
    if not webhook:
        webhook = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
    try:
        response = requests.post(webhook, json={"content": message}, timeout=10)
        return response.status_code in [200, 204]
    except:
        return False

def send_email(subject: str, content: str, config: dict = None) -> bool:
    """发送邮件 - Gmail SMTP"""
    if not config:
        config = EMAIL_CONFIG
    
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = f'{Header(config.get("sender_name", "财神爷"), "utf-8")} <{config["sender"]}>'
        msg['To'] = ', '.join(config.get('receivers', []))
        
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['sender'], config['password'])
        server.sendmail(config['sender'], config.get('receivers', []), msg.as_string())
        server.quit()
        
        print(f"邮件发送成功: {subject}")
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False

def notify_alert(title: str, message: str, level: str = "info") -> bool:
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
    msg = f"{emoji} **{title}**\n{message}"
    send_discord(msg)
    send_email(title, f"<p>{message}</p>")
    return True

if __name__ == "__main__":
    send_email("测试", "<p>Gmail配置完成</p>")
