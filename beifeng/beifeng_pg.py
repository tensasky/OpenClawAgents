#!/usr/bin/env python3
"""
北风 - 股票数据采集 Agent (PostgreSQL 版本)
三阶段架构：探测 -> 执行 -> 审计
"""

import os
import sys
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import requests
from dataclasses import dataclass
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor

# 配置
WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
DATA_DIR = WORKSPACE / "data"
LOG_DIR = WORKSPACE / "logs"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

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

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "database": "beifeng_stocks",
    "user": "beifeng",
    "password": ""  # 本地信任连接，无需密码
}

# 数据源配置
DATA_SOURCES = {
    "sina": {
        "name": "新浪财经",
        "url": "https://hq.sinajs.cn/list=sh000001",
        "timeout": 30,
        "weight": 1.0
    },
    "tencent": {
        "name": "腾讯财经", 
        "url": "https://qt.gtimg.cn/q=sh000001",
        "timeout": 30,
        "weight": 1.0
    },
    "eastmoney": {
        "name": "东方财富",
        "url": "https://push2.eastmoney.com/api/qt/stock/get?secid=1.000001",
        "timeout": 30,
        "weight": 0.8
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


class Database:
    """PostgreSQL 数据库管理"""
    
    def __init__(self):
        self.conn = None
        self.connect()
    
    def connect(self):
        """连接数据库"""
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.conn.autocommit = False
            logger.info("✅ 数据库连接成功")
        except Exception as e:
            logger.error(f"❌ 数据库连接失败: {e}")
            raise
    
    def get_last_update(self, stock_code: str, data_type: str) -> Optional[datetime]:
        """获取某股票某类型的最后更新时间"""
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT MAX(timestamp) as last_time FROM kline_data 
                   WHERE stock_code=%s AND data_type=%s""",
                (stock_code, data_type)
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
        return None
    
    def get_failed_ranges(self, stock_code: str, data_type: str) -> List[Tuple[datetime, datetime]]:
        """获取失败的区间"""
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT start_time, end_time FROM fetch_log 
                   WHERE stock_code=%s AND data_type=%s AND status='FAILED'
                   ORDER BY created_at DESC LIMIT 10""",
                (stock_code, data_type)
            )
            return [(row[0], row[1]) for row in cur.fetchall()]
    
    def log_fetch(self, stock_code: str, data_type: str, start: datetime, end: datetime,
                  status: str, count: int, source: str, error_msg: str = None):
        """记录抓取日志"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO fetch_log (stock_code, data_type, start_time, end_time, status, records_count, source, error_msg)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                    (stock_code, data_type, start, end, status, count, source, error_msg)
                )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"记录抓取日志失败: {e}")
    
    def log_error(self, stock_code: str, data_type: str, missed_range: str, reason: str, source: str):
        """记录错误日志"""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO error_log (stock_code, data_type, missed_range, reason, source)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (stock_code, data_type, missed_range, reason, source)
                )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            logger.error(f"记录错误日志失败: {e}")
    
    def insert_kline_batch(self, stock_code: str, data_type: str, data: List[Dict]):
        """批量插入K线数据"""
        if not data:
            return
        
        inserted = 0
        for item in data:
            try:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO kline_data (stock_code, data_type, timestamp, open, high, low, close, volume, amount)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT DO NOTHING""",
                        (stock_code, data_type, item['timestamp'], 
                         item['open'], item['high'], item['low'], item['close'],
                         item['volume'], item['amount'])
                    )
                self.conn.commit()
                inserted += 1
            except Exception as e:
                self.conn.rollback()
                logger.warning(f"  插入单条失败: {e}")
        
        logger.info(f"  ✅ 成功写入 {inserted}/{len(data)} 条记录")
    
    def insert_stock(self, code: str, name: str, market: str):
        """插入股票基础信息"""
        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO stocks (code, name, market) VALUES (%s, %s, %s)
                   ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name, updated_at=CURRENT_TIMESTAMP""",
                (code, name, market)
            )
        self.conn.commit()
    
    def get_all_stocks(self) -> List[Dict]:
        """获取所有股票列表"""
        with self.conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT * FROM stocks ORDER BY code")
            return cur.fetchall()


class SourcePoller:
    """阶段一：数据源连通性探测"""
    
    def __init__(self):
        self.sources = DATA_SOURCES
    
    def poll_all(self) -> List[SourceHealth]:
        """探测所有数据源"""
        results = []
        for key, config in self.sources.items():
            health = self._test_source(key, config)
            results.append(health)
            status = "✅" if health.available else "❌"
            logger.info(f"{status} {config['name']}: {health.latency*1000:.0f}ms")
        return results
    
    def _test_source(self, key: str, config: Dict) -> SourceHealth:
        try:
            start = time.time()
            response = requests.get(
                config['url'],
                timeout=config['timeout'],
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            latency = time.time() - start
            
            if response.status_code == 200:
                return SourceHealth(name=key, latency=latency, available=True)
            else:
                return SourceHealth(name=key, latency=latency, available=False, 
                                  error_msg=f"HTTP {response.status_code}")
        except requests.Timeout:
            return SourceHealth(name=key, latency=config['timeout'], available=False, 
                              error_msg="Timeout (>30s)")
        except Exception as e:
            return SourceHealth(name=key, latency=0, available=False, error_msg=str(e))
    
    def select_best(self, results: List[SourceHealth]) -> Optional[str]:
        available = [r for r in results if r.available]
        if not available:
            logger.error("❌ 所有数据源不可用！")
            return None
        # 优先选择腾讯（已实现）
        for r in available:
            if r.name == "tencent":
                logger.info(f"🎯 选择数据源: {r.name} ({r.latency*1000:.0f}ms)")
                return r.name
        # 否则选最快的
        best = min(available, key=lambda x: x.latency)
        logger.info(f"🎯 选择数据源: {best.name} ({best.latency*1000:.0f}ms)")
        return best.name


class StockDataFetcher:
    """股票数据抓取器"""
    
    def __init__(self, source: str):
        self.source = source
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def fetch_daily_kline(self, stock_code: str, start: datetime, end: datetime) -> List[Dict]:
        """获取日K线数据"""
        if self.source == "tencent":
            return self._fetch_tencent_daily(stock_code, start, end)
        elif self.source == "sina":
            return self._fetch_sina_daily(stock_code, start, end)
        else:
            raise NotImplementedError(f"数据源 {self.source} 尚未实现")
    
    def _fetch_tencent_daily(self, stock_code: str, start: datetime, end: datetime) -> List[Dict]:
        """从腾讯财经获取日K线"""
        # 转换股票代码格式 (sh000001 -> sh000001, sz000001 -> sz000001)
        # 腾讯格式: sh000001, sz000001
        code = stock_code.lower()
        
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"{code},day,{start.strftime('%Y-%m-%d')},{end.strftime('%Y-%m-%d')},500,qfq"
        }
        
        try:
            logger.info(f"  请求: {code}")
            response = self.session.get(url, params=params, timeout=30)
            data = response.json()
            
            result = []
            kline_data = data.get("data", {}).get(code, {}).get("qfqday", []) or data.get("data", {}).get(code, {}).get("day", [])
            
            for item in kline_data:
                # 格式: [日期, 开盘, 收盘, 最低, 最高, 成交量]
                result.append({
                    'timestamp': datetime.strptime(item[0], '%Y-%m-%d'),
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'low': float(item[3]),
                    'high': float(item[4]),
                    'volume': int(float(item[5])),
                    'amount': float(item[6]) if len(item) > 6 else 0
                })
            
            logger.info(f"  获取 {len(result)} 条数据")
            return result
        except Exception as e:
            logger.error(f"  抓取失败: {e}")
            return []


class IncrementalFetcher:
    """阶段二：增量补数逻辑"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def generate_tasks(self, stock_codes: List[str], data_type: str = 'daily') -> List[FetchTask]:
        """生成抓取任务"""
        tasks = []
        now = datetime.now()
        
        for code in stock_codes:
            last_update = self.db.get_last_update(code, data_type)
            
            if last_update is None:
                # 全新股票，抓取5年历史
                logger.info(f"📊 {code}: 无历史数据，全量抓取")
                tasks.append(FetchTask(
                    stock_code=code, data_type=data_type,
                    start_time=now - timedelta(days=365*5), end_time=now, priority=0
                ))
            elif (now - last_update) > timedelta(minutes=5):
                # 需要增量更新
                logger.info(f"🔄 {code}: 最后更新 {last_update}, 需要补数")
                tasks.append(FetchTask(
                    stock_code=code, data_type=data_type,
                    start_time=last_update, end_time=now, priority=0
                ))
            
            # 检查失败区间
            failed_ranges = self.db.get_failed_ranges(code, data_type)
            for start, end in failed_ranges:
                logger.info(f"🔁 {code}: 断点续传 {start} ~ {end}")
                tasks.append(FetchTask(
                    stock_code=code, data_type=data_type,
                    start_time=start, end_time=end, priority=1
                ))
        
        tasks.sort(key=lambda x: x.priority, reverse=True)
        return tasks


