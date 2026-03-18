#!/usr/bin/env python3
"""
跨进程数据库锁管理器
解决多个cron脚本同时访问SQLite数据库的冲突问题

使用方法:
    from process_lock import ProcessLock
    
    with ProcessLock("my_script"):
        # 你的数据库操作
        ...
"""

import os
import sys
import time
import fcntl
import signal
import tempfile
from pathlib import Path
from datetime import datetime
from contextlib import contextmanager
from typing import Optional

# 配置
LOCK_DIR = Path.home() / "Documents/OpenClawAgents" / ".locks"
LOCK_DIR.mkdir(exist_ok=True)

# 默认配置
DEFAULT_TIMEOUT = 30  # 获取锁超时时间（秒）
DEFAULT_RETRY_INTERVAL = 0.5  # 重试间隔（秒）
MAX_RETRIES = 3  # 最大重试次数


class ProcessLock:
    """
    进程锁上下文管理器
    
    特性:
    - 跨进程锁（使用flock）
    - 自动重试机制
    - 超时保护
    - 可重入锁（同一进程内）
    """
    
    _local_locks = {}  # 进程本地锁记录
    
    def __init__(self, lock_name: str, timeout: int = DEFAULT_TIMEOUT, 
                 retry_interval: float = DEFAULT_RETRY_INTERVAL,
                 max_retries: int = MAX_RETRIES):
        """
        初始化进程锁
        
        Args:
            lock_name: 锁名称（用于生成锁文件）
            timeout: 获取锁超时时间（秒）
            retry_interval: 重试间隔（秒）
            max_retries: 最大重试次数
        """
        self.lock_name = lock_name.replace("/", "_").replace(":", "_")
        self.lock_file = LOCK_DIR / f"{self.lock_name}.lock"
        self.timeout = timeout
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self._fd: Optional[int] = None
        self._acquired = False
    
    def acquire(self) -> bool:
        """获取锁"""
        # 检查进程本地是否已持有锁（可重入）
        if self.lock_name in ProcessLock._local_locks:
            ProcessLock._local_locks[self.lock_name] += 1
            self._acquired = True
            return True
        
        # 打开锁文件
        self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
        
        start_time = time.time()
        retries = 0
        
        while True:
            try:
                # 非阻塞获取排他锁
                fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                self._acquired = True
                ProcessLock._local_locks[self.lock_name] = 1
                return True
            except (BlockingIOError, OSError):
                retries += 1
                elapsed = time.time() - start_time
                
                if elapsed >= self.timeout:
                    os.close(self._fd)
                    self._fd = None
                    return False
                
                if retries >= self.max_retries * 10:  # 限制警告频率
                    pass  # 静默等待
                
                time.sleep(self.retry_interval)
    
    def release(self):
        """释放锁"""
        # 进程本地锁计数
        if self.lock_name in ProcessLock._local_locks:
            ProcessLock._local_locks[self.lock_name] -= 1
            if ProcessLock._local_locks[self.lock_name] > 0:
                return  # 还持有锁，不真正释放
        
        if self._acquired and self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except:
                pass
            finally:
                self._fd = None
                self._acquired = False
                if self.lock_name in ProcessLock._local_locks:
                    del ProcessLock._local_locks[self.lock_name]
    
    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"获取锁 '{self.lock_name}' 超时（{self.timeout}秒）")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


@contextmanager
def acquire_lock(lock_name: str, timeout: int = DEFAULT_TIMEOUT, 
                 on_waiting=None, on_failed=None):
    """
    获取进程锁的便捷函数
    
    Args:
        lock_name: 锁名称
        timeout: 超时时间
        on_waiting: 等待锁时的回调函数
        on_failed: 获取锁失败时的回调函数
    
    Example:
        with acquire_lock("beifeng_collect") as locked:
            if locked:
                # 执行任务
                ...
    """
    lock = ProcessLock(lock_name, timeout)
    
    class LockResult:
        def __init__(self, success):
            self.success = success
    
    if lock.acquire():
        try:
            yield True
        finally:
            lock.release()
    else:
        if on_failed:
            on_failed()
        yield False


def check_lock(lock_name: str) -> bool:
    """
    检查锁是否被占用
    
    Args:
        lock_name: 锁名称
    
    Returns:
        True if lock is held by another process
    """
    lock_file = LOCK_DIR / f"{lock_name.replace('/', '_').replace(':', '_')}.lock"
    
    if not lock_file.exists():
        return False
    
    try:
        fd = os.open(str(lock_file), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return False  # 锁可用
        except (BlockingIOError, OSError):
            os.close(fd)
            return True  # 锁被占用
    except:
        return False


def get_lock_info(lock_name: str) -> dict:
    """获取锁的详细信息"""
    lock_file = LOCK_DIR / f"{lock_name.replace('/', '_').replace(':', '_')}.lock"
    
    if not lock_file.exists():
        return {"exists": False, "locked": False}
    
    stat = lock_file.stat()
    is_locked = check_lock(lock_name)
    
    return {
        "exists": True,
        "locked": is_locked,
        "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "pid": stat.st_nlink  # 硬链接数（持有锁的进程）
    }


def cleanup_stale_locks(max_age_hours: int = 24):
    """清理过期的锁文件（锁持有进程已崩溃）"""
    import glob
    
    cleaned = 0
    for lock_file in LOCK_DIR.glob("*.lock"):
        # 检查文件是否被锁定
        if not check_lock(lock_file.stem):
            # 锁文件存在但没有进程持有，删除
            age_hours = (time.time() - lock_file.stat().st_mtime) / 3600
            if age_hours > max_age_hours:
                lock_file.unlink()
                cleaned += 1
    
    return cleaned


if __name__ == '__main__':
    # 测试
    print("🧪 进程锁测试")
    
    # 测试1: 基本锁
    print("\n📌 测试1: 基本锁")
    with ProcessLock("test_lock", timeout=5) as locked:
        if locked:
            print("   ✅ 锁获取成功")
            time.sleep(1)
        else:
            print("   ❌ 锁获取失败")
    
    # 测试2: 检查锁状态
    print("\n📌 测试2: 检查锁状态")
    info = get_lock_info("test_lock")
    print(f"   锁状态: {info}")
    
    # 测试3: 清理过期锁
    print("\n📌 测试3: 清理过期锁")
    cleaned = cleanup_stale_locks()
    print(f"   清理了 {cleaned} 个过期锁")
    
    print("\n✅ 测试完成")
