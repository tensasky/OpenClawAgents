#!/usr/bin/env python3
"""财神爷复盘系统 - 严谨版"""

import sqlite3
import baostock as bs
from datetime import datetime, timedelta

WORKDIR = "/Users/roberto/Documents/OpenClawAgents"

def get_market_data(days=5):
    """获取近几日数据"""
    lg = bs.login()
    
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    
    rs = bs.query_history_k_data_plus("sh.000001", 
        "date,close,pctChg,volume", 
        start_date=start_date, end_date=end_date)
    
    data = []
    while rs.error_code == '0' and rs.next():
        d = rs.get_row_data()
        data.append({
            'date': d[0],
            'close': float(d[1]) if d[1] else 0,
            'pct': float(d[2]) if d[2] else 0,
            'volume': float(d[3]) if d[3] else 0
        })
    
    bs.logout()
    return data

def analyze_market(data):
    """严谨分析市场"""
    if len(data) < 2:
        return "数据不足"
    
    today = data[-1]
    yesterday = data[-2]
    
    analysis = {
        'today_pct': today['pct'],
        'yesterday_pct': yesterday['pct'],
        'today_close': today['close'],
        'yesterday_close': yesterday['close'],
        'volume': today['volume'],
    }
    
    # 1. 计算实际反弹幅度
    if yesterday['pct'] < 0:
        rebound = abs(today['pct']) / abs(yesterday['pct']) if yesterday['pct'] != 0 else 0
        analysis['rebound_ratio'] = rebound
    else:
        analysis['rebound_ratio'] = None
    
    # 2. 连续涨跌分析
    consecutive = 0
    for d in reversed(data):
        if d['pct'] > 0:
            consecutive += 1
        else:
            break
    
    # 3. 均线位置 (简单计算20日均值)
    if len(data) >= 20:
        ma20 = sum([d['close'] for d in data[-20:]]) / 20
        analysis['ma20'] = ma20
        analysis['above_ma20'] = today['close'] > ma20
    else:
        analysis['ma20'] = None
        analysis['above_ma20'] = None
    
    return analysis

def get_conclusion(analysis):
    """基于事实的结论"""
    today_pct = analysis['today_pct']
    rebound_ratio = analysis.get('rebound_ratio')
    above_ma20 = analysis.get('above_ma20')
    
    conclusions = []
    
    # 1. 涨跌事实
    if today_pct > 0:
        conclusions.append(f"今日上涨 {today_pct:.2f}%")
    else:
        conclusions.append(f"今日下跌 {abs(today_pct):.2f}%")
    
    # 2. 反弹力度分析
    if rebound_ratio is not None:
        if rebound_ratio < 0.5:
            conclusions.append(f"昨日大跌{abs(analysis['yesterday_pct']):.1f}%，今日仅收复{int(rebound_ratio*100)}%，反弹力度弱")
        elif rebound_ratio < 1:
            conclusions.append(f"昨日大跌{abs(analysis['yesterday_pct']):.1f}%，今日收复{int(rebound_ratio*100)}%，反弹力度中等")
        elif rebound_ratio < 1.5:
            conclusions.append("昨日大跌，今日基本收复，反弹力度强")
        else:
            conclusions.append("昨日大跌，今日大幅反包，反转信号")
    
    # 3. 均线判断
    if above_ma20 is not None:
        if above_ma20:
            conclusions.append("股价位于20日均线上方")
        else:
            conclusions.append("股价位于20日均线下方，偏弱")
    
    # 4. 建议
    if rebound_ratio and rebound_ratio < 0.5:
       建议 = "⚠️ 建议观望，反弹力度不足"
    elif rebound_ratio and rebound_ratio < 1:
       建议 = "➡️ 建议谨慎，可小仓位试错"
    elif today_pct > 2:
       建议 = "👑 市场强势，可适度做多"
    else:
       建议 = "➡️ 建议观望为主"
    
    conclusions.append(f"\n结论: {建议}")
    
    return conclusions

def review():
    print(f"\n{'='*55}")
    print(f"📊 财神爷每日复盘 - {datetime.now().strftime('%Y-%m-%d')}")
    print(f"{'='*55}\n")
    
    # 大盘数据
    print("【1. 大盘数据】\n")
    data = get_market_data()
    for d in data[-5:]:
        print(f"  {d['date']}: 收盘{d['close']:.2f} 涨跌{d['pct']:+.2f}%")
    
    # 严谨分析
    print("\n【2. 市场分析】\n")
    analysis = analyze_market(data)
    conclusions = get_conclusion(analysis)
    for c in conclusions:
        print(f"  {c}")
    
    # 板块
    print("\n【3. 板块回顾】\n")
    try:
        conn = sqlite3.connect(f"{WORKDIR}/xifeng/data/xifeng.db")
        cur = conn.cursor()
        cur.execute("SELECT sector_name, change_pct FROM sectors ORDER BY change_pct DESC LIMIT 5")
        for row in cur.fetchall():
            print(f"  {row[0]}: {row[1]:+.1f}%")
        conn.close()
    except: pass
    
    # 信号
    print("\n【4. 今日信号】\n")
    try:
        conn = sqlite3.connect(f"{WORKDIR}/hongzhong/data/signals_v3.db")
        cur = conn.cursor()
        today = datetime.now().strftime('%Y-%m-%d')
        cur.execute("SELECT stock_code, stock_name, strategy FROM signals WHERE timestamp LIKE ? ORDER BY score DESC LIMIT 5", (today+'%',))
        rows = cur.fetchall()
        if rows:
            for r in rows:
                print(f"  {r[0]} {r[1]}: {r[2]}")
        else:
            print("  今日无信号")
        conn.close()
    except: pass
    
    print(f"\n{'='*55}")
    print("复盘完成!")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    review()
