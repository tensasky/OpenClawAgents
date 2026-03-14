#!/usr/bin/env python3
"""
红中 V3.3 - 完整版（使用表格格式通知）
"""

import sqlite3
import requests
import smtplib
import sys
from datetime import datetime
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("红中")

# 导入表格格式
sys.path.insert(0, str(Path(__file__).parent))
from discord_table_format import DiscordTableFormat

# 配置
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3823810468@qq.com"
SENDER_PASSWORD = "tmwhuqnthrpbcgec"
RECEIVER_EMAIL = "3823810468@qq.com"

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HONGZHONG_DB = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

def get_stock_name(stock_code):
    """获取股票名称"""
    try:
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_name FROM stock_names WHERE stock_code = ?", (stock_code,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else stock_code
    except:
        return stock_code

def main():
    """主程序"""
    print("="*80)
    log.step("红中V3.3运行中")
    print("="*80)
    
    # 获取今日信号
    conn = sqlite3.connect(HONGZHONG_DB)
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor.execute(f"""
        SELECT * FROM signals 
        WHERE date(timestamp) = '{today}'
        ORDER BY stock_code
    """)
    
    columns = [description[0] for description in cursor.description]
    signals = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    
    # 分离保守和平衡
    conservative = [s for s in signals if s['version'] == 'conservative']
    balance = [s for s in signals if s['version'] == 'balance']
    
    log.info(f"保守策略: {len(conservative)} 个")
    log.info(f"平衡策略: {len(balance)} 个")
    
    # 生成Discord消息
    discord_msg = DiscordTableFormat.generate_full_message(conservative, balance)
    
    # 发送Discord
    log.step("发送Discord")
    try:
        requests.post(
            DISCORD_WEBHOOK,
            json={"content": discord_msg},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        log.success("Discord已发送")
    except Exception as e:
        log.fail(f"Discord失败: {e}")
    
    print("\n" + "="*80)

if __name__ == '__main__':
    main()
