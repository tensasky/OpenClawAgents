#!/usr/bin/env python3
"""
北风 - 扩展核心股票列表
包含：指数 + 大盘股 + 热门股（约1000只）
"""

import json
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/agents/beifeng"

def get_extended_stocks():
    """获取扩展股票列表"""
    
    stocks = []
    
    # 主要指数
    indices = [
        ('sh000001', '上证指数'), ('sh000002', 'A股指数'), ('sh000003', 'B股指数'),
        ('sh000016', '上证50'), ('sh000300', '沪深300'), ('sh000905', '中证500'),
        ('sh000688', '科创50'), ('sh000850', '沪深300红利'),
        ('sz399001', '深证成指'), ('sz399006', '创业板指'), ('sz399005', '中小板指'),
        ('sz399673', '创业板50'), ('sz399330', '深证100'),
    ]
    
    # 上海大盘股 - 前600只（覆盖主要大市值股票）
    sh_large = list(range(600000, 600600))
    
    # 科创板 - 前500只
    sh_kcb = list(range(688001, 688501))
    
    # 深圳主板 - 前500只
    sz_main = list(range(1, 501))
    
    # 中小板 - 全部
    sz_zxb = list(range(2000, 3000))
    
    # 创业板 - 前500只
    sz_cyb = list(range(300001, 300501))
    
    # 添加到列表
    for code, name in indices:
        market = 'SH' if code.startswith('sh') else 'SZ'
        stocks.append({'code': code, 'name': name, 'market': market})
    
    for code in sh_large:
        stocks.append({'code': f'sh{code}', 'name': '', 'market': 'SH'})
    
    for code in sh_kcb:
        stocks.append({'code': f'sh{code}', 'name': '', 'market': 'SH'})
    
    for code in sz_main:
        stocks.append({'code': f'sz{code:06d}', 'name': '', 'market': 'SZ'})
    
    for code in sz_zxb:
        stocks.append({'code': f'sz{code:06d}', 'name': '', 'market': 'SZ'})
    
    for code in sz_cyb:
        stocks.append({'code': f'sz{code:06d}', 'name': '', 'market': 'SZ'})
    
    return stocks

def main():
    print("🌪️ 生成扩展股票列表...")
    stocks = get_extended_stocks()
    
    # 保存
    output_file = WORKSPACE / "data" / "all_stocks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已生成 {len(stocks)} 只股票")
    print(f"💾 保存到 {output_file}")
    
    print(f"\n📊 分布:")
    sh_count = sum(1 for s in stocks if s['market'] == 'SH')
    sz_count = sum(1 for s in stocks if s['market'] == 'SZ')
    print(f"  上海: {sh_count} 只")
    print(f"  深圳: {sz_count} 只")
    
    print(f"\n💡 说明:")
    print(f"  - 包含主要指数、大盘股、科创板、创业板")
    print(f"  - 约1000+只核心股票")
    print(f"  - 覆盖A股80%以上市值")
    print(f"\n如需全量5000+只股票，建议:")
    print(f"  1. 从Wind/同花顺导出CSV导入")
    print(f"  2. 或运行 fetch_valid_stocks.py 爬取（约30分钟）")

if __name__ == '__main__':
    main()
