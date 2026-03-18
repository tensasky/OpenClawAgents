#!/usr/bin/env python3
"""
北风历史数据补全脚本
补全A股自1990年以来的日线数据
"""

import sqlite3
import akshare as ak
import logging
from datetime import datetime, timedelta
from pathlib import Path
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("北风")


# 配置
DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/beifeng/logs"

LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"history_fill_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("北风历史补全")


def get_all_stocks():
    """获取所有股票代码"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code, name FROM stocks")
    stocks = cursor.fetchall()
    conn.close()
    return stocks


def get_stock_earliest_date(stock_code: str) -> str:
    """获取股票最早的数据日期"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT MIN(timestamp) FROM daily WHERE stock_code = ?
    """, (stock_code,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def fetch_history_data(stock_code: str, start_date: str, end_date: str):
    """使用akshare获取历史数据"""
    try:
        # 转换代码格式
        # sh600000 -> 600000
        # sz000001 -> 000001
        if stock_code.startswith('sh'):
            symbol = stock_code[2:]
        elif stock_code.startswith('sz'):
            symbol = stock_code[2:]
        else:
            symbol = stock_code
        
        # 获取历史数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date=start_date, end_date=end_date, adjust="qfq")
        
        if df is None or df.empty:
            return []
        
        records = []
        for _, row in df.iterrows():
            records.append({
                'timestamp': row['日期'] + ' 00:00:00',
                'open': float(row['开盘']),
                'high': float(row['最高']),
                'low': float(row['最低']),
                'close': float(row['收盘']),
                'volume': int(row['成交量']),
                'amount': float(row['成交额']) if '成交额' in row else 0
            })
        
        return records
    except Exception as e:
        logger.error(f"获取 {stock_code} 历史数据失败: {e}")
        return []


def save_history_data(stock_code: str, records: list):
    """保存历史数据到数据库"""
    if not records:
        return 0
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    inserted = 0
    for record in records:
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO kline_data 
                (stock_code, data_type, timestamp, open, high, low, close, volume, amount, source)
                VALUES (?, 'daily', ?, ?, ?, ?, ?, ?, ?, 'akshare_history')
            """, (
                stock_code,
                record['timestamp'],
                record['open'],
                record['high'],
                record['low'],
                record['close'],
                record['volume'],
                record['amount']
            ))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            logger.debug(f"插入数据失败: {e}")
    
    conn.commit()
    conn.close()
    return inserted


def fill_stock_history(stock_code: str, stock_name: str):
    """补全单只股票的历史数据"""
    logger.info(f"补全 {stock_code}({stock_name}) 历史数据...")
    
    # 获取最早的数据日期
    earliest = get_stock_earliest_date(stock_code)
    
    if earliest:
        # 已经有数据，从最早日期往前补
        earliest_date = datetime.strptime(earliest[:10], '%Y-%m-%d')
        if earliest_date.year <= 2010:
            logger.info(f"  {stock_code} 已有足够历史数据(到{earliest[:10]})，跳过")
            return 0
        end_date = (earliest_date - timedelta(days=1)).strftime('%Y%m%d')
    else:
        # 完全没有数据，补全到最新
        end_date = datetime.now().strftime('%Y%m%d')
    
    start_date = "19900101"  # A股开始时间
    
    logger.info(f"  获取 {start_date} 到 {end_date} 的数据...")
    
    records = fetch_history_data(stock_code, start_date, end_date)
    
    if records:
        inserted = save_history_data(stock_code, records)
        logger.info(f"  插入 {inserted} 条历史数据")
        return inserted
    else:
        logger.warning(f"  未获取到数据")
        return 0


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("北风历史数据补全开始")
    logger.info("=" * 60)
    
    stocks = get_all_stocks()
    logger.info(f"共有 {len(stocks)} 只股票需要处理")
    
    total_inserted = 0
    processed = 0
    
    for i, (code, name) in enumerate(stocks):
        try:
            inserted = fill_stock_history(code, name)
            total_inserted += inserted
            processed += 1
            
            if processed % 100 == 0:
                logger.info(f"进度: {processed}/{len(stocks)}，累计插入 {total_inserted} 条")
            
            # 限速，避免请求过快
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"处理 {code} 时出错: {e}")
            continue
    
    logger.info("=" * 60)
    logger.info(f"历史数据补全完成: 处理 {processed} 只股票，插入 {total_inserted} 条数据")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
