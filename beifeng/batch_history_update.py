#!/usr/bin/env python3
"""
批量历史日线数据更新 - Batch Historical Data Update
从2021-03-10开始，全量更新A股历史日线数据
"""

import sqlite3
import requests
import time
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Tuple
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("历史数据更新")

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
BATCH_SIZE = 50  # 每批处理50只股票
MAX_WORKERS = 5  # 并发数
SAVE_INTERVAL = 100  # 每100只股票保存一次统计

class HistoricalDataUpdater:
    """历史数据更新器"""
    
    def __init__(self):
        self.stats = {
            'total_stocks': 0,
            'processed': 0,
            'success': 0,
            'failed': 0,
            'total_records': 0,
            'start_time': time.time()
        }
        self._lock = threading.Lock()
        self._last_save = 0
        
    def get_stock_list(self) -> List[str]:
        """获取股票列表（从daily表获取所有股票）"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        # 从daily表获取所有股票（因为stock_names表不完整）
        cursor.execute("SELECT DISTINCT stock_code FROM daily ORDER BY stock_code")
        stocks = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        log.info(f"获取到 {len(stocks)} 只股票")
        return stocks
    
    def fetch_history(self, stock_code: str, start_date: str, end_date: str) -> Tuple[bool, int]:
        """
        获取单只股票历史数据
        
        Returns:
            (是否成功, 新增记录数)
        """
        try:
            # 使用AKShare获取历史数据
            import akshare as ak
            
            # 转换股票代码格式
            if stock_code.startswith('sh'):
                symbol = stock_code[2:] + '.SH'
            elif stock_code.startswith('sz'):
                symbol = stock_code[2:] + '.SZ'
            else:
                symbol = stock_code
            
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code[2:],
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
                        row['开盘'],
                        row['最高'],
                        row['最低'],
                        row['收盘'],
                        row['成交量'],
                        row['成交额'],
                        'akshare'
                    ))
                    inserted += 1
                except Exception as e:
                    continue
            
            conn.commit()
            conn.close()
            
            return True, inserted
            
        except Exception as e:
            log.warning(f"获取 {stock_code} 历史数据失败: {e}")
            return False, 0
    
    def update_stock(self, stock_code: str, start_date: str, end_date: str) -> Tuple[bool, int]:
        """更新单只股票"""
        success, count = self.fetch_history(stock_code, start_date, end_date)
        
        with self._lock:
            self.stats['processed'] += 1
            if success:
                self.stats['success'] += 1
                self.stats['total_records'] += count
            else:
                self.stats['failed'] += 1
        
        return success, count
    
    def print_progress(self):
        """打印进度"""
        with self._lock:
            processed = self.stats['processed']
            total = self.stats['total_stocks']
            success = self.stats['success']
            failed = self.stats['failed']
            records = self.stats['total_records']
            elapsed = time.time() - self.stats['start_time']
            
            if processed > 0:
                avg_time = elapsed / processed
                eta = avg_time * (total - processed)
                progress = processed / total * 100
            else:
                avg_time = 0
                eta = 0
                progress = 0
            
            log.info(f"进度: {processed}/{total} ({progress:.1f}%) | "
                    f"成功: {success} | 失败: {failed} | "
                    f"记录: {records:,} | "
                    f"速度: {avg_time:.2f}s/只 | "
                    f"ETA: {int(eta//60)}分{int(eta%60)}秒")
    
    def run(self, start_date: str = "2021-03-10", end_date: str = None):
        """运行批量更新"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        log.step(f"开始批量历史数据更新: {start_date} ~ {end_date}")
        
        # 获取股票列表
        stocks = self.get_stock_list()
        self.stats['total_stocks'] = len(stocks)
        
        log.info(f"总共 {len(stocks)} 只股票需要更新")
        log.info(f"日期范围: {start_date} 至 {end_date}")
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(self.update_stock, stock, start_date, end_date): stock
                for stock in stocks
            }
            
            # 处理完成的任务
            for i, future in enumerate(as_completed(future_to_stock)):
                stock = future_to_stock[future]
                try:
                    success, count = future.result()
                except Exception as e:
                    log.error(f"处理 {stock} 时出错: {e}")
                
                # 定时打印进度（每SAVE_INTERVAL只）
                if (i + 1) % SAVE_INTERVAL == 0:
                    self.print_progress()
        
        # 最终统计
        self.print_progress()
        
        elapsed = time.time() - self.stats['start_time']
        log.success(f"批量更新完成！")
        log.info(f"总用时: {int(elapsed//60)}分{int(elapsed%60)}秒")
        log.info(f"成功: {self.stats['success']}/{self.stats['total_stocks']}")
        log.info(f"失败: {self.stats['failed']}")
        log.info(f"总记录: {self.stats['total_records']:,}")


if __name__ == '__main__':
    updater = HistoricalDataUpdater()
    
    # 从最早日期开始更新
    updater.run(
        start_date="2021-03-10",
        end_date=datetime.now().strftime('%Y-%m-%d')
    )
