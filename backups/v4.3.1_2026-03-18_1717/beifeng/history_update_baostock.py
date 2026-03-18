#!/usr/bin/env python3
"""
历史数据更新方案 - 使用Baostock（免费稳定）
"""

import sqlite3
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("历史数据更新-Baostock")

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def get_stock_list():
    """获取股票列表"""
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily ORDER BY stock_code")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_with_baostock(stock_code: str, start_date: str, end_date: str):
    """使用Baostock获取数据"""
    try:
        import baostock as bs
        
        # 登录
        lg = bs.login()
        if lg.error_code != '0':
            log.error(f"Baostock登录失败: {lg.error_msg}")
            return False, 0
        
        # 转换代码格式
        if stock_code.startswith('sh'):
            bs_code = f"sh.{stock_code[2:]}"
        elif stock_code.startswith('sz'):
            bs_code = f"sz.{stock_code[2:]}"
        else:
            bs_code = stock_code
        
        # 获取数据
        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"  # 复权
        )
        
        if rs.error_code != '0':
            log.warning(f"{stock_code} 获取失败: {rs.error_msg}")
            bs.logout()
            return False, 0
        
        # 保存数据
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        inserted = 0
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily 
                    (stock_code, timestamp, open, high, low, close, volume, amount, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock_code,
                    row[0],  # date
                    float(row[1]) if row[1] else 0,  # open
                    float(row[2]) if row[2] else 0,  # high
                    float(row[3]) if row[3] else 0,  # low
                    float(row[4]) if row[4] else 0,  # close
                    int(float(row[5])) if row[5] else 0,  # volume
                    float(row[6]) if row[6] else 0,  # amount
                    'baostock'
                ))
                inserted += 1
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        bs.logout()
        
        return True, inserted
        
    except Exception as e:
        log.warning(f"{stock_code} 异常: {e}")
        return False, 0

def main():
    """主程序"""
    log.step("使用Baostock获取历史数据")
    
    # 检查baostock是否安装
    try:
        import baostock as bs
        log.success("Baostock已安装")
    except ImportError:
        log.error("Baostock未安装，请先安装: pip install baostock")
        return
    
    start_date = "1990-12-19"
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    stocks = get_stock_list()
    log.info(f"总股票数: {len(stocks)}")
    log.info(f"日期范围: {start_date} ~ {end_date}")
    
    # 测试第一只
    if stocks:
        log.info(f"测试获取第一只股票: {stocks[0]}")
        success, records = fetch_with_baostock(stocks[0], "2024-01-01", "2024-03-01")
        if success:
            log.success(f"测试成功! 获取到 {records} 条记录")
            log.info("可以开始全量更新")
        else:
            log.error("测试失败，请检查网络或Baostock服务")

if __name__ == '__main__':
    main()
