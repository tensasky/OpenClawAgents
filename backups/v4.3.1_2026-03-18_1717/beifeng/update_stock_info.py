#!/usr/bin/env python3
"""
更新股票详细信息
从东方财富获取板块、行业、财务数据
"""

import sqlite3
import requests
import time
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("股票信息更新")

DB_PATH = Path(__file__).parent / "data" / "stocks_real.db"

def get_stock_basic(code: str) -> dict:
    """获取股票基本信息"""
    try:
        # 腾讯股票API
        url = f"https://qt.gtimg.cn/q={code}"
        resp = requests.get(url, timeout=3)
        
        if '~' in resp.text:
            parts = resp.text.split('~')
            return {
                'sector': parts[190] if len(parts) > 190 else '',  # 所属行业
                'industry': parts[190] if len(parts) > 190 else '',  # 行业
            }
    except:
        pass
    return {}


def update_all_stocks():
    """更新所有股票信息"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取所有股票
    cursor.execute('SELECT stock_code FROM master_stocks')
    stocks = [r[0] for r in cursor.fetchall()]
    
    log.info(f"开始更新 {len(stocks)} 只股票信息...")
    
    updated = 0
    for i, code in enumerate(stocks):
        info = get_stock_basic(code)
        
        if info:
            cursor.execute('''
                UPDATE master_stocks
                SET sector = ?, industry = ?, updated_at = datetime('now')
                WHERE stock_code = ?
            ''', (info.get('sector', ''), info.get('industry', ''), code))
            updated += 1
        
        if (i + 1) % 100 == 0:
            log.info(f"进度: {i+1}/{len(stocks)}")
        
        time.sleep(0.1)  # 避免请求过快
    
    conn.commit()
    conn.close()
    
    log.success(f"完成! 更新了 {updated} 只股票")
    return updated


if __name__ == '__main__':
    update_all_stocks()
