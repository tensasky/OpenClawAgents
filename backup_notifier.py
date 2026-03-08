#!/usr/bin/env python3
"""
备用通知管理器 - Discord 失败时自动切换 Telegram
"""

import requests
import json
from datetime import datetime

# Discord Webhook
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# Telegram Bot
TELEGRAM_TOKEN = "8254326617:AAHNI0UmAbhh2RZQfscshDLow2jqQZ5ICvk"
TELEGRAM_CHAT_ID = "7952042326"  # 你的 Telegram User ID

class BackupNotifier:
    """备用通知管理器"""
    
    def __init__(self):
        self.discord_available = True
        self.telegram_available = True
    
    def send_discord(self, content: str, title: str = None, color: int = 0x3498db) -> bool:
        """发送 Discord 消息"""
        try:
            embed = {
                "title": title or "通知",
                "description": content,
                "color": color,
                "timestamp": datetime.now().isoformat(),
                "footer": {"text": "OpenClaw"}
            }
            
            response = requests.post(
                DISCORD_WEBHOOK,
                json={"embeds": [embed]},
                timeout=10
            )
            
            if response.status_code == 204:
                self.discord_available = True
                return True
            else:
                self.discord_available = False
                return False
                
        except Exception as e:
            print(f"Discord 失败: {e}")
            self.discord_available = False
            return False
    
    def send_telegram(self, text: str) -> bool:
        """发送 Telegram 消息"""
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
            payload = {
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=payload, timeout=10)
            
            if response.status_code == 200:
                self.telegram_available = True
                return True
            else:
                self.telegram_available = False
                print(f"Telegram 错误: {response.text}")
                return False
                
        except Exception as e:
            print(f"Telegram 失败: {e}")
            self.telegram_available = False
            return False
    
    def send(self, content: str, title: str = None, color: int = 0x3498db) -> bool:
        """
        发送通知，Discord 失败自动切 Telegram
        
        优先级:
        1. Discord (主)
        2. Telegram (备)
        """
        # 先尝试 Discord
        if self.send_discord(content, title, color):
            print("✅ Discord 发送成功")
            return True
        
        print("⚠️ Discord 失败，切换到 Telegram...")
        
        # Discord 失败，尝试 Telegram
        # 转换格式为纯文本
        telegram_text = f"*{title or '通知'}*\n\n{content}"
        
        if self.send_telegram(telegram_text):
            print("✅ Telegram 发送成功")
            return True
        
        print("❌ Discord 和 Telegram 都失败了")
        return False


# 全局通知器
_notifier = BackupNotifier()

def send_notification(content: str, title: str = None, color: int = 0x3498db):
    """发送通知（带备用）"""
    return _notifier.send(content, title, color)

def test_channels():
    """测试两个渠道"""
    print("测试通知渠道...")
    print("=" * 60)
    
    # 测试 Discord
    print("1. 测试 Discord...")
    discord_ok = _notifier.send_discord("测试消息", "渠道测试", 0x00ff00)
    print(f"   Discord: {'✅ 正常' if discord_ok else '❌ 失败'}")
    
    # 测试 Telegram
    print("2. 测试 Telegram...")
    telegram_ok = _notifier.send_telegram("🤖 *渠道测试*\n\nTelegram 备用通知测试")
    print(f"   Telegram: {'✅ 正常' if telegram_ok else '❌ 失败'}")
    
    print("=" * 60)
    
    if discord_ok and telegram_ok:
        print("✅ 两个渠道都正常，Discord 为主，Telegram 备用")
    elif discord_ok:
        print("⚠️ 只有 Discord 正常")
    elif telegram_ok:
        print("⚠️ 只有 Telegram 正常，建议检查 Discord")
    else:
        print("❌ 两个渠道都失败，请检查配置")

if __name__ == '__main__':
    test_channels()
