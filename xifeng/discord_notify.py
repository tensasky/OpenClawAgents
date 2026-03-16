#!/usr/bin/env python3
"""
西风 - 通知模块（Discord + Telegram 备用）
"""

import sys
import json
from pathlib import Path

# 导入备用通知管理器
sys.path.insert(0, str(Path(__file__).parent.parent))
from backup_notifier import send_notification
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("西风")


SKILL_DIR = Path(__file__).parent

def send_report():
    """发送热点报告"""
    try:
        # 读取 hot_spots.json
        with open(SKILL_DIR / "data" / "hot_spots.json") as f:
            data = json.load(f)
        
        sectors = data.get('hot_sectors', [])
        
        # 分类
        high = [s for s in sectors if s['level'] == 'High']
        medium = [s for s in sectors if s['level'] == 'Medium']
        low = [s for s in sectors if s['level'] == 'Low']
        
        content = f"""
🌪️ **西风热点报告**

📊 市场概览
• 监控板块: {len(sectors)} 个
• 热点: {len(high)} 个 🔥
• 中热: {len(medium)} 个 📈
• 低热: {len(low)} 个 📉

📈 中热板块
"""
        
        for s in medium[:5]:
            content += f"• {s['name']}: {s['heat_score']}分\n"
        
        if not medium:
            content += "• 暂无中热板块\n"
        
        # 根据热度选择颜色
        if high:
            color = 0xff0000
        elif medium:
            color = 0xffa500
        else:
            color = 0x3498db
        
        send_notification(content, "🌪️ 西风热点报告", color)
        log.info("✅ 报告已发送")
        
    except Exception as e:
        log.info(f"报告生成失败: {e}")

if __name__ == '__main__':
    send_report()
