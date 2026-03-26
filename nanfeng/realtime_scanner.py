#!/usr/bin/env python3
"""实时选股扫描 - 完全使用实时API数据"""

import urllib.request
import sqlite3
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def get_realtime_data(code):
    """从腾讯API获取实时数据"""
    try:
        url = f'https://qt.gtimg.cn/q={code}'
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=3) as r:
            parts = r.read().decode('gbk').split('~')
            return {
                'price': float(parts[3]),
                'pct': float(parts[5]) / 100 if parts[5] else 0,
                'name': parts[2],
                'open': float(parts[5]),  # 涨跌幅
                'high': float(parts[33]),
                'low': float(parts[34])
            }
    except:
        return None

def get_historical_prices(code, days=30):
    """从数据库获取历史收盘价"""
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(f"""
        SELECT timestamp, close FROM daily 
        WHERE stock_code='{code}' AND timestamp < '2026-03-26'
        ORDER BY timestamp DESC LIMIT {days}
    """, conn)
    conn.close()
    return df['close'].tolist() if len(df) > 0 else []

def calculate_ma_slope(prices):
    """计算MA20斜率"""
    if len(prices) < 25:
        return None
    prices = prices[:25]  # 最近25天
    ma = pd.Series(prices).rolling(20).mean()
    if pd.isna(ma.iloc[-5]) or ma.iloc[-5] == 0:
        return None
    return (ma.iloc[-1] - ma.iloc[-5]) / ma.iloc[-5]

def scan():
    """扫描并返回实时数据"""
    # 从数据库获取股票列表
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily WHERE timestamp >= '2026-02-01'")
    stocks = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    results = []
    
    for code in stocks[:500]:  # 扫描前500只
        # 获取实时数据
        rt = get_realtime_data(code)
        if not rt or rt['price'] <= 0:
            continue
        
        # 获取历史数据计算MA20斜率
        hist = get_historical_prices(code)
        if len(hist) < 25:
            continue
        
        # 加入今天的收盘价（用当前价）
        hist_with_today = [rt['price']] + hist
        
        slope = calculate_ma_slope(hist_with_today)
        
        # 筛选: MA20向上且今日上涨
        if slope and slope > 0.003 and rt['pct'] > 0:
            results.append({
                'code': code,
                'name': rt['name'],
                'price': rt['price'],
                'pct': rt['pct'],
                'slope': slope * 100
            })
        
        if len(results) >= 50:
            break
    
    results.sort(key=lambda x: (x['slope'], x['pct']), reverse=True)
    return results

if __name__ == "__main__":
    print(f"=== 实时选股扫描 {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    
    results = scan()
    
    print(f"找到 {len(results)} 只符合条件的股票\n")
    print("代码 | 名称 | 价格 | 涨幅 | MA20斜率")
    print("-" * 60)
    for r in results[:20]:
        print(f"{r['code']} | {r['name'][:8]} | ¥{r['price']:.2f} | {r['pct']:+.2f}% | {r['slope']:.2f}%")
    
    # 发送邮件
    body = f"实时选股结果 (MA20斜率>0.3% 且今日上涨)\n"
    body += f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    body += f"数据来源: 腾讯实时API\n\n"
    body += "代码 | 名称 | 价格 | 涨幅 | MA20斜率\n"
    body += "-" * 60 + "\n"
    for r in results:
        body += f"{r['code']} | {r['name'][:8]} | ¥{r['price']:.2f} | {r['pct']:+.2f}% | {r['slope']:.2f}%\n"
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'实时选股 {datetime.now().strftime("%m-%d %H:%M")}'
    msg['From'] = 'tensasky2003@gmail.com'
    msg['To'] = 'tensasky2003@gmail.com,rcheng2@lululemon.com'
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('tensasky2003@gmail.com', 'cqcm tbkh skyh auyf')
    server.send_message(msg)
    server.quit()
    
    print(f"\n✅ 邮件已发送")
