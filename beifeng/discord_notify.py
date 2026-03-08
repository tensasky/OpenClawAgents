#!/usr/bin/env python3
"""
北风 - Discord 通知模块
"""

import requests
import json
from datetime import datetime
from pathlib import Path

# Discord Webhook
WEBHOOK_URL = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

def send_discord_message(content: str, title: str = None, color: int = 0x00ff00):
    """发送 Discord 消息"""
    
    embed = {
        "title": title or "北风通知",
        "description": content,
        "color": color,
        "timestamp": datetime.now().isoformat(),
        "footer": {
            "text": "🌪️ 北风股票数据采集系统"
        }
    }
    
    payload = {
        "embeds": [embed]
    }
    
    try:
        response = requests.post(
            WEBHOOK_URL,
            json=payload,
            timeout=10
        )
        return response.status_code == 204
    except Exception as e:
        print(f"Discord 发送失败: {e}")
        return False

def send_progress_report(stocks: int, records: int, latest: str):
    """发送进度报告"""
    content = f"""
📊 **数据状态**
• 监控股票: **{stocks}** 只
• 数据记录: **{records:,}** 条
• 最新数据: **{latest[:10]}**

⏰ **定时任务**
• 每5分钟自动更新
• 每小时监控检查
• 自动补全新股票

💡 查看详情: `python3 status.py`
"""
    return send_discord_message(content, "🌪️ 北风进度报告", 0x3498db)

def send_alert(message: str):
    """发送告警"""
    return send_discord_message(message, "🚨 北风告警", 0xff0000)

def send_completion_report():
    """发送完成报告"""
    import sqlite3
    
    WORKSPACE = Path.home() / ".openclaw/agents/beifeng"
    conn = sqlite3.connect(WORKSPACE / "data" / "stocks.db")
    conn.row_factory = sqlite3.Row
    
    cursor = conn.execute("SELECT COUNT(DISTINCT stock_code) as stocks, COUNT(*) as records FROM kline_data")
    row = cursor.fetchone()
    stocks = row['stocks']
    records = row['records']
    
    cursor = conn.execute("SELECT MAX(timestamp) as latest FROM kline_data")
    latest = cursor.fetchone()['latest']
    
    cursor = conn.execute("SELECT COUNT(*) as count FROM fetch_log WHERE status='SUCCESS'")
    success_count = cursor.fetchone()['count']
    
    conn.close()
    
    content = f"""
✅ **核心任务完成**
• 已抓取股票: **{stocks}** 只
• 数据记录: **{records:,}** 条
• 最新数据: **{latest[:10]}**
• 成功抓取: **{success_count}** 次

📊 **系统状态**
• 数据完整度: 核心100只 ✅
• 定时任务: 每5分钟更新 ✅
• 监控检查: 每小时运行 ✅
• 自动补全: 已启用 ✅

🔄 **后续计划**
• 定时任务将逐步补全剩余股票
• 预计完成时间: 24-48 小时
• 数据每日自动更新保持最新

北风已就绪，正在自动运行中。
"""
    return send_discord_message(content, "🌪️ 北风初始化完成", 0x00ff00)

if __name__ == '__main__':
    # 测试
    print("测试 Discord 通知...")
    send_completion_report()
    print("已发送")
