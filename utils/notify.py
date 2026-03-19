#!/usr/bin/env python3
"""
通知系统 - 统一通知模板
支持: Discord, Email, 终端
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from pathlib import Path
from datetime import datetime
from typing import List

# 配置文件（从hongzhong配置读取）
# 默认使用dongfeng的Discord webhook
DISCORD_WEBHOOK = os.environ.get('HONGZHONG_DISCORD_WEBHOOK', 
    'https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48')

# 尝试读取配置文件
CONFIG_PATH = Path.home() / "Documents/OpenClawAgents/hongzhong/config.yaml"
if CONFIG_PATH.exists():
    try:
        import yaml
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
        
        email_cfg = config.get('notification', {}).get('email', {})
        discord_cfg = config.get('notification', {}).get('discord', {})
        
        EMAIL_CONFIG = {
            'smtp_server': email_cfg.get('smtp_server', 'smtp.qq.com'),
            'smtp_port': email_cfg.get('smtp_port', 465),
            'sender': email_cfg.get('username', '3823810468@qq.com'),
            'password': 'yodqmyrlygqecgaj',
            'receivers': ['tensasky@gmail.com', 'rcheng2@lululemon.com', '3823810468@qq.com']
        }
        
        if not DISCORD_WEBHOOK:
            DISCORD_WEBHOOK = discord_cfg.get('webhook_url', '')
        
    except:
        EMAIL_CONFIG = {
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 465,
            'sender': '3823810468@qq.com',
            'password': 'yodqmyrlygqecgaj',
            'receivers': ['tensasky@gmail.com', 'rcheng2@lululemon.com', '3823810468@qq.com'],
            'sender_name': '财神爷'
        }
else:
    EMAIL_CONFIG = {
        'smtp_server': 'smtp.qq.com',
        'smtp_port': 465,
        'sender': '3823810468@qq.com',
        'password': 'yodqmyrlygqecgaj',
        'receivers': ['tensasky@gmail.com', 'rcheng2@lululemon.com', '3823810468@qq.com'],
            'sender_name': '财神爷'
    }


def send_discord(message: str, webhook: str = None) -> bool:
    """发送Discord通知"""
    import requests
    
    if not webhook:
        webhook = DISCORD_WEBHOOK
    
    if not webhook:
        return False
    
    try:
        data = {
            'content': message,
            'username': '发财交易助手'
        }
        requests.post(webhook, json=data, timeout=10)
        return True
    except Exception as e:
        print(f"Discord发送失败: {e}")
        return False


def send_email(subject: str, content: str, config: dict = None) -> bool:
    """发送邮件通知"""
    if not config:
        config = EMAIL_CONFIG
    
    if not config.get('password'):
        print("未配置邮件密码")
        return False
    
    try:
        msg = MIMEText(content, 'html', 'utf-8')
        msg['Subject'] = subject
        from email.header import Header
        sender_name = config.get('sender_name', '')
        sender_encoded = Header(sender_name, 'utf-8').encode() if sender_name else ''
        msg['From'] = f'{sender_encoded} <{config["sender"]}>' if sender_name else config['sender']
        msg['To'] = ', '.join(config['receivers'])
        
        server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
        server.starttls()
        server.login(config['sender'], config['password'])
        server.sendmail(config['sender'], config['receivers'], msg.as_string())
        server.quit()
        
        return True
    except Exception as e:
        print(f"邮件发送失败: {e}")
        return False


def notify_trade(action: str, stock_code: str, stock_name: str, 
                 price: float, quantity: int, reason: str = "",
                 config: dict = None):
    """
    发送交易通知
    
    Args:
        action: BUY/SELL
        stock_code: 股票代码
        stock_name: 股票名称
        price: 成交价格
        quantity: 成交数量
        reason: 交易原因
    """
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    emoji = "🟢" if action == "BUY" else "🔴"
    
    message = f"""
{emoji} **{action} 交易通知**
━━━━━━━━━━━━━━━━━━━━
时间: {timestamp}
股票: {stock_code} {stock_name}
价格: ¥{price:.2f}
数量: {quantity}股
金额: ¥{price * quantity:.2f}
原因: {reason}
━━━━━━━━━━━━━━━━━━━━
"""
    
    # 打印到终端
    print(message)
    
    # 发送Discord
    send_discord(message)
    
    # 发送邮件
    html_content = f"""
