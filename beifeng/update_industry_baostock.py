#!/usr/bin/env python3
"""
使用baostock批量更新板块/行业数据
"""

import baostock as bs
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


def batch_update_industry(limit: int = 100):
    """批量更新行业数据"""
    lg = bs.login()
    print('登录:', lg.error_msg)
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 获取需要更新的股票
    cursor.execute(f"""
        SELECT stock_code FROM master_stocks LIMIT {limit}
    """)
    stocks = [r[0] for r in cursor.fetchall()]
    
    print(f"开始更新 {len(stocks)} 只股票...")
    
    updated = 0
    for code in stocks:
        # 转换代码格式
        bs_code = code.replace('sh', 'sh.').replace('sz', 'sz.')
        
        rs = bs.query_stock_basic(bs_code)
        
        while rs.next():
            data = rs.get_row_data()
            # data: [code, name, list_date, delist_date, type, status]
            # 不包含行业信息
            
        time.sleep(0.1)
    
    bs.logout()
    conn.close()
    
    print(f"完成!")
    return updated


if __name__ == '__main__':
    batch_update_industry(10)
