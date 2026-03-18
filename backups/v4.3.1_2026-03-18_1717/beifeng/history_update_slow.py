#!/usr/bin/env python3
"""
批量历史日线数据更新 - 单线程慢速版
避免请求过快导致被封
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
BATCH_SIZE = 50  # 每50只保存一次进度
REQUEST_DELAY = 3  # 每只股票间隔3秒

def get_stock_list():
    """获取股票列表"""
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily ORDER BY stock_code")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def fetch_single_stock(stock_code: str, start_date: str, end_date: str) -> tuple:
    """获取单只股票历史数据"""
    try:
        import akshare as ak
        
        # 提取代码
        symbol = stock_code[2:]  # 去掉sh/sz前缀
        
        # 获取历史数据
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace('-', ''),
            end_date=end_date.replace('-', ''),
            adjust="qfq"
        )
        
        if df.empty:
            return True, 0
        
        # 保存到数据库
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        inserted = 0
        for _, row in df.iterrows():
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO daily 
                    (stock_code, timestamp, open, high, low, close, volume, amount, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock_code,
                    row['日期'],
                    float(row['开盘']),
                    float(row['最高']),
                    float(row['最低']),
                    float(row['收盘']),
                    int(row['成交量']),
                    float(row['成交额']),
                    'akshare'
                ))
                inserted += 1
            except Exception as e:
                continue
        
        conn.commit()
        conn.close()
        
        return True, inserted
        
    except Exception as e:
        log.warning(f"{stock_code} 失败: {e}")
        return False, 0

def main():
    """主程序"""
    start_date = "1990-12-19"  # A股最早日期
    end_date = datetime.now().strftime('%Y-%m-%d')
    
    log.step(f"开始历史数据更新: {start_date} ~ {end_date}")
    
    # 获取股票列表
    stocks = get_stock_list()
    total = len(stocks)
    
    log.info(f"总股票数: {total}")
    log.info(f"预计时间: {total * REQUEST_DELAY / 3600:.1f} 小时")
    log.info(f"按 Ctrl+C 可随时停止，已保存的不会重复下载")
    
    # 检查是否已有进度
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT stock_code FROM daily WHERE source = 'akshare'")
    completed = set(row[0] for row in cursor.fetchall())
    conn.close()
    
    log.info(f"已完成: {len(completed)}/{total} 只")
    
    # 过滤已完成的
    stocks_to_update = [s for s in stocks if s not in completed]
    
    # 开始更新
    success_count = 0
    fail_count = 0
    total_records = 0
    start_time = time.time()
    
    for i, stock in enumerate(stocks_to_update, 1):
        try:
            success, records = fetch_single_stock(stock, start_date, end_date)
            
            if success:
                success_count += 1
                total_records += records
                log.info(f"✅ {stock}: {records}条记录")
            else:
                fail_count += 1
                log.warning(f"❌ {stock}: 获取失败")
            
            # 打印进度
            if i % 10 == 0:
                elapsed = time.time() - start_time
                progress = i / len(stocks_to_update) * 100
                speed = i / elapsed if elapsed > 0 else 0
                eta = (len(stocks_to_update) - i) / speed if speed > 0 else 0
                
                log.info(f"进度: {i}/{len(stocks_to_update)} ({progress:.1f}%) | "
                        f"成功: {success_count} | 失败: {fail_count} | "
                        f"ETA: {int(eta//3600)}小时{int(eta%3600//60)}分")
            
            # 请求间隔
            time.sleep(REQUEST_DELAY)
            
        except KeyboardInterrupt:
            log.info("用户中断，保存当前进度...")
            break
        except Exception as e:
            log.error(f"处理 {stock} 时出错: {e}")
            fail_count += 1
    
    # 最终统计
    elapsed = time.time() - start_time
    log.success("历史数据更新完成!")
    log.info(f"总用时: {int(elapsed//3600)}小时{int(elapsed%3600//60)}分")
    log.info(f"成功: {success_count}/{len(stocks_to_update)}")
    log.info(f"失败: {fail_count}")
    log.info(f"总记录: {total_records:,}")

if __name__ == '__main__':
    main()
