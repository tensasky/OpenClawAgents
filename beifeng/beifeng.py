#!/usr/bin/python3
"""
北风 - 股票数据采集 Agent (重构版)
完整流程：自检 -> 测速 -> 抓取 -> 校验 -> 持久化
"""

import os
import sys
import time
import json
import sqlite3
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

# 导入抓取模块
from fetcher import DataFetcher, SinaFetcher, TencentFetcher, RateLimiter
from minute_fetcher import MinuteDataFetcher

# 配置
WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
DATA_DIR = WORKSPACE / "data"
LOG_DIR = WORKSPACE / "logs"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 初始化日志
log = get_logger("北风")

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"beifeng_{datetime.now():%Y%m%d}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("北风")

# 数据源配置
DATA_SOURCES = {
    "tencent": {
        "name": "腾讯财经",
        "url": "https://qt.gtimg.cn/q=sh000001",
        "timeout": 30,
        "weight": 1.0
    },
    "sina": {
        "name": "新浪财经",
        "url": "https://hq.sinajs.cn/list=sh000001",
        "timeout": 30,
        "weight": 0.5
    }
}


@dataclass
class SourceHealth:
    """数据源健康状态"""
    name: str
    latency: float
    available: bool
    error_msg: Optional[str] = None


@dataclass
class FetchTask:
    """抓取任务"""
    stock_code: str
    data_type: str
    start_time: datetime
    end_time: datetime
    priority: int = 0
    retry_count: int = 0


@dataclass
class SyncStatus:
    """同步状态"""
    stock_code: str
    data_type: str
    last_sync: Optional[datetime]
    last_success: Optional[datetime]
    record_count: int
    gap_ranges: List[Tuple[datetime, datetime]]  # 历史缺口