class BeiFengAgent:
    """北风 Agent 主类"""
    
    def __init__(self):
        self.db = Database()
        self.poller = SourcePoller()
        self.fetcher = IncrementalFetcher(self.db)
        self.current_source = None
        self.data_fetcher = None
    
    def run(self, stock_codes: List[str], data_type: str = 'daily'):
        """执行三阶段流程"""
        logger.info("=" * 60)
        logger.info("🌪️ 北风启动 - 股票数据采集 (PostgreSQL版)")
        logger.info("=" * 60)
        
        # 阶段一：探测
        logger.info("\n📡 阶段一：数据源连通性探测")
        health_results = self.poller.poll_all()
        best_source = self.poller.select_best(health_results)
        
        if not best_source:
            logger.error("❌ 无可用数据源，任务终止")
            return False
        
        self.current_source = best_source
        self.data_fetcher = StockDataFetcher(best_source)
        
        # 阶段二：执行
        logger.info("\n📥 阶段二：增量补数")
        tasks = self.fetcher.generate_tasks(stock_codes, data_type)
        logger.info(f"生成 {len(tasks)} 个抓取任务")
        
        for i, task in enumerate(tasks, 1):
            logger.info(f"\n[{i}/{len(tasks)}] {task.stock_code} {task.data_type}")
            self._execute_task(task)
        
        # 阶段三：审计
        logger.info("\n📊 阶段三：审计报告")
        self._generate_report()
        
        logger.info("\n✅ 北风任务完成")
        return True
    
    def _execute_task(self, task: FetchTask):
        """执行单个任务"""
        try:
            logger.info(f"  抓取区间: {task.start_time.date()} ~ {task.end_time.date()}")
            
            # 抓取数据
            data = self.data_fetcher.fetch_daily_kline(
                task.stock_code, task.start_time, task.end_time
            )
            
            if data:
                # 批量插入
                self.db.insert_kline_batch(task.stock_code, task.data_type, data)
                logger.info(f"  ✅ 成功写入 {len(data)} 条记录")
                
                self.db.log_fetch(
                    task.stock_code, task.data_type, task.start_time, task.end_time,
                    'SUCCESS', len(data), self.current_source
                )
            else:
                logger.warning(f"  ⚠️ 无数据返回")
                self.db.log_fetch(
                    task.stock_code, task.data_type, task.start_time, task.end_time,
                    'FAILED', 0, self.current_source, "无数据"
                )
        
        except Exception as e:
            logger.error(f"  ❌ 抓取失败: {e}")
            self.db.log_error(
                task.stock_code, task.data_type,
                f"{task.start_time}~{task.end_time}", str(e), self.current_source
            )
            self.db.log_fetch(
                task.stock_code, task.data_type, task.start_time, task.end_time,
                'FAILED', 0, self.current_source, str(e)
            )
    
    def _generate_report(self):
        """生成报告"""
        with self.db.conn.cursor() as cur:
            cur.execute("""
                SELECT status, COUNT(*) as count FROM fetch_log 
                WHERE date(created_at) = CURRENT_DATE GROUP BY status
            """)
            stats = {row[0]: row[1] for row in cur.fetchall()}
            
            cur.execute("""
                SELECT COUNT(*) as count FROM error_log 
                WHERE date(timestamp) = CURRENT_DATE
            """)
            error_count = cur.fetchone()[0]
        
        logger.info(f"\n📈 今日统计:")
        logger.info(f"  成功: {stats.get('SUCCESS', 0)}")
        logger.info(f"  失败: {stats.get('FAILED', 0)}")
        logger.info(f"  错误记录: {error_count}")


