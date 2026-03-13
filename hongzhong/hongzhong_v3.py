#!/usr/bin/env python3
"""
红中 V3.0 - 高频扫描版
每15分钟扫描一次，支持保守版&平衡版双版本
发送Discord+邮件通知，持久化存储
"""

import os
import sys
import json
import sqlite3
import requests
import smtplib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Optional

# 配置路径
HONGZHONG_DIR = Path(__file__).parent
DATA_DIR = HONGZHONG_DIR / "data"
LOG_DIR = HONGZHONG_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 数据库路径
SIGNALS_DB = DATA_DIR / "signals_v3.db"

# Discord配置
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# 邮件配置
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "3823810468@qq.com"
SENDER_PASSWORD = "fhmozvhlbqzldjhg"
RECEIVER_EMAIL = "3823810468@qq.com"

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"hongzhong_v3_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("红中V3")


class SignalDatabase:
    """信号数据库"""
    
    def __init__(self):
        self.db_path = SIGNALS_DB
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                strategy TEXT NOT NULL,
                version TEXT NOT NULL,  -- conservative/balance
                entry_price REAL,
                stop_loss REAL,
                target_1 REAL,
                target_2 REAL,
                target_3 REAL,
                position_size TEXT,
                score REAL,
                adx REAL,
                rsi REAL,
                volume_ratio REAL,
                sector TEXT,
                is_hot_sector INTEGER,
                sent_discord INTEGER DEFAULT 0,
                sent_email INTEGER DEFAULT 0,
                UNIQUE(stock_code, timestamp, strategy, version)
            )
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signals_time 
            ON signals(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_signals_stock 
            ON signals(stock_code)
        ''')
        
        conn.commit()
        conn.close()
        logger.info("信号数据库初始化完成")
    
    def save_signal(self, signal: Dict) -> bool:
        """保存信号到数据库"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO signals 
                (timestamp, stock_code, stock_name, strategy, version,
                 entry_price, stop_loss, target_1, target_2, target_3,
                 position_size, score, adx, rsi, volume_ratio, sector, is_hot_sector)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal['timestamp'],
                signal['stock_code'],
                signal.get('stock_name', ''),
                signal['strategy'],
                signal['version'],
                signal['entry_price'],
                signal['stop_loss'],
                signal['target_1'],
                signal['target_2'],
                signal['target_3'],
                signal['position_size'],
                signal.get('score', 0),
                signal.get('adx', 0),
                signal.get('rsi', 0),
                signal.get('volume_ratio', 0),
                signal.get('sector', ''),
                1 if signal.get('is_hot_sector', False) else 0
            ))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            logger.error(f"保存信号失败: {e}")
            return False
    
    def get_today_signals(self) -> List[Dict]:
        """获取今日所有信号"""
        conn = sqlite3.connect(self.db_path)
        today = datetime.now().strftime('%Y-%m-%d')
        
        df = pd.read_sql_query(f"""
            SELECT * FROM signals
            WHERE date(timestamp) = '{today}'
            ORDER BY timestamp DESC
        """, conn)
        
        conn.close()
        return df.to_dict('records')


class Notifier:
    """通知器"""
    
    @staticmethod
    def send_discord(signal: Dict) -> bool:
        """发送Discord通知"""
        try:
            version_emoji = "🛡️" if signal['version'] == 'conservative' else "⚖️"
            strategy_emoji = {
                '趋势跟踪': '📈',
                '均值回归': '🔄',
                '突破策略': '🚀',
                '稳健增长': '📊',
                '热点追击': '🔥'
            }.get(signal['strategy'], '📌')
            
            content = f"""{version_emoji} **红中V3预警** {strategy_emoji}

**版本**: {'保守版' if signal['version'] == 'conservative' else '平衡版'}
**策略**: {signal['strategy']}
**股票**: {signal['stock_code']} {signal.get('stock_name', '')}

💰 **操作建议**
入场价: ¥{signal['entry_price']:.2f}
止损价: ¥{signal['stop_loss']:.2f} ({((signal['stop_loss']/signal['entry_price']-1)*100):.1f}%)
目标1: ¥{signal['target_1']:.2f} (+{((signal['target_1']/signal['entry_price']-1)*100):.0f}%)
目标2: ¥{signal['target_2']:.2f} (+{((signal['target_2']/signal['entry_price']-1)*100):.0f}%)
建议仓位: {signal['position_size']}

📊 **技术指标**
分数: {signal.get('score', 'N/A')}
ADX: {signal.get('adx', 'N/A')}
RSI: {signal.get('rsi', 'N/A')}
量比: {signal.get('volume_ratio', 'N/A')}
板块: {signal.get('sector', 'N/A')} {'🔥' if signal.get('is_hot_sector') else ''}

⏰ **时间**: {signal['timestamp']}
"""
            
            response = requests.post(
                DISCORD_WEBHOOK,
                json={"content": content},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 204:
                logger.info(f"Discord通知已发送: {signal['stock_code']}")
                return True
            else:
                logger.error(f"Discord发送失败: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Discord通知异常: {e}")
            return False
    
    @staticmethod
    def send_email(signal: Dict) -> bool:
        """发送邮件通知"""
        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = RECEIVER_EMAIL
            msg['Subject'] = f"🀄 红中V3预警 - {signal['stock_code']} ({'保守版' if signal['version'] == 'conservative' else '平衡版'})"
            
            body = f"""
红中V3高频扫描预警

版本: {'保守版' if signal['version'] == 'conservative' else '平衡版'}
策略: {signal['strategy']}
股票: {signal['stock_code']} {signal.get('stock_name', '')}
时间: {signal['timestamp']}

【操作建议】
入场价: ¥{signal['entry_price']:.2f}
止损价: ¥{signal['stop_loss']:.2f}
目标1: ¥{signal['target_1']:.2f}
目标2: ¥{signal['target_2']:.2f}
建议仓位: {signal['position_size']}

【技术指标】
分数: {signal.get('score', 'N/A')}
ADX: {signal.get('adx', 'N/A')}
RSI: {signal.get('rsi', 'N/A')}
量比: {signal.get('volume_ratio', 'N/A')}
板块: {signal.get('sector', 'N/A')}

请及时查看并决策。

--
财神爷量化交易系统
"""
            
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, RECEIVER_EMAIL, msg.as_string())
            server.quit()
            
            logger.info(f"邮件通知已发送: {signal['stock_code']}")
            return True
            
        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False


class HongzhongV3:
    """红中V3主类"""
    
    def __init__(self):
        self.db = SignalDatabase()
        self.notifier = Notifier()
        self.scan_count = 0
        
    def scan_signals(self) -> List[Dict]:
        """扫描信号（模拟版，实际应调用南风引擎）"""
        signals = []
        
        # 这里应该调用南风V5.4引擎进行实际扫描
        # 现在模拟生成一些信号用于测试
        
        # 模拟保守版信号
        if datetime.now().minute % 30 == 0:  # 每30分钟可能产生保守版信号
            signals.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stock_code': 'sh600348',
                'stock_name': '华阳股份',
                'strategy': '趋势跟踪',
                'version': 'conservative',
                'entry_price': 10.27,
                'stop_loss': 10.06,
                'target_1': 10.89,
                'target_2': 11.50,
                'target_3': 12.32,
                'position_size': '20%',
                'score': 9.2,
                'adx': 42,
                'rsi': 58,
                'volume_ratio': 2.5,
                'sector': '煤炭',
                'is_hot_sector': True
            })
        
        # 模拟平衡版信号（更频繁）
        if datetime.now().minute % 15 == 0:
            signals.append({
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'stock_code': 'sz301667',
                'stock_name': '测试股份',
                'strategy': '突破策略',
                'version': 'balance',
                'entry_price': 25.50,
                'stop_loss': 24.86,
                'target_1': 27.03,
                'target_2': 28.56,
                'target_3': 30.60,
                'position_size': '15%',
                'score': 8.3,
                'adx': 35,
                'rsi': 62,
                'volume_ratio': 3.2,
                'sector': '科技',
                'is_hot_sector': True
            })
        
        return signals
    
    def process_signals(self, signals: List[Dict]):
        """处理信号"""
        for signal in signals:
            # 保存到数据库
            if self.db.save_signal(signal):
                logger.info(f"信号已保存: {signal['stock_code']} ({signal['version']})")
                
                # 发送Discord通知
                self.notifier.send_discord(signal)
                
                # 发送邮件通知
                self.notifier.send_email(signal)
    
    def run(self):
        """运行一次扫描"""
        self.scan_count += 1
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        logger.info(f"="*70)
        logger.info(f"🀄 红中V3第{self.scan_count}次扫描 - {now}")
        logger.info(f"="*70)
        
        # 扫描信号
        signals = self.scan_signals()
        
        if signals:
            logger.info(f"发现 {len(signals)} 个信号")
            self.process_signals(signals)
        else:
            logger.info("本次扫描未发现信号")
        
        logger.info(f"扫描完成，等待下次...")


def main():
    """主程序"""
    print("="*70)
    print("🀄 红中V3.0 - 高频扫描系统")
    print("="*70)
    print("扫描间隔: 15分钟")
    print("支持版本: 保守版 + 平衡版")
    print("通知方式: Discord + 邮件")
    print("持久化: SQLite数据库 + 日志文件")
    print("="*70)
    
    hongzhong = HongzhongV3()
    hongzhong.run()


if __name__ == '__main__':
    import pandas as pd  # 需要导入pandas
    main()