class Database:
    """数据库管理"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(DATA_DIR / "stocks_real.db")
        self.conn = None
        self.init_db()
    
    def init_db(self):
        """初始化数据库表结构"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        
        # K线数据
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS kline_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                data_type TEXT,
                timestamp TIMESTAMP,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                amount REAL,
                source TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(stock_code, data_type, timestamp)
            )
        """)
        
        # 同步状态
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_status (
                stock_code TEXT,
                data_type TEXT,
                last_sync TIMESTAMP,
                last_success TIMESTAMP,
                record_count INTEGER DEFAULT 0,
                PRIMARY KEY (stock_code, data_type)
            )
        """)
        
        # 抓取日志
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                data_type TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                status TEXT,
                records_count INTEGER,
                source TEXT,
                duration_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 错误任务
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS error_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                data_type TEXT,
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                error_msg TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        
        # 数据缺口
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS data_gaps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                data_type TEXT,
                gap_start TIMESTAMP,
                gap_end TIMESTAMP,
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP
            )
        """)
        
        self.conn.commit()
        log.info(f"数据库初始化完成: {self.db_path}")
    
    def get_sync_status(self, stock_code: str, data_type: str) -> Optional[SyncStatus]:
        """获取同步状态"""
        cursor = self.conn.execute(
            """SELECT * FROM sync_status WHERE stock_code=? AND data_type=?""",
            (stock_code, data_type)
        )
        row = cursor.fetchone()
        
        if row:
            # 获取缺口
            cursor = self.conn.execute(
                """SELECT gap_start, gap_end FROM data_gaps 
                   WHERE stock_code=? AND data_type=? AND status='OPEN'""",
                (stock_code, data_type)
            )
            gaps = [(datetime.fromisoformat(r['gap_start']), 
                     datetime.fromisoformat(r['gap_end'])) for r in cursor.fetchall()]
            
            return SyncStatus(
                stock_code=row['stock_code'],
                data_type=row['data_type'],
                last_sync=datetime.fromisoformat(row['last_sync']) if row['last_sync'] else None,
                last_success=datetime.fromisoformat(row['last_success']) if row['last_success'] else None,
                record_count=row['record_count'],
                gap_ranges=gaps
            )
        return None
    
    def update_sync_status(self, stock_code: str, data_type: str, record_count: int = None):
        """更新同步状态"""
        now = datetime.now().isoformat()
        
        if record_count is not None:
            self.conn.execute(
                """INSERT OR REPLACE INTO sync_status 
                   (stock_code, data_type, last_sync, last_success, record_count)
                   VALUES (?, ?, ?, ?, ?)""",
                (stock_code, data_type, now, now, record_count)
            )
        else:
            self.conn.execute(
                """INSERT OR REPLACE INTO sync_status 
                   (stock_code, data_type, last_sync)
                   VALUES (?, ?, ?)
                   ON CONFLICT(stock_code, data_type) 
                   DO UPDATE SET last_sync=?""",
                (stock_code, data_type, now, now)
            )
        self.conn.commit()
    
    def insert_kline(self, stock_code: str, data_type: str, data: List[Dict], source: str):
        """插入K线数据"""
        for item in data:
            self.conn.execute(
                """INSERT OR REPLACE INTO kline_data 
                   (stock_code, data_type, timestamp, open, high, low, close, volume, amount, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (stock_code, data_type, item['timestamp'], 
                 item['open'], item['high'], item['low'], item['close'],
                 item['volume'], item['amount'], source)
            )
        self.conn.commit()
    
    def log_fetch(self, stock_code: str, data_type: str, start: datetime, end: datetime,
                  status: str, count: int, source: str, duration_ms: int):
        """记录抓取日志"""
        self.conn.execute(
            """INSERT INTO fetch_log (stock_code, data_type, start_time, end_time, status, records_count, source, duration_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (stock_code, data_type, start.isoformat(), end.isoformat(), status, count, source, duration_ms)
        )
        self.conn.commit()
    
    def log_error_task(self, task: FetchTask, error_msg: str):
        """记录错误任务"""
        self.conn.execute(
            """INSERT INTO error_tasks (stock_code, data_type, start_time, end_time, error_msg, retry_count)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (task.stock_code, task.data_type, task.start_time.isoformat(), 
             task.end_time.isoformat(), error_msg, task.retry_count)
        )
        self.conn.commit()
    
    def add_data_gap(self, stock_code: str, data_type: str, gap_start: datetime, gap_end: datetime):
        """添加数据缺口"""
        self.conn.execute(
            """INSERT INTO data_gaps (stock_code, data_type, gap_start, gap_end)
               VALUES (?, ?, ?, ?)""",
            (stock_code, data_type, gap_start.isoformat(), gap_end.isoformat())
        )
        self.conn.commit()
    
    def resolve_data_gap(self, stock_code: str, data_type: str, gap_start: datetime, gap_end: datetime):
        """标记缺口已解决"""
        self.conn.execute(
            """UPDATE data_gaps SET status='RESOLVED', resolved_at=datetime('now')
               WHERE stock_code=? AND data_type=? AND gap_start=? AND gap_end=?""",
            (stock_code, data_type, gap_start.isoformat(), gap_end.isoformat())
        )
        self.conn.commit()
    
    def get_data_range(self, stock_code: str, data_type: str) -> Tuple[Optional[datetime], Optional[datetime]]:
        """获取数据时间范围"""
        cursor = self.conn.execute(
            """SELECT MIN(timestamp) as min_time, MAX(timestamp) as max_time 
               FROM kline_data WHERE stock_code=? AND data_type=?""",
            (stock_code, data_type)
        )
        row = cursor.fetchone()
        if row and row['min_time']:
            return (datetime.fromisoformat(row['min_time']), 
                    datetime.fromisoformat(row['max_time']))
        return (None, None)


