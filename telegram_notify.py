#!/usr/bin/env python3
"""
Telegram 通知模块 - 备用通知渠道
"""

import requests
import json
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/ "utils"))
from agent_logger import get_logger

log = get_logger("System")


# Telegram Bot 配置
BOT_TOKEN = "8254326617:AAHNI0UmAbhh2RZQfscshDLow2jqQZ5ICvk"
CHAT_ID = "1479827696556048596"  # 你的 Discord ID 作为备用标识

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(text: str, parse_mode: str = "Markdown") -> bool:
    """发送 Telegram 消息"""
    url = f"{BASE_URL}/sendMessage"
    
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": parse_mode
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        log.info(f"Telegram 发送失败: {e}")
        return False

def send_beifeng_report(stocks: int, records: int, latest: str):
    """发送北风报告"""
    text = f"""
🌪️ *北风数据报告*

📊 数据状态
• 已入库股票: {stocks} 只
• 总记录数: {records:,} 条
• 最新数据: {latest[:10]}

⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}
"""
    return send_message(text)

def send_xifeng_report(sectors: list):
    """发送西风报告"""
    high = [s for s in sectors if s.get('level') == 'High']
    medium = [s for s in sectors if s.get('level') == 'Medium']
    
    text = f"""
🌪️ *西风热点报告*

📊 市场概览
• 监控板块: {len(sectors)} 个
• 热点: {len(high)} 个 🔥
• 中热: {len(medium)} 个 📈

📈 热点板块
"""
    for s in medium[:3]:
        text += f"• {s.get('sector', 'N/A')}: {s.get('heat_score', 0)}分\n"
    
    if not medium:
        text += "• 暂无热点\n"
    
    text += f"\n⏰ 更新时间: {datetime.now().strftime('%H:%M:%S')}"
    
    return send_message(text)

def send_alert(message: str):
    """发送告警"""
    text = f"🚨 *告警*\n\n{message}\n\n⏰ {datetime.now().strftime('%H:%M:%S')}"
    return send_message(text)

if __name__ == '__main__':
    # 测试
    log.info("测试 Telegram 通知...")
    result = send_message("🤖 OpenClaw 备用通知测试\n\n北风/西风 Telegram 通知已配置")
    log.info(f"发送结果: {'成功' if result else '失败'}")
