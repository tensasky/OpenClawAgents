#!/usr/bin/env python3
"""
健壮性数据采集系统 - Resilient Data Fetcher
包含: 断路器、重试队列、优先级管理、状态持久化
"""

import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# 配置
LOG_DIR = Path.home() / "Documents/OpenClawAgents/beifeng/logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "resilient_fetcher.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ResilientFetcher")


class CircuitState(Enum):
    """断路器状态"""
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 断开
    HALF_OPEN = "half_open"  # 半开测试


@dataclass
class FetchTask:
    """采集任务"""
    task_id: str
    stock_code: str
    priority: int = 1  # 1-5，5最高
    retry_count: int = 0
    max_retry: int = 3
    created_at: datetime = None
    next_retry: datetime = None
    status: str = "pending"  # pending, running, completed, failed
    result: Dict = None
    error: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class CircuitBreaker:
    """断路器 - 防止故障扩散"""
    
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        self.lock = threading.Lock()
        
    def call(self, func: Callable, *args, **kwargs):
        """执行受保护的函数"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    logger.info(f"[{self.name}] 断路器半开，尝试恢复")
                else:
                    raise Exception(f"[{self.name}] 断路器断开，服务不可用")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info(f"[{self.name}] 断路器关闭，服务恢复")
            else:
                self.failure_count = max(0, self.failure_count - 1)
    
    def _on_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"[{self.name}] 半开状态失败，重新断开")
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"[{self.name}] 失败次数达{self.failure_threshold}，断路器断开")
    
    def _should_attempt_reset(self) -> bool:
        if self.last_failure_time is None:
            return True
        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed >= self.recovery_timeout


class RetryQueue:
    """重试队列 - 失败任务自动重试"""
    
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = str(Path.home() / "Documents/OpenClawAgents/beifeng/data/retry_queue.db")
        self.db_path = db_path
        self._init_db()
        self.lock = threading.Lock()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS retry_queue (
                task_id TEXT PRIMARY KEY,
                stock_code TEXT NOT NULL,
                priority INTEGER DEFAULT 1,
                retry_count INTEGER DEFAULT 0,
                max_retry INTEGER DEFAULT 3,
                created_at TEXT,
                next_retry TEXT,
                status TEXT DEFAULT 'pending',
                error TEXT,
                data TEXT
            )
        ''')
        conn.commit()
        conn.close()
    
    def add(self, task: FetchTask):
        """添加任务到重试队列"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 指数退避计算下次重试时间
            delay = 2 ** task.retry_count  # 2, 4, 8, 16...
            task.next_retry = datetime.now() + timedelta(seconds=delay)
            
            cursor.execute('''
                INSERT OR REPLACE INTO retry_queue 
                (task_id, stock_code, priority, retry_count, max_retry, created_at, next_retry, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task.task_id, task.stock_code, task.priority, task.retry_count,
                task.max_retry, task.created_at.isoformat(), 
                task.next_retry.isoformat(), task.status, task.error
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"[RetryQueue] 任务 {task.task_id} 加入队列，第{task.retry_count}次重试，{delay}秒后执行")
    
    def get_ready_tasks(self, limit: int = 10) -> List[FetchTask]:
        """获取待重试的任务"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute('''
                SELECT task_id, stock_code, priority, retry_count, max_retry, error
                FROM retry_queue
                WHERE status = 'pending' AND next_retry <= ?
                ORDER BY priority DESC, next_retry ASC
                LIMIT ?
            ''', (now, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            tasks = []
            for row in rows:
                task = FetchTask(
                    task_id=row[0],
                    stock_code=row[1],
                    priority=row[2],
                    retry_count=row[3],
                    max_retry=row[4],
                    error=row[5]
                )
                tasks.append(task)
            
            return tasks
    
    def remove(self, task_id: str):
        """移除任务"""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM retry_queue WHERE task_id = ?", (task_id,))
            conn.commit()
            conn.close()
    
    def get_stats(self) -> Dict:
        """获取队列统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*), AVG(retry_count) FROM retry_queue WHERE status = 'pending'")
        total, avg_retry = cursor.fetchone()
        
        cursor.execute("SELECT COUNT(*) FROM retry_queue WHERE retry_count >= max_retry")
        failed = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'pending': total,
            'avg_retry': avg_retry or 0,
            'permanently_failed': failed
        }


class TaskScheduler:
    """任务调度器 - 优先级管理和并发控制"""
    
    def __init__(self, max_concurrent: int = 3):
        self.max_concurrent = max_concurrent
        self.running_tasks: Dict[str, FetchTask] = {}
        self.task_semaphore = threading.Semaphore(max_concurrent)
        self.lock = threading.Lock()
        self._stop_event = threading.Event()
    
    def submit(self, task: FetchTask, executor: Callable) -> bool:
        """提交任务"""
        with self.lock:
            # 检查是否已有相同任务在运行
            if task.task_id in self.running_tasks:
                existing = self.running_tasks[task.task_id]
                
                # 高优先级可以抢占低优先级
                if task.priority > existing.priority:
                    logger.info(f"[Scheduler] 高优先级任务 {task.task_id} 抢占，中断旧任务")
                    self._cancel_task(task.task_id)
                else:
                    logger.info(f"[Scheduler] 任务 {task.task_id} 已在运行，跳过")
                    return False
        
        # 启动任务
        def task_wrapper():
            try:
                self.task_semaphore.acquire()
                with self.lock:
                    self.running_tasks[task.task_id] = task
                
                task.status = "running"
                result = executor(task)
                task.status = "completed"
                task.result = result
                
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                logger.error(f"[Scheduler] 任务 {task.task_id} 失败: {e}")
                raise
            finally:
                with self.lock:
                    if task.task_id in self.running_tasks:
                        del self.running_tasks[task.task_id]
                self.task_semaphore.release()
        
        threading.Thread(target=task_wrapper, name=f"Task-{task.task_id}").start()
        logger.info(f"[Scheduler] 任务 {task.task_id} 已启动 (优先级: {task.priority})")
        return True
    
    def _cancel_task(self, task_id: str):
        """取消任务（标记取消，由任务自行检查）"""
        if task_id in self.running_tasks:
            self.running_tasks[task_id].status = "cancelled"
    
    def is_running(self, task_id: str) -> bool:
        """检查任务是否在运行"""
        with self.lock:
            return task_id in self.running_tasks
    
    def get_running_count(self) -> int:
        """获取运行中的任务数"""
        with self.lock:
            return len(self.running_tasks)


class ResilientFetcher:
    """健壮性数据采集器 - 整合所有保护机制"""
    
    def __init__(self):
        # 为每个数据源创建断路器
        self.circuit_breakers = {
            'tencent': CircuitBreaker('tencent', failure_threshold=5, recovery_timeout=60),
            'sina': CircuitBreaker('sina', failure_threshold=3, recovery_timeout=30),
            'backup': CircuitBreaker('backup', failure_threshold=10, recovery_timeout=120)
        }
        
        self.retry_queue = RetryQueue()
        self.scheduler = TaskScheduler(max_concurrent=5)
        self.stats = {
            'success': 0,
            'failed': 0,
            'retried': 0,
            'cached': 0
        }
    
    def fetch_stock(self, stock_code: str, priority: int = 1) -> Optional[Dict]:
        """
        采集单只股票数据（入口方法）
        
        Args:
            stock_code: 股票代码
            priority: 优先级 1-5，越高越优先
        
        Returns:
            股票数据或None
        """
        task = FetchTask(
            task_id=f"{stock_code}_{datetime.now().strftime('%H%M%S')}",
            stock_code=stock_code,
            priority=priority
        )
        
        def execute(task):
            return self._fetch_with_resilience(task)
        
        # 提交到调度器
        if self.scheduler.submit(task, execute):
            # 等待结果（简化版，实际可用Future）
            timeout = 30
            start = time.time()
            while time.time() - start < timeout:
                if task.status == "completed":
                    return task.result
                elif task.status == "failed":
                    break
                time.sleep(0.1)
        
        return None
    
    def _fetch_with_resilience(self, task: FetchTask) -> Optional[Dict]:
        """带保护机制的采集"""
        sources = [
            ('tencent', self._fetch_tencent, 10),
            ('sina', self._fetch_sina, 15),
            ('backup', self._fetch_backup, 20)
        ]
        
        for source_name, fetch_func, timeout in sources:
            cb = self.circuit_breakers[source_name]
            
            try:
                # 使用断路器保护
                data = cb.call(fetch_func, task.stock_code, timeout)
                
                if data and self._validate_data(data):
                    self.stats['success'] += 1
                    logger.info(f"[ResilientFetcher] {task.stock_code} 从 {source_name} 采集成功")
                    return data
                    
            except Exception as e:
                logger.warning(f"[ResilientFetcher] {source_name} 失败: {e}")
                continue
        
        # 所有源失败，尝试缓存
        cached = self._get_cached(task.stock_code)
        if cached:
            self.stats['cached'] += 1
            logger.info(f"[ResilientFetcher] {task.stock_code} 使用缓存数据")
            return cached
        
        # 彻底失败，加入重试队列
        task.error = "All sources failed"
        if task.retry_count < task.max_retry:
            task.retry_count += 1
            self.retry_queue.add(task)
            self.stats['retried'] += 1
        else:
            self.stats['failed'] += 1
            logger.error(f"[ResilientFetcher] {task.stock_code} 彻底失败，已达最大重试次数")
        
        return None
    
    def _fetch_tencent(self, code: str, timeout: int) -> Dict:
        """腾讯数据源（模拟）"""
        # 实际实现调用腾讯API
        import random
        if random.random() < 0.3:  # 30%失败率模拟
            raise Exception("Timeout")
        return {'code': code, 'price': 10.0, 'source': 'tencent'}
    
    def _fetch_sina(self, code: str, timeout: int) -> Dict:
        """新浪数据源（模拟）"""
        return {'code': code, 'price': 10.0, 'source': 'sina'}
    
    def _fetch_backup(self, code: str, timeout: int) -> Dict:
        """备用数据源"""
        return {'code': code, 'price': 10.0, 'source': 'backup'}
    
    def _validate_data(self, data: Dict) -> bool:
        """数据验证"""
        required_fields = ['code', 'price']
        return all(field in data for field in required_fields)
    
    def _get_cached(self, code: str) -> Optional[Dict]:
        """获取缓存数据"""
        # 从数据库读取昨日数据作为缓存
        try:
            conn = sqlite3.connect(
                Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
            )
            cursor = conn.cursor()
            cursor.execute(
                "SELECT close FROM daily WHERE stock_code = ? ORDER BY timestamp DESC LIMIT 1",
                (code,)
            )
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {'code': code, 'price': result[0], 'source': 'cache', 'stale': True}
        except:
            pass
        return None
    
    def process_retry_queue(self):
        """处理重试队列（定时调用）"""
        tasks = self.retry_queue.get_ready_tasks(limit=10)
        
        for task in tasks:
            logger.info(f"[ResilientFetcher] 重试任务 {task.task_id}")
            self.retry_queue.remove(task.task_id)
            self.fetch_stock(task.stock_code, priority=task.priority)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        stats = self.stats.copy()
        stats['retry_queue'] = self.retry_queue.get_stats()
        stats['running_tasks'] = self.scheduler.get_running_count()
        return stats


# 使用示例
if __name__ == '__main__':
    fetcher = ResilientFetcher()
    
    # 模拟采集
    test_stocks = ['sh000001', 'sz399001', 'sh600519']
    
    print("🚀 启动健壮性采集测试\n")
    
    for stock in test_stocks:
        result = fetcher.fetch_stock(stock, priority=3)
        if result:
            print(f"✅ {stock}: {result}")
        else:
            print(f"❌ {stock}: 采集失败，已加入重试队列")
    
    # 处理重试队列
    time.sleep(2)
    print("\n🔄 处理重试队列...")
    fetcher.process_retry_queue()
    
    # 打印统计
    print("\n📊 统计信息:")
    stats = fetcher.get_stats()
    print(f"  成功: {stats['success']}")
    print(f"  失败: {stats['failed']}")
    print(f"  重试: {stats['retried']}")
    print(f"  缓存: {stats['cached']}")
    print(f"  运行中任务: {stats['running_tasks']}")
    print(f"  重试队列: {stats['retry_queue']}")
