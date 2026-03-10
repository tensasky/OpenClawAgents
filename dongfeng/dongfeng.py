#!/usr/bin/env python3
"""
东风 - 股票初筛与池管理 Agent
从北风数据源筛选活跃股票，管理股票池
"""

import sqlite3
import json
import logging
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import sys

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "stock_pool.db"
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"dongfeng_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dongfeng")


class StockPoolManager:
    """股票池管理器"""
    
    def __init__(self):
        self.conn = None
        self.beifeng_conn = None
        self.init_db()
    
    def init_db(self):
        """初始化股票池数据库"""
        self.conn = sqlite3.connect(DB_PATH)
        cursor = self.conn.cursor()
        
        # 活跃股票池
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT UNIQUE NOT NULL,
                stock_name TEXT,
                entry_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                entry_price REAL,
                entry_amplitude REAL,
                entry_volume_ratio REAL,
                status TEXT DEFAULT 'ACTIVE',
                last_check_date TIMESTAMP,
                notes TEXT
            )
        """)
        
        # 备用股票池（曾经活跃但现在不活跃）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS backup_pool (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT NOT NULL,
                stock_name TEXT,
                entry_date TIMESTAMP,
                exit_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                exit_reason TEXT,
                days_in_pool INTEGER,
                max_amplitude REAL,
                avg_volume_ratio REAL,
                final_price REAL,
                notes TEXT
            )
        """)
        
        # 筛选历史记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scan_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_stocks INTEGER,
                active_found INTEGER,
                moved_to_backup INTEGER,
                params TEXT
            )
        """)
        
        self.conn.commit()
        logger.info("股票池数据库初始化完成")
    
    def connect_beifeng(self):
        """连接北风数据库"""
        if not BEIFENG_DB.exists():
            logger.error(f"北风数据库不存在: {BEIFENG_DB}")
            return False
        try:
            self.beifeng_conn = sqlite3.connect(BEIFENG_DB)
            return True
        except Exception as e:
            logger.error(f"连接北风数据库失败: {e}")
            return False
    
    def get_stock_kline(self, stock_code: str, days: int = 10) -> List[Dict]:
        """获取股票K线数据"""
        if not self.beifeng_conn:
            return []
        
        cursor = self.beifeng_conn.cursor()
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (stock_code, days))
        
        rows = cursor.fetchall()
        return [
            {
                'timestamp': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
                'amount': row[6]
            }
            for row in rows
        ]
    
    def calculate_amplitude(self, kline: List[Dict]) -> Optional[float]:
        """计算最新一天的振幅"""
        if len(kline) < 2:
            return None
        
        today = kline[0]
        yesterday = kline[1]
        
        if yesterday['close'] == 0:
            return None
        
        amplitude = (today['high'] - today['low']) / yesterday['close'] * 100
        return round(amplitude, 2)
    
    def calculate_volume_ratio(self, kline: List[Dict]) -> Optional[float]:
        """计算成交量比率（今日 vs 前5日均量）"""
        if len(kline) < 6:
            return None
        
        today_volume = kline[0]['volume']
        avg_volume = sum(day['volume'] for day in kline[1:6]) / 5
        
        if avg_volume == 0:
            return None
        
        ratio = (today_volume / avg_volume - 1) * 100
        return round(ratio, 2)
    
    def is_gentle_volume(self, ratio: float) -> bool:
        """判断是否温和放量（20%-100%）"""
        return 20 <= ratio <= 100
    
    def scan_stocks(self, min_amplitude: float = 3.0) -> Tuple[List[Dict], List[Dict]]:
        """
        扫描所有股票，筛选活跃股票
        返回: (新活跃股票列表, 应移出活跃池的股票列表)
        """
        if not self.connect_beifeng():
            return [], []
        
        cursor = self.beifeng_conn.cursor()
        cursor.execute("SELECT code, name FROM stocks")
        all_stocks = cursor.fetchall()
        
        new_active = []
        total_checked = 0
        
        logger.info(f"开始扫描 {len(all_stocks)} 只股票...")
        
        for stock_code, stock_name in all_stocks:
            total_checked += 1
            if total_checked % 100 == 0:
                logger.info(f"已检查 {total_checked}/{len(all_stocks)} 只股票")
            
            kline = self.get_stock_kline(stock_code, 10)
            if len(kline) < 6:
                continue
            
            amplitude = self.calculate_amplitude(kline)
            volume_ratio = self.calculate_volume_ratio(kline)
            
            if amplitude is None or volume_ratio is None:
                continue
            
            # 筛选条件：振幅>3% 且 温和放量
            if amplitude >= min_amplitude and self.is_gentle_volume(volume_ratio):
                new_active.append({
                    'code': stock_code,
                    'name': stock_name,
                    'amplitude': amplitude,
                    'volume_ratio': volume_ratio,
                    'price': kline[0]['close']
                })
        
        # 检查当前活跃池，找出不再活跃的股票
        should_exit = self.check_exit_candidates(new_active)
        
        logger.info(f"扫描完成: 发现 {len(new_active)} 只活跃股票, {len(should_exit)} 只应移出")
        return new_active, should_exit
    
    def check_exit_candidates(self, current_active: List[Dict]) -> List[Dict]:
        """检查当前活跃池中应退出的股票"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT stock_code, stock_name, entry_date, entry_price FROM active_pool WHERE status = 'ACTIVE'")
        current_pool = cursor.fetchall()
        
        active_codes = {s['code'] for s in current_active}
        should_exit = []
        
        for code, name, entry_date, entry_price in current_pool:
            if code not in active_codes:
                # 检查为什么退出
                kline = self.get_stock_kline(code, 10)
                if len(kline) >= 2:
                    amplitude = self.calculate_amplitude(kline)
                    volume_ratio = self.calculate_volume_ratio(kline)
                    
                    if amplitude is not None and amplitude < 3.0:
                        reason = f"振幅不足({amplitude}%)"
                    elif volume_ratio is not None and not self.is_gentle_volume(volume_ratio):
                        reason = f"放量异常({volume_ratio}%)"
                    else:
                        reason = "不再活跃"
                    
                    should_exit.append({
                        'code': code,
                        'name': name,
                        'entry_date': entry_date,
                        'exit_price': kline[0]['close'],
                        'reason': reason
                    })
        
        return should_exit
    
    def add_to_active_pool(self, stocks: List[Dict]):
        """添加股票到活跃池"""
        cursor = self.conn.cursor()
        added = 0
        
        for stock in stocks:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO active_pool 
                    (stock_code, stock_name, entry_price, entry_amplitude, entry_volume_ratio, last_check_date)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    stock['code'],
                    stock['name'],
                    stock['price'],
                    stock['amplitude'],
                    stock['volume_ratio'],
                    datetime.now()
                ))
                if cursor.rowcount > 0:
                    added += 1
                    logger.info(f"添加 {stock['code']}({stock['name']}) 到活跃池: 振幅{stock['amplitude']}%, 放量{stock['volume_ratio']}%")
            except Exception as e:
                logger.error(f"添加 {stock['code']} 失败: {e}")
        
        self.conn.commit()
        logger.info(f"新增 {added} 只股票到活跃池")
    
    def move_to_backup_pool(self, stocks: List[Dict]):
        """将股票移到备用池"""
        cursor = self.conn.cursor()
        moved = 0
        
        for stock in stocks:
            try:
                # 计算在池中的天数
                entry_date = datetime.fromisoformat(stock['entry_date'].replace('Z', '+00:00').replace('+00:00', ''))
                days_in_pool = (datetime.now() - entry_date).days
                
                # 插入备用池
                cursor.execute("""
                    INSERT INTO backup_pool 
                    (stock_code, stock_name, entry_date, exit_reason, days_in_pool, final_price)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    stock['code'],
                    stock['name'],
                    stock['entry_date'],
                    stock['reason'],
                    days_in_pool,
                    stock['exit_price']
                ))
                
                # 从活跃池移除
                cursor.execute("DELETE FROM active_pool WHERE stock_code = ?", (stock['code'],))
                moved += 1
                logger.info(f"移动 {stock['code']}({stock['name']}) 到备用池: {stock['reason']}, 在池{days_in_pool}天")
            except Exception as e:
                logger.error(f"移动 {stock['code']} 失败: {e}")
        
        self.conn.commit()
        logger.info(f"移动 {moved} 只股票到备用池")
    
    def get_active_pool(self) -> List[Dict]:
        """获取当前活跃池"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT stock_code, stock_name, entry_date, entry_price, 
                   entry_amplitude, entry_volume_ratio, last_check_date
            FROM active_pool WHERE status = 'ACTIVE'
            ORDER BY entry_date DESC
        """)
        
        rows = cursor.fetchall()
        return [
            {
                'code': row[0],
                'name': row[1],
                'entry_date': row[2],
                'entry_price': row[3],
                'amplitude': row[4],
                'volume_ratio': row[5],
                'last_check': row[6]
            }
            for row in rows
        ]
    
    def get_backup_pool(self, limit: int = 50) -> List[Dict]:
        """获取备用池"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT stock_code, stock_name, entry_date, exit_date, 
                   exit_reason, days_in_pool, final_price
            FROM backup_pool
            ORDER BY exit_date DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        return [
            {
                'code': row[0],
                'name': row[1],
                'entry_date': row[2],
                'exit_date': row[3],
                'reason': row[4],
                'days_in_pool': row[5],
                'final_price': row[6]
            }
            for row in rows
        ]
    
    def record_scan_history(self, total: int, active: int, moved: int, params: str):
        """记录扫描历史"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO scan_history (total_stocks, active_found, moved_to_backup, params)
            VALUES (?, ?, ?, ?)
        """, (total, active, moved, params))
        self.conn.commit()
    
    def close(self):
        """关闭连接"""
        if self.conn:
            self.conn.close()
        if self.beifeng_conn:
            self.beifeng_conn.close()