<h2>{emoji} {action} 交易通知</h2>
<p><b>时间:</b> {timestamp}</p>
<p><b>股票:</b> {stock_code} {stock_name}</p>
<p><b>价格:</b> ¥{price:.2f}</p>
<p><b>数量:</b> {quantity}股</p>
<p><b>金额:</b> ¥{price * quantity:.2f}</p>
<p><b>原因:</b> {reason}</p>
"""
    send_email(f"🎯 {action} {stock_code}", html_content, config)


def notify_alert(level: str, title: str, content: str):
    """发送告警通知"""
    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌"}.get(level, "ℹ️")
    
    message = f"{emoji} **{title}**\n{content}"
    print(message)
    send_discord(message)


if __name__ == '__main__':
    # 测试
    notify_trade("BUY", "sh600519", "贵州茅台", 1850.0, 100, "南风V5.1评分85分")


# ============ 表格通知格式 ============

def format_table_notification(signals: list, title: str = "📊 信号报告") -> str:
    """格式化表格通知"""
    if not signals:
        return "暂无信号"
    
    # 表头
    header = f"**{title}**\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    header += "代码     | 名称     | 价格   | 评分 | 策略\n"
    header += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    
    # 数据行
    rows = []
    for s in signals:
        code = s.get('stock_code', '')[:8]
        name = s.get('stock_name', '')[:8]
        price = s.get('entry_price', 0)
        score = s.get('score', 0)
        strategy = s.get('strategy', '')[:10]
        
        rows.append(f"{code:8} | {name:8} | ¥{price:5.2f} | {score:5.1f} | {strategy}")
    
    return header + "\n".join(rows) + "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"


def format_buy_notification(stock_code, stock_name, price, quantity, score, strategy) -> str:
    """买入通知表格格式"""
    return f"""
🟢 **买入信号**
━━━━━━━━━━━━━━━━━━━━
股票: {stock_code} {stock_name}
价格: ¥{price:.2f}
数量: {quantity}股
评分: {score}
策略: {strategy}
━━━━━━━━━━━━━━━━━━━━
"""


def format_sell_notification(stock_code, stock_name, price, quantity, profit_pct, reason) -> str:
    """卖出通知表格格式"""
    return f"""
🔴 **卖出信号**
━━━━━━━━━━━━━━━━━━━━
股票: {stock_code} {stock_name}
价格: ¥{price:.2f}
数量: {quantity}股
盈亏: {profit_pct:+.2f}%
原因: {reason}
━━━━━━━━━━━━━━━━━━━━
"""


# ============ 股票详细信息 ============

def get_stock_detail(code: str) -> dict:
    """获取股票详细信息"""
    import sqlite3
    from pathlib import Path
    
    DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
    
    try:
        conn = sqlite3.connect(str(DB))
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT stock_code, stock_name, market, sector, industry,
                   total_shares, float_shares, company_name
            FROM master_stocks
            WHERE stock_code = ?
        ''', (code,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'code': row[0],
                'name': row[1],
                'market': row[2],
                'sector': row[3] or '未知',
                'industry': row[4] or '未知',
                'total_shares': row[5],
                'float_shares': row[6],
                'company': row[7]
            }
    except:
        pass
    
    return {}


def format_stock_detail(code: str) -> str:
    """格式化股票详细信息"""
    info = get_stock_detail(code)
    
    if not info:
        return "暂无详细信息"
    
    lines = [
        f"🏢 公司: {info.get('company', '未知')}",
        f"📊 板块: {info.get('sector', '未知')}",
        f"🏭 行业: {info.get('industry', '未知')}",
    ]
    
    if info.get('total_shares'):
        total = info['total_shares'] / 1e8  # 亿股
        float_ = info.get('float_shares', 0) / 1e8
        lines.append(f"📈 总股本: {total:.2f}亿  流通: {float_:.2f}亿")
    
    return "\n".join(lines)


def format_signal_with_detail(code: str, name: str, price: float, score: float, strategy: str) -> str:
    """格式化信号详情（带板块和财务）"""
    detail = format_stock_detail(code)
    
    return f"""
