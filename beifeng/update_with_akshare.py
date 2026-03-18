#!/usr/bin/env python3
"""
使用akshare批量更新股票基础数据
"""

import akshare as ak
import sqlite3
import time
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"


def update_with_akshare():
    """使用akshare更新数据"""
    print("获取A股列表...")
    df = ak.stock_info_a_code_name()
    
    print(f"获取到 {len(df)} 只股票")
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 批量更新
    updated = 0
    for _, row in df.iterrows():
        code = row['code']
        name = row['name']
        
        # 格式化代码
        if code.startswith('6'):
            full_code = f"sh{code}"
        else:
            full_code = f"sz{code}"
        
        try:
            cursor.execute("""
                UPDATE master_stocks
                SET stock_name = ?
                WHERE stock_code = ?
            """, (name, full_code))
            
            if cursor.rowcount > 0:
                updated += 1
            
        except Exception as e:
            pass
    
    conn.commit()
    conn.close()
    
    print(f"✅ 更新完成: {updated} 只股票")
    return updated


def get_industry_from_akshare(code: str) -> str:
    """从akshare获取行业"""
    try:
        # 东方财富行业分类
        df = ak.stock_board_industry_name_em()
        return df.to_string()[:100]
    except:
        return ""


if __name__ == '__main__':
    update_with_akshare()
