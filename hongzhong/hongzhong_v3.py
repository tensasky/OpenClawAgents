#!/usr/bin/env python3
"""
红中 V3.1 - 高频扫描系统
每30分钟扫描，支持保守版&平衡版
"""

import sqlite3
import json
import requests
import smtplib
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
HONGZHONG_DIR = Path(__file__).parent
DATA_DIR = HONGZHONG_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

SIGNALS_DB = DATA_DIR / "signals_v3.db"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# 邮件配置
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3823810468@qq.com"
SENDER_PASSWORD = "tmwhuqnthrpbcgec"
RECEIVER_EMAIL = "3823810468@qq.com"

class HongzhongV31:
    """红中V3.1"""
    
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                strategy TEXT NOT NULL,
                version TEXT NOT NULL,
                entry_price REAL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                score REAL,
                sent_discord INTEGER DEFAULT 0,
                UNIQUE(stock_code, timestamp, strategy, version)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def generate_mock_signals(self):
        """生成模拟信号（实际应调用南风引擎）"""
        signals = []
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 模拟保守版信号（高质量，少而精）
        if datetime.now().minute % 30 == 0:
            signals.append({
                'timestamp': now,
                'stock_code': 'sh600348',
                'stock_name': '华阳股份',
                'strategy': '趋势跟踪',
                'version': 'conservative',
                'entry_price': 10.27,
                'stop_loss': 10.06,
                'target_1': 10.89,
                'target_2': 11.50,
                'score': 9.2
            })
        
        # 模拟平衡版信号（更多机会）
        if datetime.now().minute % 15 == 0:
            signals.append({
                'timestamp': now,
                'stock_code': 'sz301667',
                'stock_name': '测试股份',
                'strategy': '突破策略',
                'version': 'balance',
                'entry_price': 25.50,
                'stop_loss': 24.86,
                'target_1': 27.03,
                'target_2': 28.56,
                'score': 8.3
            })
        
        return signals
    
    def save_signals(self, signals):
        """保存信号"""
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        saved = 0
        for sig in signals:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO signals 
                    (timestamp, stock_code, stock_name, strategy, version,
                     entry_price, stop_loss, target_1, target_2, score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    sig['timestamp'], sig['stock_code'], sig['stock_name'],
                    sig['strategy'], sig['version'], sig['entry_price'],
                    sig['stop_loss'], sig['target_1'], sig['target_2'], sig['score']
                ))
                if cursor.rowcount > 0:
                    saved += 1
            except Exception as e:
                print(f"保存失败: {e}")
        
        conn.commit()
        conn.close()
        return saved
    
    def send_discord(self, signals):
        """发送Discord通知"""
        for sig in signals:
            try:
                version_emoji = "🛡️" if sig['version'] == 'conservative' else "⚖️"
                
                content = f"""{version_emoji} **红中V3.1预警**

**版本**: {'保守版' if sig['version'] == 'conservative' else '平衡版'}
**策略**: {sig['strategy']}
**股票**: {sig['stock_code']} {sig['stock_name']}

💰 **操作建议**
入场价: ¥{sig['entry_price']:.2f}
止损价: ¥{sig['stop_loss']:.2f}
目标1: ¥{sig['target_1']:.2f}
目标2: ¥{sig['target_2']:.2f}

📊 **评分**: {sig['score']}
⏰ **时间**: {sig['timestamp']}
"""
                
                requests.post(
                    DISCORD_WEBHOOK,
                    json={"content": content},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
            except Exception as e:
                print(f"Discord发送失败: {e}")
    
    def send_email(self, signals):
        """发送邮件通知"""
        for sig in signals:
            try:
                msg = MIMEMultipart()
                msg['From'] = SENDER_EMAIL
                msg['To'] = RECEIVER_EMAIL
                msg['Subject'] = f"🀄 红中V3.1预警 - {sig['stock_code']} ({'保守版' if sig['version'] == 'conservative' else '平衡版'})"
                
                body = f"""
红中V3.1交易预警

版本: {'保守版' if sig['version'] == 'conservative' else '平衡版'}
策略: {sig['strategy']}
股票: {sig['stock_code']} {sig['stock_name'] or ''}
时间: {sig['timestamp']}

【操作建议】
入场价: ¥{sig['entry_price']:.2f}
止损价: ¥{sig['stop_loss']:.2f}
目标1: ¥{sig['target_1']:.2f}
目标2: ¥{sig['target_2']:.2f}

【评分】
综合分数: {sig['score']}

请及时查看并决策。

--
红中V3.1量化预警系统
"""
                
                msg.attach(MIMEText(body, 'plain', 'utf-8'))
                
                server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
                server.login(SENDER_EMAIL, SENDER_PASSWORD)
                server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
                server.quit()
                
                print(f"✅ 邮件已发送: {sig['stock_code']}")
                
            except Exception as e:
                print(f"❌ 邮件发送失败: {e}")
    
    def run(self):
        """运行扫描"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 🀄 红中V3.1扫描启动...")
        
        signals = self.generate_mock_signals()
        
        if signals:
            saved = self.save_signals(signals)
            print(f"✅ 发现 {len(signals)} 个信号，保存 {saved} 个")
            self.send_discord(signals)
            self.send_email(signals)
        else:
            print("⏳ 本次扫描无信号")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 扫描完成")


def main():
    hongzhong = HongzhongV31()
    hongzhong.run()


if __name__ == '__main__':
    main()
