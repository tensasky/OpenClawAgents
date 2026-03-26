#!/usr/bin/env python3
"""选股扫描 - 使用Baostock数据源"""

import baostock as bs
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

def get_market_data():
    """获取大盘数据"""
    lg = bs.login()
    rs = bs.query_history_k_data_plus("sh.000001", "date,close,pctChg", 
        start_date='2026-03-26', end_date='2026-03-26')
    market = {}
    while rs.error_code == '0' and rs.next():
        d = rs.get_row_data()
        market = {'close': d[1], 'pct': d[2]}
    bs.logout()
    return market

def get_stock_ma20_slope(stock_code):
    """获取MA20斜率"""
    lg = bs.login()
    rs = bs.query_history_k_data_plus(stock_code, "date,close", 
        start_date='2026-02-20', end_date='2026-03-26')
    
    prices = []
    while rs.error_code == '0' and rs.next():
        d = rs.get_row_data()
        if d[1]:
            prices.append(float(d[1]))
    
    bs.logout()
    
    if len(prices) < 25:
        return None
    
    prices = prices[::-1]  # 正序
    ma = pd.Series(prices).rolling(20).mean()
    
    if ma.iloc[-5] <= 0:
        return None
    
    return (ma.iloc[-1] - ma.iloc[-5]) / ma.iloc[-5]

def scan_stocks():
    """扫描股票"""
    lg = bs.login()
    
    # 获取沪深300成分股
    rs = bs.query_hs300_stocks()
    stocks = []
    while rs.error_code == '0' and rs.next():
        stocks.append(rs.get_row_data()[0])
    
    results = []
    
    for code in stocks[:100]:
        try:
            # 获取今日数据
            full_code = code.replace('.', '.')
            rs = bs.query_history_k_data_plus(full_code, "date,close,pctChg", 
                start_date='2026-03-26', end_date='2026-03-26')
            
            today_data = None
            while rs.error_code == '0' and rs.next():
                d = rs.get_row_data()
                today_data = {'close': float(d[1]), 'pct': float(d[2])}
            
            if not today_data or today_data['pct'] <= 0:
                continue
            
            # 获取MA20斜率
            slope = get_stock_ma20_slope(full_code)
            
            if slope and slope > 0.003:  # > 0.3%
                results.append({
                    'code': code,
                    'close': today_data['close'],
                    'pct': today_data['pct'],
                    'slope': slope * 100
                })
        except:
            continue
    
    bs.logout()
    results.sort(key=lambda x: x['slope'], reverse=True)
    return results

if __name__ == "__main__":
    print(f"=== Baostock选股扫描 {datetime.now().strftime('%Y-%m-%d %H:%M')} ===\n")
    
    # 大盘
    market = get_market_data()
    print(f"上证: {market.get('close', 'N/A')} ({market.get('pct', 0):+.2f}%)")
    
    # 扫描
    results = scan_stocks()
    
    print(f"\n找到 {len(results)} 只MA20斜率>0.3%且今日上涨的股票\n")
    print("代码 | 收盘价 | 涨幅 | MA20斜率")
    print("-" * 45)
    for r in results[:20]:
        print(f"{r['code']} | ¥{r['close']:.2f} | {r['pct']:+.2f}% | {r['slope']:.2f}%")
    
    # 发邮件
    body = f"选股结果 (Baostock数据源)\n"
    body += f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    body += f"上证: {market.get('close', 'N/A')} ({market.get('pct', 0):+.2f}%)\n\n"
    body += "代码 | 收盘价 | 涨幅 | MA20斜率\n"
    body += "-" * 45 + "\n"
    for r in results:
        body += f"{r['code']} | ¥{r['close']:.2f} | {r['pct']:+.2f}% | {r['slope']:.2f}%\n"
    
    msg = MIMEText(body, 'plain', 'utf-8')
    msg['Subject'] = f'Baostock选股结果 {datetime.now().strftime("%m-%d")}'
    msg['From'] = 'tensasky2003@gmail.com'
    msg['To'] = 'tensasky2003@gmail.com,rcheng2@lululemon.com'
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login('tensasky2003@gmail.com', 'cqcm tbkh skyh auyf')
    server.send_message(msg)
    server.quit()
    
    print(f"\n✅ 邮件已发送")
