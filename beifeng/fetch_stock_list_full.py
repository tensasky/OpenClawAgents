#!/usr/bin/env python3
"""
北风 - 获取全部 A 股列表
来源：腾讯财经 API
"""

import requests
import json
import re
from pathlib import Path

WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"

def fetch_all_stocks():
    """从腾讯财经获取全部 A 股"""
    
    # 腾讯财经提供所有股票列表
    url = "https://qt.gtimg.cn/q=sh000001"
    
    # 实际上我们需要用另一个接口获取全部列表
    # 使用东方财富的股票列表接口
    print("🌪️ 正在获取全部 A 股列表...")
    
    all_stocks = []
    
    # 上海 A 股 (sh6xxxxxx)
    print("  获取上海 A 股...")
    for page in range(1, 100):  # 足够多的页数
        url = f"http://31.push2.eastmoney.com/api/qt/clist/get?pn={page}&pz=500&po=1&np=1&fltt=2&invt=2&fid=f12&fs=m:0+t:6,m:0+t:13,m:0+t:80,m:1+t:2,m:1+t:23&fields=f12,f14"
        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
            
            if 'data' not in data or 'diff' not in data['data']:
                break
            
            stocks = data['data']['diff']
            if not stocks:
                break
            
            for stock in stocks:
                code = stock.get('f12', '')
                name = stock.get('f14', '')
                if code and name:
                    # 判断市场
                    if code.startswith('6'):
                        market = 'SH'
                        full_code = f'sh{code}'
                    elif code.startswith('0') or code.startswith('3'):
                        market = 'SZ'
                        full_code = f'sz{code}'
                    elif code.startswith('8') or code.startswith('4'):
                        market = 'BJ'
                        full_code = f'bj{code}'
                    else:
                        continue
                    
                    all_stocks.append({
                        'code': full_code,
                        'name': name,
                        'market': market
                    })
            
            print(f"    第 {page} 页: {len(stocks)} 只")
            
            if len(stocks) < 500:
                break
                
        except Exception as e:
            print(f"    第 {page} 页错误: {e}")
            break
    
    # 去重
    seen = set()
    unique_stocks = []
    for s in all_stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique_stocks.append(s)
    
    print(f"\n✅ 共获取 {len(unique_stocks)} 只 A 股")
    return unique_stocks

def save_stocks(stocks):
    """保存到文件"""
    output_file = WORKSPACE / "data" / "all_stocks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存到 {output_file}")

if __name__ == '__main__':
    stocks = fetch_all_stocks()
    save_stocks(stocks)
    
    # 显示前20只
    print(f"\n前20只股票:")
    for s in stocks[:20]:
        print(f"  {s['code']}: {s['name']}")
