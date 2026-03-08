#!/usr/bin/env python3
"""
北风 - 获取全部 A 股列表 (备用方案)
使用腾讯财经批量接口
"""

import requests
import json
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/agents/beifeng"

def fetch_all_stocks():
    """获取全部 A 股"""
    
    print("🌪️ 正在获取全部 A 股列表...")
    
    all_stocks = []
    
    # 上海 A 股: 600000-609999
    print("  生成上海 A 股代码...")
    for i in range(600000, 610000):
        all_stocks.append({'code': f'sh{i}', 'name': '', 'market': 'SH'})
    
    # 上海科创板: 688xxx
    for i in range(688000, 689000):
        all_stocks.append({'code': f'sh{i}', 'name': '', 'market': 'SH'})
    
    # 深圳主板: 000000-009999
    print("  生成深圳主板代码...")
    for i in range(1, 10000):
        all_stocks.append({'code': f'sz{i:06d}', 'name': '', 'market': 'SZ'})
    
    # 深圳中小板: 002000-002999
    print("  生成深圳中小板代码...")
    for i in range(2000, 3000):
        all_stocks.append({'code': f'sz{i:06d}', 'name': '', 'market': 'SZ'})
    
    # 深圳创业板: 300000-301999
    print("  生成深圳创业板代码...")
    for i in range(300000, 302000):
        all_stocks.append({'code': f'sz{i:06d}', 'name': '', 'market': 'SZ'})
    
    # 北京交易所: 430000-899999 (部分)
    print("  生成北交所代码...")
    for i in range(430000, 440000):
        all_stocks.append({'code': f'bj{i}', 'name': '', 'market': 'BJ'})
    for i in range(830000, 840000):
        all_stocks.append({'code': f'bj{i}', 'name': '', 'market': 'BJ'})
    
    print(f"\n📊 生成代码总数: {len(all_stocks)} 个")
    print("⚠️  注意: 这是全量代码列表，实际有效股票约 5000+ 只")
    print("💡 建议: 首次运行时用实际查询验证有效性")
    
    return all_stocks

def save_stocks(stocks):
    """保存到文件"""
    output_file = WORKSPACE / "data" / "all_stocks_full.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存到 {output_file}")
    print(f"   共 {len(stocks)} 个代码")

if __name__ == '__main__':
    stocks = fetch_all_stocks()
    save_stocks(stocks)
    
    print(f"\n前10个代码示例:")
    for s in stocks[:10]:
        print(f"  {s['code']}")