📊 **交易信号**
━━━━━━━━━━━━━━━━━━━━
股票: {code} {name}
价格: ¥{price:.2f}
评分: {score:.1f}
策略: {strategy}

{detail}
━━━━━━━━━━━━━━━━━━━━
"""


def get_financial_data(code: str) -> dict:
    """获取财务数据"""
    import requests
    
    try:
        # 东方财富财务指标API
        secid = f"1.{code[2:]}" if code.startswith('sh') else f"0.{code[2:]}"
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/FinanceAnalysis/GetMainFinanceAjax?code={secid}&"
        
        resp = requests.get(url, timeout=5)
        data = resp.json()
        
        if data.get('data'):
            d = data['data']
            return {
                'revenue': d.get('totalRevenue'),  # 营业收入
                'profit': d.get('netProfit'),  # 净利润
                'assets': d.get('totalAssets'),  # 总资产
                'debt': d.get('totalLiab'),  # 总负债
                'roe': d.get('roe'),  # ROE
                'gross_margin': d.get('grossProfitMargin'),  # 毛利率
            }
    except:
        pass
    
    return {}


def format_financial_report(code: str) -> str:
    """格式化财务报告"""
    data = get_financial_data(code)
    
    if not data:
        return "暂无财务数据"
    
    lines = ["📈 财务数据:"]
    
    if data.get('revenue'):
        lines.append(f"  营收: {data['revenue']/1e8:.2f}亿")
    if data.get('profit'):
        lines.append(f"  净利润: {data['profit']/1e8:.2f}亿")
    if data.get('roe'):
        lines.append(f"  ROE: {data['roe']:.2f}%")
    if data.get('gross_margin'):
        lines.append(f"  毛利率: {data['gross_margin']:.2f}%")
    
    return "\n".join(lines)


def format_enhanced_notification(code: str, name: str, price: float, 
                                score: float, strategy: str, 
                                reason: str = "") -> str:
    """增强版通知 - 包含板块和财务信息"""
    import requests
    
    # 获取实时数据
    try:
        resp = requests.get(f'https://qt.gtimg.cn/q={code}', timeout=3)
        if '~' in resp.text:
            parts = resp.text.split('~')
            current_price = float(parts[3]) if parts[3] else price
            change = parts[31] or '0'
            change_pct = parts[32] or '0'
            volume = int(parts[36]) if parts[36] else 0
            amount = float(parts[37])/1e8 if parts[37] else 0  # 亿
            market_cap = float(parts[45]) if parts[45] else 0  # 亿
            float_cap = float(parts[46]) if parts[46] else 0  # 亿
            
            detail = f"""
📊 **{code} {name}**
━━━━━━━━━━━━━━━━━━━━
💰 价格: ¥{current_price:.2f} ({change:+}{change_pct}%)
📈 成交量: {volume/1e6:.1f}万手  成交额: {amount:.1f}亿
🏢 总市值: {market_cap:.1f}亿  流通: {float_cap:.1f}亿
🎯 评分: {score:.1f}  策略: {strategy}
📝 理由: {reason}
━━━━━━━━━━━━━━━━━━━━
"""
            return detail
    except:
        pass
    
    # Fallback
    return f"""
📊 **{code} {name}**
━━━━━━━━━━━━━━━━━━━━
💰 价格: ¥{price:.2f}
🎯 评分: {score:.1f}  策略: {strategy}
📝 理由: {reason}
━━━━━━━━━━━━━━━━━━━━
"""
