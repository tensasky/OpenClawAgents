#!/usr/bin/env python3
"""
数据库连接池管理 - 增强版
优化数据库连接性能，支持进程锁和自动重试

特性:
- 连接复用，减少开销
- 线程安全
- SQLite WAL模式提升并发性能
- 自动重试机制（处理 database locked 错误）
- 可与 ProcessLock 配合使用
"""

import sqlite3
import threading
import time
import random
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Callable
import sys

sys.path.insert(0, str(Path(__file__).parent))
from agent_logger import get_logger
from process_lock import ProcessLock, acquire_lock

log = get_logger("连接池")


class DatabaseError(Exception):
    """数据库操作错误"""
    pass


class ConnectionPool:
    """
    SQLite连接池 - 增强版
    
    新增特性:
    - WAL模式（Write-Ahead Logging）提升并发
    - 自动重试机制（处理锁等待）
    - 可选进程锁集成
    """
    
    def __init__(self, db_path: Path, max_connections: int = 5, 
                 timeout: int = 30, enable_wal: bool = True,
                 retry_count: int = 5, retry_delay: float = 0.5):
        """
        初始化连接池
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数
            timeout: 连接超时时间（秒）
            enable_wal: 启用WAL模式提升并发
            retry_count: 锁冲突重试次数
            retry_delay: 重试延迟（秒）
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        self.enable_wal = enable_wal
        self.retry_count = retry_count
        self.retry_delay = retry_delay
        
        self._pool: Dict[int, dict] = {}
        self._lock = threading.Lock()
        self._created_count = 0
        
        # 启用WAL模式
        if self.enable_wal:
            self._enable_wal_mode()
        
        log.info(f"连接池初始化: {db_path.name}, 最大连接: {max_connections}, WAL: {enable_wal}")
    
    def _enable_wal_mode(self):
        """启用WAL模式提升并发性能"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")  # 30秒超时
            conn.close()
            log.debug("WAL模式已启用")
        except Exception as e:
            log.warning(f"启用WAL模式失败: {e}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        thread_id = threading.get_ident()
        
        with self._lock:
            if thread_id in self._pool:
                conn_info = self._pool[thread_id]
                if self._is_connection_healthy(conn_info["conn"]):
                    conn_info["last_used"] = time.time()
                    return conn_info["conn"]
                else:
                    self._close_connection(conn_info["conn"])
                    del self._pool[thread_id]
            
            self._cleanup_expired()
            
            conn = self._create_connection()
            self._pool[thread_id] = {
                "conn": conn,
                "last_used": time.time(),
                "created_at": time.time()
            }
            self._created_count += 1
            
            log.debug(f"创建新连接: 线程{thread_id}, 总计: {self._created_count}")
            return conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """创建新连接"""
        conn = sqlite3.connect(
            self.db_path, 
            timeout=self.timeout,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row
        
        # 优化参数
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        return conn
    
    def _is_connection_healthy(self, conn: sqlite3.Connection) -> bool:
        """检查连接是否健康"""
        try:
            conn.execute("SELECT 1")
            return True
        except:
            return False
    
    def _close_connection(self, conn: sqlite3.Connection):
        """安全关闭连接"""
        try:
            conn.close()
        except Exception as e:
            log.warning(f"关闭连接失败: {e}")
    
    def _cleanup_expired(self):
        """清理过期连接"""
        current_time = time.time()
        expired = [tid for tid, info in self._pool.items() 
                   if current_time - info["last_used"] > self.timeout]
        
        for tid in expired:
            self._close_connection(self._pool[tid]["conn"])
            del self._pool[tid]
    
    def release_connection(self, conn: sqlite3.Connection):
        """释放连接（标记为可用）"""
        pass
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for tid, info in list(self._pool.items()):
                self._close_connection(info["conn"])
            self._pool.clear()
            log.info(f"连接池已关闭，共创建 {self._created_count} 个连接")
    
    def get_stats(self) -> dict:
        """获取连接池统计"""
        return {
            "total_created": self._created_count,
            "active_connections": len(self._pool),
            "max_connections": self.max_connections,
            "db_path": str(self.db_path),
            "wal_enabled": self.enable_wal
        }


# 全局连接池
_pools: Dict[str, ConnectionPool] = {}
_pools_lock = threading.Lock()


def get_pool(db_path: Path, **kwargs) -> ConnectionPool:
    """获取或创建连接池"""
    db_key = str(db_path.resolve())
    
    with _pools_lock:
        if db_key not in _pools:
            _pools[db_key] = ConnectionPool(db_path, **kwargs)
        return _pools[db_key]


def close_all_pools():
    """关闭所有连接池"""
    with _pools_lock:
        for pool in _pools.values():
            pool.close_all()
        _pools.clear()
    log.info("所有连接池已关闭")


# ============ 增强版数据库操作 ============

class DatabaseOperations:
    """数据库操作包装器 - 带自动重试"""
    
    def __init__(self, db_path: Path, use_process_lock: bool = True,
                 lock_name: str = None):
        """
        初始化
        
        Args:
            db_path: 数据库路径
            use_process_lock: 是否使用进程锁
            lock_name: 进程锁名称（默认使用数据库名）
        """
        self.db_path = db_path
        self.pool = get_pool(db_path)
        self.use_process_lock = use_process_lock
        self.lock_name = lock_name or f"db_{db_path.stem}"
    
    def execute_with_retry(self, operation: Callable, 
                           max_retries: int = 5) -> any:
        """
        执行数据库操作（带自动重试）
        
        Args:
            operation: 数据库操作函数，接受cursor参数
            max_retries: 最大重试次数
        
        Returns:
            操作结果
        
        Raises:
            DatabaseError: 重试次数耗尽
        """
        last_error = None
        
        for attempt in range(max_retries):
            conn = None
            try:
                conn = self.pool.get_connection()
                cursor = conn.cursor()
                
                result = operation(cursor)
                conn.commit()
                return result
                
            except sqlite3.OperationalError as e:
                last_error = e
                error_msg = str(e).lower()
                
                if "locked" in error_msg:
                    # 数据库被锁，等待后重试
                    wait_time = (attempt + 1) * self.retry_delay + random.uniform(0, 0.5)
                    log.warning(f"数据库锁定，{attempt + 1}/{max_retries}，等待 {wait_time:.1f}s...")
                    time.sleep(wait_time)
                elif "busy" in error_msg:
                    wait_time = (attempt + 1) * 1.0
                    log.warning(f"数据库繁忙，{attempt + 1}/{max_retries}，等待 {wait_time:.1f}s...")
                    time.sleep(wait_time)
                else:
                    raise DatabaseError(f"数据库错误: {e}")
                    
            except sqlite3.Error as e:
                raise DatabaseError(f"数据库错误: {e}")
                
            finally:
                if conn:
                    self.pool.release_connection(conn)
        
        raise DatabaseError(f"重试{max_retries}次后仍失败: {last_error}")
    
    def execute(self, sql: str, params: tuple = None) -> list:
        """执行SQL并返回结果"""
        def op(cursor):
            if params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor.fetchall()
        
        return self.execute_with_retry(op)
    
    def execute_many(self, sql: str, params_list: list) -> int:
        """批量执行SQL"""
        def op(cursor):
            cursor.executemany(sql, params_list)
            return cursor.rowcount
        
        return self.execute_with_retry(op)
    
    def insert_or_update(self, table: str, data: dict, 
                         primary_key: str = "id") -> int:
        """插入或更新数据"""
        columns = list(data.keys())
        placeholders = ["?"] * len(columns)
        sql = f"""
            INSERT INTO {table} ({','.join(columns)})
            VALUES ({','.join(placeholders)})
            ON CONFLICT({primary_key}) DO UPDATE SET
            {','.join([f"{k}=excluded.{k}" for k in columns if k != primary_key])}
        """
        
        def op(cursor):
            cursor.execute(sql, tuple(data.values()))
            return cursor.lastrowid
        
        return self.execute_with_retry(op)


# 上下文管理器
class DBConnection:
    """数据库连接上下文管理器"""
    
    def __init__(self, db_path: Path, use_lock: bool = False, 
                 lock_name: str = None, lock_timeout: int = 30):
        self.db_path = db_path
        self.use_lock = use_lock
        self.lock_name = lock_name or f"db_{db_path.stem}"
        self.lock_timeout = lock_timeout
        self.process_lock = None
        self.conn = None
    
    def __enter__(self) -> sqlite3.Connection:
        # 获取进程锁
        if self.use_lock:
            self.process_lock = ProcessLock(self.lock_name, timeout=self.lock_timeout)
            if not self.process_lock.acquire():
                raise TimeoutError(f"获取数据库锁 '{self.lock_name}' 超时")
        
        # 获取连接
        pool = get_pool(self.db_path)
        self.conn = pool.get_connection()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            try:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            except:
                pass
            
            pool = get_pool(self.db_path)
            pool.release_connection(self.conn)
        
        # 释放进程锁
        if self.process_lock:
            self.process_lock.release()
        
        return False


def get_db_connection(db_path: Path, **kwargs) -> DBConnection:
    """获取数据库连接（上下文管理器）"""
    return DBConnection(db_path, **kwargs)


# ============ 便捷函数 ============

def execute_with_lock(db_path: Path, sql: str, params: tuple = None,
                       lock_name: str = None) -> list:
    """
    带锁执行的便捷函数
    
    Example:
        result = execute_with_lock(
            db_path,
            "SELECT * FROM stocks WHERE code = ?",
            ("sh600519",),
            lock_name="beifeng_collect"
        )
    """
    with get_db_connection(db_path, use_lock=True, lock_name=lock_name) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.fetchall()


def execute_write_with_lock(db_path: Path, sql: str, params: tuple = None,
                             lock_name: str = None) -> int:
    """带锁执行的写入操作"""
    with get_db_connection(db_path, use_lock=True, lock_name=lock_name) as conn:
        cursor = conn.cursor()
        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)
        return cursor.lastrowid or cursor.rowcount


if __name__ == '__main__':
    # 测试
    from pathlib import Path
    
    test_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
    
    print("🧪 数据库连接池测试")
    
    if test_db.exists():
        # 测试1: 基本查询
        print("\n📌 测试1: 基本查询")
        db = DatabaseOperations(test_db, use_process_lock=False)
        try:
            result = db.execute("SELECT COUNT(*) as cnt FROM daily")
            print(f"   日线数据: {result[0]['cnt']} 条")
        except Exception as e:
            print(f"   ⚠️ {e}")
        
        # 测试2: 带锁查询
        print("\n📌 测试2: 带进程锁查询")
        try:
            result = execute_with_lock(test_db, "SELECT COUNT(*) as cnt FROM daily",
                                        lock_name="test_lock")
            print(f"   日线数据: {result[0]['cnt']} 条")
        except Exception as e:
            print(f"   ⚠️ {e}")
        
        # 测试3: 连接池统计
        print("\n📌 测试3: 连接池统计")
        pool = get_pool(test_db)
        stats = pool.get_stats()
        print(f"   {stats}")
        
        print("\n✅ 测试完成")
    else:
        print(f"⚠️ 测试数据库不存在: {test_db}")
