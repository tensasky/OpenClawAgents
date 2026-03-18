#!/usr/bin/env python3
"""
批量历史日线数据更新 - Baostock版
从1990-12-19开始，全量更新A股历史日线数据
"""

import sqlite3
import time
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("历史数据更新")

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
SAVE_INTERVAL = 50  # 每50只保存一次进度
REQUEST_DELAY = 0.5  # 每只间隔0.5秒

import baostock as bs

def get_stock_list():
    """获取股票列表"""
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily ORDER BY stock_code")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_stock(stock_code: str, start_date: str, end_date: str):
    """获取单只股票历史数据"""
    try:
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
            adjustflag="3"
        )
        
        if rs.error_code != '0':
            return False, 0
        
        # 保存数据
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        inserted = 0
        while (rs.error_code == '0') and rs.next():
            row = rs.get_row_data()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily 
                    (stock_code, timestamp, open, high, low, close, volume, amount, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock_code,
                    row[0],
                    float(row[1]) if row[1] else 0,
                    float(row[2]) if row[2] else 0,
                    float(row[3]) if row[3] else 0,
                    float(row[4]) if row[4] else 0,
                    int(float(row[5])) if row[5] else 0,
                    float(row[6]) if row[6] else 0,
                    'baostock'
                ))
                inserted += 1
            except:
                continue
        
        conn.commit()
        conn.close()
        
        return True, inserted
        
    except Exception as e:
        log.warning(f"{stock_code} 失败: {e}")
        return False, 0

def main():
    """主程序"""
    start_date = "1990-12-19"
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    log.step(f"开始批量历史数据更新: {start_date} ~ {end_date}")
    
    # 登录Baostock
    lg = bs.login()
    if lg.error_code != '0':
        log.error(f"Baostock登录失败: {lg.error_msg}")
        return
    
    log.success("Baostock登录成功")
    
    # 获取股票列表
    stocks = get_stock_list()
    total = len(stocks)
    
    log.info(f"总股票数: {total}")
    log.info(f"预计时间: {total * REQUEST_DELAY / 3600:.1f} 小时")
    
    # 检查已完成
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily WHERE source = 'baostock'")
    completed = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    log.info(f"已完成: {len(completed)}/{total}")
    
    # 过滤已完成的
    stocks_to_update = [s for s in stocks if s not in completed]
    
    # 开始更新
    success_count = 0
    fail_count = 0
    total_records = 0
    start_time = time.time()
    
    try:
        for i, stock in enumerate(stocks_to_update, 1):
            success, records = fetch_stock(stock, start_date, end_date)
            
            if success:
                success_count += 1
                total_records += records
            else:
                fail_count += 1
            
            # 打印进度
            if i % SAVE_INTERVAL == 0:
                elapsed = time.time() - start_time
                progress = i / len(stocks_to_update) * 100
                speed = i / elapsed if elapsed > 0 else 0
                eta = (len(stocks_to_update) - i) / speed if speed > 0 else 0
                
                log.info(f"进度: {i}/{len(stocks_to_update)} ({progress:.1f}%) | "
                        f"成功: {success_count} | 失败: {fail_count} | "
                        f"记录: {total_records:,} | "
                        f"ETA: {int(eta//3600)}小时{int(eta%3600//60)}分")
            
            time.sleep(REQUEST_DELAY)
            
    except KeyboardInterrupt:
        log.info("用户中断")
    finally:
        bs.logout()
    
    # 最终统计
    elapsed = time.time() - start_time
    log.success("历史数据更新完成!")
    log.info(f"总用时: {int(elapsed//3600)}小时{int(elapsed%3600//60)}分")
    log.info(f"成功: {success_count}")
    log.info(f"失败: {fail_count}")
    log.info(f"总记录: {total_records:,}")

if __name__ == '__main__':
    main()
