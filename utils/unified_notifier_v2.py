#!/usr/bin/env python3
"""统一通知系统 V2 - 分级优先级"""

import json
import requests
import sqlite3
import time
import threading
from datetime import datetime
from pathlib import Path
from enum import Enum

# 配置
DISCORD_WEBHOOKS = {
    'P0': 'https://discord.com/api/webhooks/1480218571211673605/xxx',  # alerts-p0
    'P1': 'https://discord.com/api/webhooks/1480218571211673605/xxx',  # signals-p1
    'P2': 'https://discord.com/api/webhooks/1480218571211673605/xxx',   # daily-reports
}

EMAIL_TO = ['tensasky2003@gmail.com']
ADMIN_EMAIL = 'tensasky2003@gmail.com'

class Priority(Enum):
    P0 = "P0"  # 系统故障 - 立即
    P1 = "P1"  # 交易信号 - 5分钟内
    P2 = "P2"  # 日报 - 收盘

class UnifiedNotifierV2:
    def __init__(self):
        self.notification_queue = []
        self.worker_thread = None
        self.running = True
        
        # 启动异步工作线程
        self.start_worker()
    
    def start_worker(self):
        """启动异步通知工作线程"""
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()
        print("✅ 通知工作线程已启动")
    
    def worker(self):
        """异步处理通知队列"""
        while self.running:
            if self.notification_queue:
                item = self.notification_queue.pop(0)
                self.process_notification(item)
            time.sleep(1)  # 每秒检查
    
    def process_notification(self, item):
        """处理通知"""
        priority = item['priority']
        title = item['title']
        message = item['message']
        
        if priority == Priority.P0:
            # P0: 立即发送
            self.send_discord(Priority.P0, title, message)
            self.send_email(ADMIN_EMAIL, f"[P0] {title}", message)
        
        elif priority == Priority.P1:
            # P1: Discord立即，邮件可选
            self.send_discord(Priority.P1, title, message)
        
        else:
            # P2: 加入待发送队列 (收盘后统一发送)
            self.buffer_daily_report(title, message)
    
    def send_discord(self, priority, title, message):
        """发送Discord"""
        webhook = DISCORD_WEBHOOKS.get(priority.value)
        if not webhook:
            return
        
        # Markdown格式
        if priority == Priority.P0:
            emoji = "🚨"
            channel = "#alerts-p0"
        elif priority == Priority.P1:
            emoji = "🀄"
            channel = "#signals-p1"
        else:
            emoji = "📊"
            channel = "#daily-reports"
        
        payload = {
            "content": f"{emoji} **{title}**\n{message}",
            "username": "OpenClaw"
        }
        
        try:
            r = requests.post(webhook, json=payload, timeout=5)
            if r.status_code == 204:
                print(f"✅ Discord {priority.value} 发送成功")
        except Exception as e:
            print(f"❌ Discord发送失败: {e}")
    
    def send_email(self, to, subject, body):
        """发送邮件 (简化版)"""
        print(f"📧 邮件发送: {subject}")
        # 实际使用Gmail SMTP
    
    def buffer_daily_report(self, title, message):
        """缓存日报"""
        self.notification_queue.append({
            'priority': Priority.P2,
            'title': title,
            'message': message,
            'type': 'report'
        })
    
    # ==================== API ====================
    
    def send_alert(self, priority, title, message):
        """发送告警 (主API)"""
        item = {
            'priority': priority if isinstance(priority, Priority) else Priority[priority],
            'title': title,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        # P0立即处理
        if item['priority'] == Priority.P0:
            self.process_notification(item)
        else:
            self.notification_queue.append(item)
    
    def send_signal(self, code, name, score, price, pct):
        """发送交易信号 (P1)"""
        message = f"""
**股票代码**: {code} ({name})
**评分**: {score} (满分100)
**价格**: ¥{price} ({pct:+.2f}%)
**时间**: {datetime.now().strftime('%H:%M:%S')}
"""
        self.send_alert(Priority.P1, f"交易信号 - {code}", message)
    
    def send_system_alert(self, title, message):
        """发送系统告警 (P0)"""
        self.send_alert(Priority.P0, title, message)
    
    def send_daily_report(self, profit, positions, signals):
        """发送日报 (P2)"""
        message = f"""
**日期**: {datetime.now().strftime('%Y-%m-%d')}

### 收益
- 今日盈亏: {profit:+.2f}%

### 持仓
{chr(10).join([f"- {p['code']}: ¥{p['value']}" for p in positions])}

### 信号
- 收到: {signals['total']}个
- 执行: {signals['executed']}个
- 失败: {signals['failed']}个
"""
        self.send_alert(Priority.P2, "每日报告", message)
    
    def heartbeat(self):
        """心跳 (防Dead Man's Snitch)"""
        self.send_alert(Priority.P2, "心跳", "系统正常运行")
    
    def stop(self):
        """停止"""
        self.running = False

# 全局实例
notifier = UnifiedNotifierV2()

if __name__ == "__main__":
    # 测试
    print("=== 测试分级通知 ===")
    
    # P0测试
    notifier.send_alert(Priority.P0, "系统故障", "数据库连接失败")
    
    # P1测试
    notifier.send_signal('sh600036', '招商银行', 75, 39.56, 0.39)
    
    # P2测试
    notifier.send_daily_report(2.5, [{'code': 'sh600036', 'value': 10000}], {'total': 5, 'executed': 3, 'failed': 2})
    
    print("\n✅ 通知测试完成")
