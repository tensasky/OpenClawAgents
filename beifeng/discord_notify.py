#!/usr/bin/env python3
"""
北风 - 通知模块（Discord + Telegram 备用）
"""

import sys
from pathlib import Path

# 导入备用通知管理器
sys.path.insert(0, str(Path(__file__).parent.parent))
from backup_notifier import send_notification

def send_discord_message(content: str, title: str = None, color: int = 0x00ff00):
    """发送通知（自动备用）"""
    return send_notification(content, title, color)

def send_completion_report():
    """发送完成报告"""
    content = """
🌪️ **北风初始化完成**

✅ 核心任务完成
• 已抓取股票数据
• 定时任务已启动
• 监控检查已启用

北风已就绪！
"""
    return send_notification(content, "🌪️ 北风完成", 0x00ff00)

if __name__ == '__main__':
    send_completion_report()
    print("✅ 通知已发送")