class SelfCheck:
    """阶段1: 自检"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def run(self) -> bool:
        """执行自检"""
        log.info("🔍 阶段1: 自检")
        
        checks = []
        
        # 1. 数据库连接
        try:
            self.db.conn.execute("SELECT 1")
            checks.append(("数据库连接", True, None))
        except Exception as e:
            checks.append(("数据库连接", False, str(e)))
        
        # 2. 磁盘空间
        try:
            stat = os.statvfs(DATA_DIR)
            free_gb = stat.f_bavail * stat.f_frsize / (1024**3)
            if free_gb > 1.0:  # 至少1GB
                checks.append(("磁盘空间", True, f"{free_gb:.1f}GB 可用"))
            else:
                checks.append(("磁盘空间", False, f"仅 {free_gb:.1f}GB 可用"))
        except Exception as e:
            checks.append(("磁盘空间", False, str(e)))
        
        # 3. 网络连通性
        try:
            import urllib.request
            urllib.request.urlopen("https://www.baidu.com", timeout=5)
            checks.append(("网络连通", True, None))
        except Exception as e:
            checks.append(("网络连通", False, str(e)))
        
        # 输出结果
        all_pass = True
        for name, passed, info in checks:
            status = "✅" if passed else "❌"
            msg = f"  {status} {name}"
            if info:
                msg += f": {info}"
            log.info(msg)
            if not passed:
                all_pass = False
        
        return all_pass


class SourceSpeedTest:
    """阶段2: 测速 - 选择最优数据源"""
    
    def __init__(self):
        self.sources = DATA_SOURCES
    
    def run(self) -> Optional[str]:
        """执行测速，返回最优数据源名称"""
        log.info("\n⚡ 阶段2: 测速")
        
        results = []
        
        for key, config in self.sources.items():
            health = self._test_source(key, config)
            results.append(health)
            
            status = "✅" if health.available else "❌"
            log.info(f"  {status} {config['name']}: {health.latency*1000:.0f}ms")
        
        # 选择最优
        available = [r for r in results if r.available]
        if not available:
            log.error("❌ 所有数据源不可用！")
            return None
        
        # 按延迟排序
        best = min(available, key=lambda x: x.latency)
        log.info(f"🎯 选择数据源: {best.name} ({best.latency*1000:.0f}ms)")
        return best.name
    
    def _test_source(self, key: str, config: Dict) -> SourceHealth:
        """测试单个数据源"""
        try:
            import requests
            start = time.time()
            response = requests.head(
                config['url'], 
                timeout=config['timeout'],
                allow_redirects=True
            )
            latency = time.time() - start
            
            if response.status_code == 200:
                return SourceHealth(name=key, latency=latency, available=True)
            else:
                return SourceHealth(name=key, latency=latency, available=False, 
                                   error_msg=f"HTTP {response.status_code}")
        
        except Exception as e:
            return SourceHealth(name=key, latency=999, available=False, error_msg=str(e))


class FetchEngine:
    """阶段3: 抓取引擎"""
    
    def __init__(self, db: Database, source: str):
        self.db = db
        self.source = source
        self.fetcher = DataFetcher(source)
        self.rate_limiter = RateLimiter()
        self.minute_fetcher = MinuteDataFetcher()
    
    def run(self, task: FetchTask) -> Tuple[bool, int, str]:
        """
        执行抓取任务
        返回: (成功, 记录数, 错误信息)
        """
        log.info(f"\n📥 抓取: {task.stock_code} ({task.start_time.date()} ~ {task.end_time.date()})")
        
        start_time = time.time()
        
        try:
            # 应用速率限制
            self.rate_limiter.wait()
            
            # 执行抓取
            if task.data_type == 'daily':
                data = self.fetcher.fetch_daily(task.stock_code, task.start_time, task.end_time)
            elif task.data_type == 'minute':
                # 分钟数据：获取当日数据
                minute_data = self.minute_fetcher.fetch_tencent_minute(task.stock_code)
                if minute_data:
                    # 保存分钟数据
                    self._save_minute_data(task.stock_code, minute_data)
                    log.info(f"   ✅ 成功: {len(minute_data)} 条分钟数据")
                    return True, len(minute_data), ""
                else:
                    log.info(f"   ⚠️ 无分钟数据")
                    return True, 0, ""
            else:
                raise ValueError(f"不支持的数据类型: {task.data_type}")
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # 超时检查
            if duration_ms > 30000:  # 30秒
                log.warning(f"  ⏱️ 请求超时 ({duration_ms}ms)")
                self.db.log_error_task(task, f"Timeout: {duration_ms}ms")
                return False, 0, f"Timeout: {duration_ms}ms"
            
            # 数据校验
            if not self._validate_data(data):
                log.warning(f"  ⚠️ 数据校验失败")
                self.db.log_fetch(task.stock_code, task.data_type, task.start_time, task.end_time,
                                 'INVALID', 0, self.source, duration_ms)
                return False, 0, "Data validation failed"
            
            # 持久化
            if data:
                self.db.insert_kline(task.stock_code, task.data_type, data, self.source)
                self.db.log_fetch(task.stock_code, task.data_type, task.start_time, task.end_time,
                                 'SUCCESS', len(data), self.source, duration_ms)
                
                # 更新同步状态
                self.db.update_sync_status(task.stock_code, task.data_type, len(data))
                
                log.info(f"  ✅ 成功: {len(data)} 条记录 ({duration_ms}ms)")
                return True, len(data), None
            else:
                log.info(f"  ⚠️ 无数据")
                self.db.log_fetch(task.stock_code, task.data_type, task.start_time, task.end_time,
                                 'EMPTY', 0, self.source, duration_ms)
                return True, 0, None
                
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            log.error(f"  ❌ 失败: {error_msg}")
            
            self.db.log_fetch(task.stock_code, task.data_type, task.start_time, task.end_time,
                             'FAILED', 0, self.source, duration_ms)
            self.db.log_error_task(task, error_msg)
            
            return False, 0, error_msg
    
    def _save_minute_data(self, stock_code: str, data: List[Dict]):
        """保存分钟数据到数据库"""
        from datetime import datetime, timedelta
        import random
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        for item in data:
            try:
                # 解析时间戳 (格式: '0930' -> 转换为今天的时间)
                ts = item.get('time', '')
                if ts and len(ts) == 4 and ts.isdigit():
                    hour = int(ts[:2])
                    minute = int(ts[2:])
                    # 转换为今天的时间
                    now = datetime.now()
                    timestamp = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                    # 如果时间还没到（大于当前时间），使用前一个交易日
                    if timestamp > now:
                        timestamp = timestamp - timedelta(days=1)
                        # 调整为交易时间
                        if timestamp.hour < 9 or (timestamp.hour == 9 and timestamp.minute < 30):
                            timestamp = timestamp.replace(hour=9, minute=30)
                else:
                    timestamp = datetime.now()
                
                price = item.get('price', item.get('open', 0))
                
                self.db.conn.execute("""
                    INSERT OR REPLACE INTO minute 
                    (stock_code, timestamp, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    stock_code,
                    timestamp,
                    price, price, price, price,
                    item.get('volume', 0)
                ))
            except Exception as e:
                log.warning(f"   ⚠️ 保存失败: {e}")
        self.db.conn.commit()
    
    def _validate_data(self, data: List[Dict]) -> bool:
        """数据校验"""
        if not data:
            return True  # 空数据不算失败
        
        required_fields = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        
        for item in data:
            # 检查必需字段
            for field in required_fields:
                if field not in item:
                    log.warning(f"  缺少字段: {field}")
                    return False
            
            # 检查数值有效性
            try:
                if float(item['close']) <= 0:
                    return False
                if float(item['high']) < float(item['low']):
                    return False
            except (ValueError, TypeError):
                return False
        
        return True


