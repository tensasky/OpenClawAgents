#!/usr/bin/env python3
"""
批量初始化所有股票历史数据
"""
import json
import sys
from pathlib import Path
import psycopg2

sys.path.insert(0, str(Path.home() / ".openclaw/agents/beifeng"))
from beifeng_pg import BeiFengAgent, Database

def import_stocks():
    """导入股票列表到数据库"""
    db = Database()
    
    # 读取股票列表
    stocks_file = Path.home() / ".openclaw/agents/beifeng/data/all_stocks.json"
    with open(stocks_file, 'r', encoding='utf-8') as f:
        stocks = json.load(f)
    
    print(f"📥 导入 {len(stocks)} 只股票到数据库...")
    
    for stock in stocks:
        db.insert_stock(stock['code'], stock['name'], stock['market'])
    
    print(f"✅ 导入完成")
    return [s['code'] for s in stocks]

def batch_fetch(stock_codes, batch_size=10):
    """批量抓取，每批10只"""
    total = len(stock_codes)
    
    for i in range(0, total, batch_size):
        batch = stock_codes[i:i+batch_size]
        print(f"\n🔄 [{i+1}/{total}] 抓取: {', '.join(batch)}")
        
        agent = BeiFengAgent()
        try:
            agent.run(batch, 'daily')
        except Exception as e:
            print(f"❌ 批次失败: {e}")
        
        import time
        time.sleep(1)  # 避免请求过快

if __name__ == '__main__':
    # 导入股票列表
    codes = import_stocks()
    
    # 批量抓取（先测试前20只）
    print(f"\n🚀 开始批量抓取前 20 只股票...")
    batch_fetch(codes[:20], batch_size=5)
    
    print(f"\n✅ 初始化完成！")
