#!/usr/bin/env python3
"""
北风 - 使用 akshare 获取全部 A 股列表
"""

import akshare as ak
import json
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/agents/beifeng"

def fetch_all_stocks():
    """使用 akshare 获取全部 A 股"""
    
    print("🌪️ 正在通过 akshare 获取全部 A 股...")
    
    # 获取上海 A 股
    print("  获取上海 A 股...")
    sh_stocks = ak.stock_sh_a_spot_em()
    print(f"    上海: {len(sh_stocks)} 只")
    
    # 获取深圳 A 股
    print("  获取深圳 A 股...")
    sz_stocks = ak.stock_sz_a_spot_em()
    print(f"    深圳: {len(sz_stocks)} 只")
    
    # 获取北京 A 股
    print("  获取北京 A 股...")
    try:
        bj_stocks = ak.stock_bj_a_spot_em()
        print(f"    北京: {len(bj_stocks)} 只")
    except:
        bj_stocks = None
        print("    北京: 0 只")
    
    all_stocks = []
    
    # 处理上海
    for _, row in sh_stocks.iterrows():
        code = str(row.get('代码', ''))
        name = str(row.get('名称', ''))
        if code and name:
            all_stocks.append({
                'code': f'sh{code}',
                'name': name,
                'market': 'SH'
            })
    
    # 处理深圳
    for _, row in sz_stocks.iterrows():
        code = str(row.get('代码', ''))
        name = str(row.get('名称', ''))
        if code and name:
            all_stocks.append({
                'code': f'sz{code}',
                'name': name,
                'market': 'SZ'
            })
    
    # 处理北京
    if bj_stocks is not None:
        for _, row in bj_stocks.iterrows():
            code = str(row.get('代码', ''))
            name = str(row.get('名称', ''))
            if code and name:
                all_stocks.append({
                    'code': f'bj{code}',
                    'name': name,
                    'market': 'BJ'
                })
    
    print(f"\n✅ 共获取 {len(all_stocks)} 只 A 股")
    return all_stocks

def save_stocks(stocks):
    """保存到文件"""
    output_file = WORKSPACE / "data" / "all_stocks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    print(f"💾 已保存到 {output_file}")

def main():
    stocks = fetch_all_stocks()
    save_stocks(stocks)
    
    # 显示统计
    sh_count = sum(1 for s in stocks if s['market'] == 'SH')
    sz_count = sum(1 for s in stocks if s['market'] == 'SZ')
    bj_count = sum(1 for s in stocks if s['market'] == 'BJ')
    
    print(f"\n📊 分布统计:")
    print(f"  上海: {sh_count} 只")
    print(f"  深圳: {sz_count} 只")
    print(f"  北京: {bj_count} 只")
    
    print(f"\n前20只股票:")
    for s in stocks[:20]:
        print(f"  {s['code']}: {s['name']}")

if __name__ == '__main__':
    main()