class TaskPlanner:
    """任务规划器 - 生成抓取任务"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def plan(self, stock_codes: List[str], data_type: str = 'daily') -> List[FetchTask]:
        """规划抓取任务"""
        log.info(f"\n📋 任务规划: {len(stock_codes)} 只股票")
        
        tasks = []
        now = datetime.now()
        
        for code in stock_codes:
            # 获取当前数据范围
            min_time, max_time = self.db.get_data_range(code, data_type)
            
            if min_time is None:
                # 全新股票，抓取5年历史
                log.info(f"  {code}: 全新股票，全量抓取")
                tasks.append(FetchTask(
                    stock_code=code,
                    data_type=data_type,
                    start_time=now - timedelta(days=365*5),
                    end_time=now,
                    priority=0
                ))
            else:
                # 1. 先补历史缺口
                status = self.db.get_sync_status(code, data_type)
                if status and status.gap_ranges:
                    for gap_start, gap_end in status.gap_ranges:
                        log.info(f"  {code}: 补缺口 {gap_start.date()} ~ {gap_end.date()}")
                        tasks.append(FetchTask(
                            stock_code=code,
                            data_type=data_type,
                            start_time=gap_start,
                            end_time=gap_end,
                            priority=2  # 高优先级
                        ))
                
                # 2. 再抓增量
                if (now - max_time) > timedelta(days=1):
                    log.info(f"  {code}: 增量更新 {max_time.date()} ~ {now.date()}")
                    tasks.append(FetchTask(
                        stock_code=code,
                        data_type=data_type,
                        start_time=max_time,
                        end_time=now,
                        priority=1
                    ))
        
        # 按优先级排序
        tasks.sort(key=lambda x: x.priority, reverse=True)
        
        log.info(f"  生成 {len(tasks)} 个任务")
        return tasks


class BeiFengAgent:
    """北风 Agent 主类"""
    
    def __init__(self):
        self.db = Database()
        self.current_source = None
    
    def run(self, stock_codes: List[str], data_type: str = 'daily'):
        """执行完整流程"""
        log.info("=" * 60)
        log.info("🌪️ 北风启动 - 股票数据采集")
        log.info("=" * 60)
        
        # ========== 阶段1: 自检 ==========
        self_check = SelfCheck(self.db)
        if not self_check.run():
            log.error("❌ 自检失败，任务终止")
            return False
        
        # ========== 阶段2: 测速 ==========
        speed_test = SourceSpeedTest()
        best_source = speed_test.run()
        
        if not best_source:
            log.error("❌ 无可用数据源，任务终止")
            return False
        
        self.current_source = best_source
        
        # ========== 阶段3: 任务规划 ==========
        planner = TaskPlanner(self.db)
        tasks = planner.plan(stock_codes, data_type)
        
        if not tasks:
            log.info("✅ 所有数据已是最新，无需抓取")
            return True
        
        # ========== 阶段4: 抓取 ==========
        log.info(f"\n📥 阶段4: 抓取 ({best_source})")
        engine = FetchEngine(self.db, best_source)
        
        success_count = 0
        fail_count = 0
        total_records = 0
        
        for i, task in enumerate(tasks, 1):
            log.info(f"\n[{i}/{len(tasks)}]")
            success, count, error = engine.run(task)
            
            if success:
                success_count += 1
                total_records += count
            else:
                fail_count += 1
        
        # ========== 阶段5: 报告 ==========
        log.info("\n" + "=" * 60)
        log.info("📊 执行报告")
        log.info("=" * 60)
        log.info(f"  任务总数: {len(tasks)}")
        log.info(f"  成功: {success_count}")
        log.info(f"  失败: {fail_count}")
        log.info(f"  新增记录: {total_records}")
        log.info("=" * 60)
        
        return fail_count == 0


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='北风 - 股票数据采集 Agent')
    parser.add_argument('stocks', nargs='+', help='股票代码列表 (如: sh000001 sz000001)')
    parser.add_argument('--type', default='daily', choices=['daily', 'minute', 'tick'],
                       help='数据类型')
    
    args = parser.parse_args()
    
    agent = BeiFengAgent()
    success = agent.run(args.stocks, args.type)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
