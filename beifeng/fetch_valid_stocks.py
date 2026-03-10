#!/usr/bin/env python3
"""
北风 - 获取实时有效 A 股列表
使用腾讯财经批量接口验证
"""

import requests
import json
from pathlib import Path
from typing import List, Set

WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"

def verify_stock_batch(codes: List[str]) -> List[dict]:
    """验证一批股票代码是否有效"""
    if not codes:
        return []
    
    # 腾讯接口：最多 800 只一次
    codes_str = ','.join(codes)
    url = f"https://qt.gtimg.cn/q={codes_str}"
    
    try:
        resp = requests.get(url, timeout=30)
        resp.encoding = 'gb2312'
        
        valid_stocks = []
        lines = resp.text.strip().split(';')
        
        for line in lines:
            if not line.strip() or 'v_' not in line:
                continue
            
            # 解析返回数据
            # 格式: v_sh600000="1~浦发银行~600000~..."
            try:
                parts = line.split('="')
                if len(parts) < 2:
                    continue
                
                code_key = parts[0].replace('v_', '')
                data = parts[1].rstrip('"')
                
                if '~' in data:
                    fields = data.split('~')
                    if len(fields) >= 2:
                        name = fields[1]
                        if name and name != '':
                            valid_stocks.append({
                                'code': code_key,
                                'name': name,
                                'market': 'SH' if code_key.startswith('sh') else 'SZ' if code_key.startswith('sz') else 'BJ'
                            })
            except:
                continue
        
        return valid_stocks
        
    except Exception as e:
        print(f"  请求失败: {e}")
        return []

def fetch_all_valid_stocks():
    """获取全部有效 A 股"""
    
    print("🌪️ 正在获取全部有效 A 股...")
    print("  这会需要一些时间（约5-10分钟）...")
    
    all_valid = []
    batch_size = 500
    
    # 上海主板 (600000-609999)
    print("\n  扫描上海主板...")
    for prefix in ['600', '601', '602', '603', '605', '688']:
        print(f"    {prefix}xxx 段...")
        for start in range(0, 1000, batch_size):
            batch = [f"sh{prefix}{i:03d}" for i in range(start, min(start+batch_size, 1000))]
            valid = verify_stock_batch(batch)
            all_valid.extend(valid)
            if valid:
                print(f"      找到 {len(valid)} 只")
    
    # 深圳主板 (000000-009999)
    print("\n  扫描深圳主板...")
    for start in range(0, 10000, batch_size):
        batch = [f"sz{i:06d}" for i in range(start, min(start+batch_size, 10000))]
        valid = verify_stock_batch(batch)
        all_valid.extend(valid)
        if valid and start % 2000 == 0:
            print(f"    进度 {start}/10000, 累计 {len(all_valid)} 只")
    
    # 深圳中小板 (002000-002999)
    print("\n  扫描深圳中小板...")
    for start in range(2000, 3000, batch_size):
        batch = [f"sz{i:06d}" for i in range(start, min(start+batch_size, 3000))]
        valid = verify_stock_batch(batch)
        all_valid.extend(valid)
    
    # 深圳创业板 (300000-301999)
    print("\n  扫描深圳创业板...")
    for start in range(300000, 302000, batch_size):
        batch = [f"sz{i:06d}" for i in range(start, min(start+batch_size, 302000))]
        valid = verify_stock_batch(batch)
        all_valid.extend(valid)
    
    print(f"\n✅ 共找到 {len(all_valid)} 只有效 A 股")
    return all_valid

def main():
    stocks = fetch_all_valid_stocks()
    
    # 保存
    output_file = WORKSPACE / "data" / "all_stocks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 已保存到 {output_file}")
    
    # 统计
    sh_count = sum(1 for s in stocks if s['market'] == 'SH')
    sz_count = sum(1 for s in stocks if s['market'] == 'SZ')
    bj_count = sum(1 for s in stocks if s['market'] == 'BJ')
    
    print(f"\n📊 分布:")
    print(f"  上海: {sh_count} 只")
    print(f"  深圳: {sz_count} 只")
    print(f"  北京: {bj_count} 只")
    
    print(f"\n前20只:")
    for s in stocks[:20]:
        print(f"  {s['code']}: {s['name']}")

if __name__ == '__main__':
    main()
