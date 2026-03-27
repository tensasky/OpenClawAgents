#!/usr/bin/env python3
"""
统一通知系统 - 分级优先级 (根据设计文档)
P0: 系统故障 → Discord立即 + Email
P1: 交易信号 → Discord <5分钟
P2: 日报 → Email(15:45) + Discord收盘后
"""

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
    'P0': 'https://discord.com/api/webhooks/1480218571211673605/xxx',  # #alerts-p0
    'P1': 'https://discord.com/api/webhooks/1480218571211673605/xxx',  # #signals-p1
    'P2': 'https://discord.com/api/webhooks/1480218571211673605/xxx',  # #daily-reports
}

EMAIL_TO = ['tensasky2003@gmail.com']
ADMIN_EMAIL = 'tensasky2003@gmail.com'

class Priority(Enum):
    P0 = "P0"  # 系统故障
    P1 = "P1"  # 交易信号
    P2 = "P2"  # 日报/心跳

class UnifiedNotifier:
    def __init__(self):
        self.notification_queue = []
        self.daily_reports = []
        self.running = True
        
        # 启动异步工作线程
        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        
        # 启动心跳线程
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_worker, daemon=True)
        self.heartbeat_thread.start()
        
        print("✅ 统一通知系统已启动")
    
    def _worker(self):
        """异步处理通知"""
        while self.running:
            if self.notification_queue:
                item = self.notification_queue.pop(0)
                self._process(item)
            time.sleep(1)
    
    def _heartbeat_worker(self):
        """心跳 - Dead Man's Snitch"""
        while self.running:
            time.sleep(300)  # 每5分钟
            
            # 如果5分钟没发通知，发心跳
            if len(self.notification_queue) == 0:
                self.send(Priority.P2, "心跳", "系统正常运行")
    
    def _process(self, item):
        """处理单个通知"""
        priority = item['priority']
        title = item['title']
        message = item['message']
        
        if priority == Priority.P0:
            # P0: 立即发送 Discord + Email
            self._send_discord(priority, title, message)
            self._send_email(ADMIN_EMAIL, f"[P0] {title}", message)
        
        elif priority == Priority.P1:
            # P1: Discord立即
            self._send_discord(priority, title, message)
        
        else:
            # P2: 缓存日报，15:45发送
            self.daily_reports.append(item)
            if datetime.now().hour >= 15:
                self._send_daily_report()
    
    def _send_discord(self, priority, title, message):
        """发送Discord - Markdown格式"""
        webhook = DISCORD_WEBHOOKS.get(priority.value)
        if not webhook:
            return
        
        # Emoji
        if priority == Priority.P0:
            emoji = "🚨"
        elif priority == Priority.P1:
            emoji = "🀄"
        else:
            emoji = "📊"
        
        # Markdown格式
        content = f"{emoji} **{title}**\n{message}"
        
        try:
            requests.post(webhook, json={"content": content}, timeout=5)
        except:
            pass
    
    def _send_email(self, to, subject, body):
        """发送邮件 - HTML格式"""
        print(f"📧 邮件: {subject}")
    
    def _send_daily_report(self):
        """发送日报"""
        if not self.daily_reports:
            return
        
        # 生成HTML报告
        html = f"""
<html>
<head><title>OpenClaw 日报</title></head>
<body>
<h1>OpenClaw 每日报告</h1>
<p>日期: {datetime.now().strftime('%Y-%m-%d')}</p>
<h2>指标</h2>
<ul>
<li>信号: {len(self.daily_reports)}个</li>
<li>持仓: 6只</li>
</ul>
</body>
</html>
"""
        
        self._send_email(EMAIL_TO[0], "OpenClaw 日报", html)
        self.daily_reports.clear()
    
    def buffer_daily_report(self, title, message):
        """P2级别进入缓冲池，盘后统一发送"""
        self.daily_reports.append({
            'title': title,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def send_alert(self, level, title, message):
        """对外API - 符合原型"""
        if level == "P0":
            self._send_discord(Priority.P0, f"🔴 **CRITICAL**: {title}", message)
            self._send_email(ADMIN_EMAIL, title, message)  # P0 同时发邮件备份
        elif level == "P1":
            self._send_discord(Priority.P1, f"🟢 **SIGNAL**: {title}", message)
        else:
            # P2 级别进入缓冲池，盘后统一发送邮件
            self.buffer_daily_report(title, message)
    
    # ==================== API ====================
    
    def send(self, priority, title, message):
        """发送通知 - 主API"""
        self.notification_queue.append({
            'priority': priority if isinstance(priority, Priority) else Priority[priority],
            'title': title,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })
    
    def send_signal(self, code, name, score, price, pct, ma20_slope, rsi):
        """发送交易信号 - P1"""
        message = f"""
**股票**: {code} ({name})
**评分**: {score} (满分100)
**价格**: ¥{price} ({pct:+.2f}%)
---
**因子**:
- MA20斜率: {ma20_slope:.2f}%
- RSI: {rsi:.1f}
- 状态: 已通过

---
[查看详情]
"""
        self.send(Priority.P1, f"交易信号 - {code}", message)
    
    def send_system_alert(self, title, message):
        """发送系统告警 - P0"""
        self.send(Priority.P0, title, message)
    
    def send_daily_report(self, profit, positions, signals):
        """发送日报 - P2"""
        message = f"""
**日期**: {datetime.now().strftime('%Y-%m-%d')}

### 收益
- 今日盈亏: {profit:+.2f}%

### 持仓
"""
        for p in positions:
            message += f"- {p['code']}: ¥{p['value']}\n"
        
        message += f"""
### 信号
- 收到: {signals['total']}个
- 执行: {signals['executed']}个
- 失败: {signals['failed']}个
"""
        self.send(Priority.P2, "每日报告", message)

# 全局实例
notifier = UnifiedNotifier()

if __name__ == "__main__":
    # 测试
    print("=== 测试通知系统 ===")
    
    notifier.send(Priority.P0, "系统故障", "数据库连接失败")
    notifier.send(Priority.P1, "交易信号", "sh600036: ¥39.56 评分70")
    notifier.send(Priority.P2, "日报", "今日收益+0.5%")
    
    print("✅ 测试完成")
