#!/usr/bin/env python3
"""
西风 - Discord 通知模块
"""

import requests
import json
from datetime import datetime
from pathlib import Path

SKILL_DIR = Path(__file__).parent
WEBHOOK_URL = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

def send_discord_message(content: str, title: str = None, color: int = 0x3498db):
    """发送 Discord 消息"""
    
    embed = {
        "title": title or "西风通知",
        "description": content,
        "color": color,
        "timestamp": datetime.now().isoformat(),
        "footer": {
            "text": "🌪️ 西风舆情分析系统"
        }
    }
    
    payload = {"embeds": [embed]}
    
    try:
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        return response.status_code == 204
    except Exception as e:
        print(f"Discord 发送失败: {e}")
        return False

def send_report():
    """发送热点报告"""
    try:
        # 读取 hot_spots.json
        with open(SKILL_DIR / "data" / "hot_spots.json") as f:
            data = json.load(f)
        
        sectors = data.get('hot_spots', [])
        
        # 分类
        high = [s for s in sectors if s['level'] == 'High']
        medium = [s for s in sectors if s['level'] == 'Medium']
        low = [s for s in sectors if s['level'] == 'Low']
        
        content = f"""
🌪️ **西风热点报告** ({datetime.now().strftime('%H:%M')})

📊 **市场概览**
• 监控板块: {len(sectors)} 个
• 热点(High): {len(high)} 个 🔥
• 中热(Medium): {len(medium)} 个 📈
• 低热(Low): {len(low)} 个 📉

📈 **中热板块**
"""
        
        for s in medium[:5]:
            content += f"• {s['sector']}: {s['heat_score']}分 | 爆发{s['momentum']}x\n"
        
        if not medium:
            content += "• 暂无中热板块\n"
        
        content += f"""
📉 **低热板块**
"""
        
        for s in low[:5]:
            content += f"• {s['sector']}: {s['heat_score']}分 | 今日{s['today_count']}次\n"
        
        # 根据热度选择颜色
        if high:
            color = 0xff0000  # 红色 - 有热点
        elif medium:
            color = 0xffa500  # 橙色 - 有中热
        else:
            color = 0x3498db  # 蓝色 - 正常
        
        send_discord_message(content, "🌪️ 西风热点报告", color)
        print("✅ Discord 报告已发送")
        
    except Exception as e:
        print(f"报告生成失败: {e}")

if __name__ == '__main__':
    send_report()
