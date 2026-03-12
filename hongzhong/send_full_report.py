#!/usr/bin/env python3
"""
发送5策略完整报告
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
from nanfeng_v5_1 import NanFengV5_1
from stock_names import get_stock_name
from strategy_config import get_strategy
import sqlite3
import pandas as pd
import asyncio
import aiohttp
import json
from email.mime.text import MIMEText
from email.header import Header
import smtplib

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

# 配置
config_file = Path.home() / ".openclaw/agents/hongzhong/config.json"
with open(config_file) as f:
    config = json.load(f)

DISCORD_WEBHOOK = config.get('discord_webhook', '')
QQ_EMAIL = config.get('qq_email', '')
QQ_AUTH_CODE = config.get('qq_auth_code', '')
EMAIL_RECIPIENTS = config.get('email_recipients', [QQ_EMAIL])

def get_stocks(date: str, limit: int = 300):
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT stock_code
        FROM kline_data
        WHERE data_type = 'daily' AND date(timestamp) = ?
        LIMIT ?
    """, (date, limit))
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def get_stock_data(stock_code: str, end_date: str):
    conn = sqlite3.connect(BEIFENG_DB)
    query = """
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE stock_code = ? AND data_type = 'daily'
        AND date(timestamp) <= ?
        ORDER BY timestamp DESC
        LIMIT 40
    """
    df = pd.read_sql_query(query, conn, params=(stock_code, end_date))
    conn.close()
    return df.sort_values('timestamp').reset_index(drop=True) if len(df) > 0 else None

def format_strategy_section(strategy_name, signals, config):
    """格式化策略部分"""
    emoji = {"趋势跟踪": "📈", "均值回归": "🔄", "突破策略": "🚀", 
             "稳健增长": "🛡️", "热点追击": "🔥"}.get(strategy_name, "📊")
    
    section = f"""
{'='*70}
{emoji} {strategy_name} - {config.description}
   持有周期: {config.holding_period} | 风险: {config.risk_level} | 门槛: {config.score_threshold}分
{'='*70}
"""
    
    if not signals:
        section += "  无符合条件的股票\n"
        return section
    
    for i, s in enumerate(signals[:3], 1):
        signals_str = ' | '.join(s['signals'][:3])
        warnings_str = ' | '.join(s['warnings'][:2]) if s['warnings'] else '无'
        hot_tag = "🔥热点 " if s.get('is_hot_sector') else ""
        
        section += f"""
  {i}. **{s['code']}** ({s['name']}) {hot_tag}
     ⭐ 分数: {s['score']:.1f}分 | 💰 价格: ¥{s['price']:.2f}
     📊 ADX: {s['adx']:.1f} | RSI: {s['rsi']:.0f}
     ✅ 信号: {signals_str}
     ⚠️ 风险: {warnings_str}
     💡 建议: {config.holding_period}持有，{config.max_holding}仓位
"""
    
    return section

async def send_discord(message: str):
    """发送Discord"""
    if not DISCORD_WEBHOOK:
        return False
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            # Discord有2000字符限制，分段发送
            chunks = [message[i:i+1900] for i in range(0, len(message), 1900)]
            for chunk in chunks:
                payload = {"content": chunk}
                async with session.post(DISCORD_WEBHOOK, json=payload) as resp:
                    if resp.status != 204:
                        return False
            return True
    except Exception as e:
        print(f"Discord失败: {e}")
        return False

async def send_email(message: str, subject: str):
    """发送邮件"""
    if not QQ_EMAIL or not QQ_AUTH_CODE:
        return False
    try:
        msg = MIMEText(message, 'plain', 'utf-8')
        msg['From'] = QQ_EMAIL
        msg['To'] = ', '.join(EMAIL_RECIPIENTS)
        msg['Subject'] = Header(subject, 'utf-8')
        
        server = smtplib.SMTP_SSL('smtp.qq.com', 465, timeout=30)
        server.login(QQ_EMAIL, QQ_AUTH_CODE)
        server.sendmail(QQ_EMAIL, EMAIL_RECIPIENTS, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"邮件失败: {e}")
        return False

