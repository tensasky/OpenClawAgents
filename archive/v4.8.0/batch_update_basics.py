#!/usr/bin/env python3
"""
批量补充股票基础数据 - 板块/行业/公司名
"""

import requests
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


def get_stock_info_from_eastmoney(code: str) -> dict:
    """从东方财富获取股票信息"""
    try:
        # 股票代码转换
        if code.startswith('sh'):
            secid = f"1.{code[2:]}"
        else:
            secid = f"0.{code[2:]}"
        
        url = f"https://emweb.securities.eastmoney.com/PC_HSF10/CompanySurvey/PageAjax?code={secid}"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
            'Referer': 'https://emweb.securities.eastmoney.com/'
        }
        
        resp = requests.get(url, headers=headers, timeout=5)
        data = resp.json()
        
        if data.get('data'):
            return {
                'sector': data['data'].get('sector', ''),      # 所属行业
                'industry': data['data'].get('industry', ''),   # 细分行业
                'company_name': data['data'].get('name', ''),   # 公司名称
                'business_scope': data['data'].get('scope', '') # 经营范围
            }
    except Exception as e:
        pass
    
    return {}


def batch_update(batch_size: int = 100):
    """批量更新"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 获取需要更新的股票
    cursor.execute("""
        SELECT stock_code, stock_name 
        FROM master_stocks 
        WHERE (sector IS NULL OR sector = '' OR sector IS NULL)
        LIMIT ?
    """, (batch_size,))
    
    stocks = cursor.fetchall()
    
    if not stocks:
        print("所有股票数据已完整!")
        conn.close()
        return 0
    
    print(f"开始更新 {len(stocks)} 只股票...")
    
    updated = 0
    for i, (code, name) in enumerate(stocks):
        info = get_stock_info_from_eastmoney(code)
        
        if info:
            cursor.execute("""
                UPDATE master_stocks
                SET sector = ?, industry = ?, company_name = ?, business_scope = ?
                WHERE stock_code = ?
            """, (
                info.get('sector', ''),
                info.get('industry', ''),
                info.get('company_name', ''),
                info.get('business_scope', ''),
                code
            ))
            updated += 1
        
        # 每50个提交一次
        if (i + 1) % 50 == 0:
            conn.commit()
            print(f"进度: {i+1}/{len(stocks)}")
        
        time.sleep(0.2)  # 避免请求过快
    
    conn.commit()
    conn.close()
    
    return updated


if __name__ == '__main__':
    import sys
    
    batch = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    
    print(f"批量更新: {batch}只/批")
    
    total = 0
    while True:
        updated = batch_update(batch)
        if updated == 0:
            break
        total += updated
        print(f"已更新 {total} 只")
    
    print(f"✅ 完成! 共更新 {total} 只股票")