def fetch_all_astocks() -> List[str]:
    """获取所有 A 股代码列表"""
    logger.info("📋 获取 A 股全量代码...")
    
    all_stocks = []
    
    # 分页获取，每页500只
    for page in range(1, 20):  # 最多20页，10000只
        url = "https://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": page,
            "pz": 500,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",  # 沪深A股
            "fields": "f12,f13,f14",
            "_": int(time.time() * 1000)
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            items = data.get("data", {}).get("diff", [])
            if not items:
                break  # 没有更多数据
            
            for item in items:
                code = item.get("f12")
                market = item.get("f13")  # 1=上海, 0=深圳
                name = item.get("f14")
                
                if code and market:
                    prefix = "sh" if str(market) == "1" else "sz"
                    full_code = f"{prefix}{code}"
                    all_stocks.append((full_code, name, prefix.upper()))
            
            logger.info(f"  第{page}页: 获取 {len(items)} 只")
            time.sleep(0.5)  # 避免请求过快
            
        except Exception as e:
            logger.error(f"❌ 第{page}页获取失败: {e}")
            break
    
    logger.info(f"✅ 总共获取到 {len(all_stocks)} 只股票")
    return all_stocks


def main():
    """命令行入口"""
    import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")

    
    parser = argparse.ArgumentParser(description='北风 - 股票数据采集 Agent')
    parser.add_argument('--init', action='store_true', help='初始化股票列表')
    parser.add_argument('stocks', nargs='*', help='指定股票代码')
    parser.add_argument('--type', default='daily', choices=['daily', 'minute'])
    parser.add_argument('--all', action='store_true', help='抓取全部A股')
    
    args = parser.parse_args()
    
    agent = BeiFengAgent()
    
    if args.init:
        # 初始化全量股票列表
        stocks = fetch_all_astocks()
        for code, name, market in stocks:
            agent.db.insert_stock(code, name, market)
        logger.info(f"✅ 已导入 {len(stocks)} 只股票到数据库")
        return
    
    if args.all:
        # 抓取全部A股
        stocks_data = agent.db.get_all_stocks()
        if not stocks_data:
            logger.error("❌ 数据库中没有股票列表，请先运行 --init")
            return
        stock_codes = [s['code'] for s in stocks_data]
        logger.info(f"🚀 开始抓取全部 {len(stock_codes)} 只A股")
        agent.run(stock_codes, args.type)
    elif args.stocks:
        # 抓取指定股票
        agent.run(args.stocks, args.type)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
