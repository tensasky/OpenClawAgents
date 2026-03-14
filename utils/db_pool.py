#!/usr/bin/env python3
"""
数据库连接池管理 - Database Connection Pool
优化数据库连接性能，避免频繁创建/关闭连接
"""

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent))
from agent_logger import get_logger

log = get_logger("连接池")


class ConnectionPool:
    """
    SQLite连接池
    
    特性:
    - 连接复用，减少开销
    - 线程安全
    - 自动回收超时连接
    - 连接健康检查
    """
    
    def __init__(self, db_path: Path, max_connections: int = 5, timeout: int = 300):
        """
        初始化连接池
        
        Args:
            db_path: 数据库文件路径
            max_connections: 最大连接数
            timeout: 连接超时时间（秒）
        """
        self.db_path = db_path
        self.max_connections = max_connections
        self.timeout = timeout
        
        self._pool: Dict[int, dict] = {}  # {thread_id: {"conn": conn, "last_used": timestamp}}
        self._lock = threading.Lock()
        self._created_count = 0
        
        log.info(f"连接池初始化: {db_path.name}, 最大连接数: {max_connections}")
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        thread_id = threading.get_ident()
        
        with self._lock:
            # 检查当前线程是否已有连接
            if thread_id in self._pool:
                conn_info = self._pool[thread_id]
                # 检查连接是否健康
                if self._is_connection_healthy(conn_info["conn"]):
                    conn_info["last_used"] = time.time()
                    return conn_info["conn"]
                else:
                    # 连接不健康，关闭并重新创建
                    self._close_connection(conn_info["conn"])
                    del self._pool[thread_id]
            
            # 清理过期连接
            self._cleanup_expired()
            
            # 创建新连接
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            self._pool[thread_id] = {
                "conn": conn,
                "last_used": time.time(),
                "created_at": time.time()
            }
            self._created_count += 1
            
            log.debug(f"创建新连接: 线程{thread_id}, 总计创建: {self._created_count}")
            return conn
    
    def release_connection(self, conn: sqlite3.Connection):
        """释放连接（实际不归还给池，SQLite连接是线程专属的）"""
        # SQLite连接是线程专属的，无法真正归还到池
        # 这里只是标记为可用
        pass
    
    def close_all(self):
        """关闭所有连接"""
        with self._lock:
            for thread_id, conn_info in list(self._pool.items()):
                self._close_connection(conn_info["conn"])
            self._pool.clear()
            log.info(f"连接池已关闭，共释放 {self._created_count} 个连接")
    
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
        expired_threads = []
        
        for thread_id, conn_info in self._pool.items():
            if current_time - conn_info["last_used"] > self.timeout:
                expired_threads.append(thread_id)
        
        for thread_id in expired_threads:
            self._close_connection(self._pool[thread_id]["conn"])
            del self._pool[thread_id]
            log.debug(f"清理过期连接: 线程{thread_id}")
    
    def get_stats(self) -> dict:
        """获取连接池统计信息"""
        return {
            "total_created": self._created_count,
            "active_connections": len(self._pool),
            "max_connections": self.max_connections,
            "db_path": str(self.db_path)
        }


# 全局连接池实例
_pools: Dict[str, ConnectionPool] = {}


def get_pool(db_path: Path) -> ConnectionPool:
    """获取或创建连接池"""
    db_key = str(db_path)
    if db_key not in _pools:
        _pools[db_key] = ConnectionPool(db_path)
    return _pools[db_key]


def close_all_pools():
    """关闭所有连接池"""
    for pool in _pools.values():
        pool.close_all()
    _pools.clear()
    log.info("所有连接池已关闭")


# 上下文管理器
class DBConnection:
    """数据库连接上下文管理器"""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.conn = None
    
    def __enter__(self) -> sqlite3.Connection:
        pool = get_pool(self.db_path)
        self.conn = pool.get_connection()
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 不关闭连接，归还给连接池
        if self.conn:
            get_pool(self.db_path).release_connection(self.conn)


# 快捷函数
def get_db_connection(db_path: Path) -> DBConnection:
    """获取数据库连接（上下文管理器）"""
    return DBConnection(db_path)


if __name__ == '__main__':
    # 测试连接池
    from pathlib import Path
    
    test_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
    
    if test_db.exists():
        # 测试基本功能
        with get_db_connection(test_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM daily")
            count = cursor.fetchone()[0]
            log.info(f"测试查询: {count}条记录")
        
        # 查看统计
        pool = get_pool(test_db)
        stats = pool.get_stats()
        log.info(f"连接池统计: {stats}")
        
        # 关闭连接池
        close_all_pools()
        print("✅ 连接池测试完成")
    else:
        print("⚠️ 测试数据库不存在")
