#!/bin/bash
# 红中V3.1 - 收盘后总结报告
# 运行时间: 每日15:35

HONGZHONG_DIR="$HOME/Documents/OpenClawAgents/hongzhong"
LOG_FILE="$HONGZHONG_DIR/logs/close_report.log"

mkdir -p "$HONGZHONG_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 红中收盘总结启动..." >> "$LOG_FILE"

cd "$HONGZHONG_DIR"

# 生成收盘总结
python3 << 'EOF'
import sqlite3
import json
import requests
from datetime import datetime
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
RECEIVER_EMAIL = "3823810468@qq.com"

def generate_close_report():
    """生成收盘总结报告"""
    if not DB_PATH.exists():
        return "❌ 数据库不存在"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 今日信号统计
    cursor.execute(f"""
        SELECT 
            version,
            strategy,
            COUNT(*) as count,
            AVG(score) as avg_score,
            GROUP_CONCAT(stock_code, ', ') as stocks
        FROM signals 
        WHERE date(timestamp) = '{today}'
        GROUP BY version, strategy
        ORDER BY version, count DESC
    """)
    
    results = cursor.fetchall()
    
    # 总信号数
    cursor.execute(f"SELECT COUNT(*) FROM signals WHERE date(timestamp) = '{today}'")
    total_signals = cursor.fetchone()[0]
    
    # 最新信号
    cursor.execute(f"""
        SELECT stock_code, stock_name, strategy, version, entry_price, score
        FROM signals WHERE date(timestamp) = '{today}'
        ORDER BY timestamp DESC LIMIT 5
    """)
    latest = cursor.fetchall()
    
    conn.close()
    
    # 生成报告
    report = f"""🀄 **红中V3.1 - 收盘总结报告**
📅 {today} 15:35

📊 **今日信号总览**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总信号数: **{total_signals}** 个

"""
    
    # 按版本统计
    con_signals = [r for r in results if r[0] == 'conservative']
    bal_signals = [r for r in results if r[0] == 'balance']
    
    if con_signals:
        report += "🛡️ **保守版**\n"
        for _, strategy, count, avg_score, stocks in con_signals:
            report += f"  • {strategy}: {count}个 (均分{avg_score:.1f})\n"
        report += "\n"
    
    if bal_signals:
        report += "⚖️ **平衡版**\n"
        for _, strategy, count, avg_score, stocks in bal_signals:
            report += f"  • {strategy}: {count}个 (均分{avg_score:.1f})\n"
        report += "\n"
    
    if latest:
        report += "📈 **最新信号**\n"
        for code, name, strategy, version, price, score in latest[:3]:
            ver = "🛡️" if version == 'conservative' else "⚖️"
            report += f"  {ver} {code} {name or ''} | {strategy} | ¥{price} | {score}分\n"
        report += "\n"
    
    report += """━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 **明日操作建议**
• 09:30 关注开盘情况
• 09:45 西风板块分析更新
• 14:30 红中预警信号
• 14:50-15:00 执行交易

⏰ **下次收盘总结**: 明日15:35
"""
    
    return report

def send_discord(report):
    """发送Discord"""
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": report},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        print(f"[{datetime.now()}] Discord已发送")
    except Exception as e:
        print(f"Discord发送失败: {e}")

def send_email(report):
    """发送邮件"""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        SMTP_SERVER = "smtp.qq.com"
        SMTP_PORT = 465
        SENDER_EMAIL = "3823810468@qq.com"
        SENDER_PASSWORD = "fhmozvhlbqzldjhg"
        
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = RECEIVER_EMAIL
        msg['Subject'] = f"🀄 红中V3.1收盘总结 - {datetime.now().strftime('%Y-%m-%d')}"
        
        msg.attach(MIMEText(report, 'plain', 'utf-8'))
        
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
        server.quit()
        
        print(f"[{datetime.now()}] 邮件已发送")
    except Exception as e:
        print(f"邮件发送失败: {e}")

# 主程序
report = generate_close_report()
print(report)
send_discord(report)
send_email(report)

# 保存报告
report_file = Path.home() / f"Documents/OpenClawAgents/hongzhong/reports/close_report_{datetime.now().strftime('%Y%m%d')}.txt"
with open(report_file, 'w', encoding='utf-8') as f:
    f.write(report)

print(f"报告已保存: {report_file}")
EOF

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
