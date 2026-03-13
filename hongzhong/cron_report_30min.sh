#!/bin/bash
# 红中V3 - 每30分钟报告定时任务
# 交易时段: 9:30, 10:00, 10:30, 11:00, 11:30, 13:00, 13:30, 14:00, 14:30, 15:00

HONGZHONG_DIR="$HOME/Documents/OpenClawAgents/hongzhong"
LOG_FILE="$HONGZHONG_DIR/logs/cron_report.log"

mkdir -p "$HONGZHONG_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 红中V3报告任务启动..." >> "$LOG_FILE"

cd "$HONGZHONG_DIR"

# 生成并发送报告
python3 << 'EOF'
import sqlite3
import json
import requests
import smtplib
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
DATA_DIR = Path(__file__).parent / "data"
SIGNALS_DB = DATA_DIR / "signals_v3.db"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3823810468@qq.com"
SENDER_PASSWORD = "fhmozvhlbqzldjhg"
RECEIVER_EMAIL = "3823810468@qq.com"

def generate_report():
    """生成30分钟报告"""
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    
    # 读取今日信号
    conn = sqlite3.connect(SIGNALS_DB)
    cursor = conn.cursor()
    
    # 保守版信号
    cursor.execute("""
        SELECT * FROM signals 
        WHERE date(timestamp) = ? AND version = 'conservative'
        ORDER BY timestamp DESC
    """, (today,))
    conservative_signals = cursor.fetchall()
    
    # 平衡版信号
    cursor.execute("""
        SELECT * FROM signals 
        WHERE date(timestamp) = ? AND version = 'balance'
        ORDER BY timestamp DESC
    """, (today,))
    balance_signals = cursor.fetchall()
    
    conn.close()
    
    # 生成报告
    report = f"""🀄 **红中V3 - 交易时段报告** | {now.strftime('%H:%M')}

📊 **今日信号统计**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🛡️ **保守版**: {len(conservative_signals)} 个信号
⚖️ **平衡版**: {len(balance_signals)} 个信号
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
    
    # 保守版最新信号
    if conservative_signals:
        report += "🛡️ **保守版最新信号**\n\n"
        for sig in conservative_signals[:3]:
            report += f"• {sig[2]} {sig[3]} | {sig[4]} | 分数{sig[11]}\n"
        report += "\n"
    
    # 平衡版最新信号
    if balance_signals:
        report += "⚖️ **平衡版最新信号**\n\n"
        for sig in balance_signals[:3]:
            report += f"• {sig[2]} {sig[3]} | {sig[4]} | 分数{sig[11]}\n"
        report += "\n"
    
    report += f"""
💡 **操作建议**
• 收盘前30分钟(14:30)为最佳入场时机
• 严格按信号止损价设置条件单
• 到达目标分批止盈

⏰ **下次报告**: {(now.replace(minute=(now.minute//30+1)*30) if now.minute < 30 else now.replace(hour=now.hour+1, minute=0)).strftime('%H:%M')}
"""
    
    return report, len(conservative_signals), len(balance_signals)

def send_discord(report):
    """发送Discord"""
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": report},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"[{datetime.now()}] Discord报告已发送")
    except Exception as e:
        print(f"[{datetime.now()}] Discord发送失败: {e}")

def send_email(report, con_count, bal_count):
    """发送邮件"""
    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"🀄 红中V3报告 - {datetime.now().strftime('%H:%M')} | 保守{con_count} 平衡{bal_count}"
        
        msg.attach(MIMEText(report, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        
        print(f"[{datetime.now()}] 邮件报告已发送")
    except Exception as e:
        print(f"[{datetime.now()}] 邮件发送失败: {e}")

# 主程序
if __name__ == '__main__':
    report, con_count, bal_count = generate_report()
    print(report)
    
    send_discord(report)
    send_email(report, con_count, bal_count)
    
    # 保存报告到文件
    report_file = DATA_DIR / f"report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"报告已保存: {report_file}")
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