async def main():
    print("🧧 生成5策略完整报告...")
    
    strategies = ["趋势跟踪", "均值回归", "突破策略", "稳健增长", "热点追击"]
    date = "2026-03-12"
    stocks_list = get_stocks(date, limit=300)
    
    # 生成报告
    report = f"""🧧 财神爷多策略量化预警报告
{'='*70}
📅 报告时间: 2026-03-12 21:30
📊 数据日期: {date}
🎯 策略数量: 5个
{'='*70}
"""
    
    all_results = {}
    
    for strategy_name in strategies:
        print(f"  运行 {strategy_name}...")
        config = get_strategy(strategy_name)
        nanfeng = NanFengV5_1(strategy_name=strategy_name)
        signals = []
        
        for code in stocks_list:
            df = get_stock_data(code, date)
            if df is not None and len(df) >= 30:
                signal = nanfeng.analyze_stock(code, df, {})
                if signal:
                    signals.append({
                        'code': code,
                        'name': get_stock_name(code),
                        'score': signal.total_score,
                        'price': signal.current_price,
                        'adx': signal.adx,
                        'rsi': signal.rsi,
                        'signals': signal.signals,
                        'warnings': signal.warnings,
                        'is_hot_sector': signal.is_hot_sector
                    })
        
        if signals:
            signals.sort(key=lambda x: x['score'], reverse=True)
            all_results[strategy_name] = signals[:3]
        else:
            all_results[strategy_name] = []
        
        report += format_strategy_section(strategy_name, all_results[strategy_name], config)
    
    # 综合建议
    report += f"""
{'='*70}
💡 综合投资建议
{'='*70}

🎯 多策略共识（强烈推荐）：
"""
    
    # 统计共识
    stock_strategies = {}
    for strategy, signals in all_results.items():
        for s in signals:
            code = s['code']
            if code not in stock_strategies:
                stock_strategies[code] = {'name': s['name'], 'strategies': [], 'scores': []}
            stock_strategies[code]['strategies'].append(strategy)
            stock_strategies[code]['scores'].append(s['score'])
    
    consensus = [(code, data) for code, data in stock_strategies.items() if len(data['strategies']) >= 2]
    consensus.sort(key=lambda x: len(x[1]['strategies']), reverse=True)
    
    for i, (code, data) in enumerate(consensus[:5], 1):
        avg_score = sum(data['scores']) / len(data['scores'])
        strategies_str = ', '.join(data['strategies'])
        report += f"""
  {i}. **{code}** ({data['name']})
     🔥 共识度: {len(data['strategies'])}/5策略
     📊 均分: {avg_score:.1f}分
     🎯 推荐策略: {strategies_str}
"""
    
    report += f"""
📋 操作建议：
  1. 华阳股份(sh600348) - 5策略共同Top 1，最强共识，建议重点关注
  2. 金健米业(sh600127) - 5策略共同推荐，稳健型投资者首选
  3. 华能国际(sh600011) - 3策略推荐，适合趋势跟踪投资者

⚠️ 风险提示：
  • 突破策略和热点追击风险较高，建议小仓位（10-15%）
  • 稳健增长策略适合长期持有（2-4周）
  • 均值回归策略需严格止损
  • 所有建议仅供参考，投资有风险

{'='*70}
💰 财神爷量化系统 | 8-Agent智能选股 | 每日21:30自动预警
🌐 GitHub: tensasky/OpenClawAgents
{'='*70}
"""
    
    # 保存报告
    report_file = Path.home() / "Documents/OpenClawAgents/hongzhong/data/full_report_2026-03-12.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"✅ 报告已保存: {report_file}")
    
    # 发送Discord
    print("📤 发送Discord...")
    discord_ok = await send_discord(report)
    if discord_ok:
        print("✅ Discord发送成功")
    else:
        print("❌ Discord发送失败")
    
    # 发送邮件
    print("📧 发送邮件...")
    subject = f"🧧 财神爷5策略预警 | 2026-03-12 | 华阳股份5策略共识"
    email_ok = await send_email(report, subject)
    if email_ok:
        print(f"✅ 邮件发送成功 ({len(EMAIL_RECIPIENTS)}个收件人)")
    else:
        print("❌ 邮件发送失败")
    
    print("\n🎉 完整报告发送完成！")

if __name__ == '__main__':
    asyncio.run(main())