def main():
    parser = argparse.ArgumentParser(description='东风 - 股票初筛与池管理')
    parser.add_argument('--scan', action='store_true', help='执行扫描')
    parser.add_argument('--list', action='store_true', help='列出活跃池')
    parser.add_argument('--backup', action='store_true', help='列出备用池')
    parser.add_argument('--min-amplitude', type=float, default=3.0, help='最小振幅(%%)，默认3%%')
    
    args = parser.parse_args()
    
    manager = StockPoolManager()
    
    try:
        if args.scan:
            logger.info("=" * 50)
            logger.info("🌸 东风开始扫描股票...")
            logger.info("=" * 50)
            
            new_active, should_exit = manager.scan_stocks(args.min_amplitude)
            
            # 添加新活跃股票
            if new_active:
                manager.add_to_active_pool(new_active)
            
            # 移出不再活跃的股票
            if should_exit:
                manager.move_to_backup_pool(should_exit)
            
            # 记录历史
            manager.record_scan_history(
                total=len(new_active) + len(should_exit),
                active=len(new_active),
                moved=len(should_exit),
                params=json.dumps({'min_amplitude': args.min_amplitude})
            )
            
            logger.info("=" * 50)
            logger.info(f"🌸 扫描完成: 新增 {len(new_active)} 只, 移出 {len(should_exit)} 只")
            logger.info("=" * 50)
        
        elif args.list:
            pool = manager.get_active_pool()
            print(f"\n🌸 当前活跃股票池 ({len(pool)} 只):\n")
            print(f"{'代码':<10} {'名称':<10} {'进入日期':<20} {'振幅':<8} {'放量':<8}")
            print("-" * 60)
            for s in pool:
                print(f"{s['code']:<10} {s['name']:<10} {s['entry_date']:<20} {s['amplitude']:<8}% {s['volume_ratio']:<8}%")
            print()
        
        elif args.backup:
            pool = manager.get_backup_pool()
            print(f"\n🌸 备用股票池 (最近 {len(pool)} 只):\n")
            print(f"{'代码':<10} {'名称':<10} {'退出日期':<20} {'原因':<20} {'天数':<6}")
            print("-" * 70)
            for s in pool:
                print(f"{s['code']:<10} {s['name']:<10} {s['exit_date']:<20} {s['reason']:<20} {s['days_in_pool']:<6}")
            print()
        
        else:
            parser.print_help()
    
    finally:
        manager.close()


if __name__ == "__main__":
    main()
