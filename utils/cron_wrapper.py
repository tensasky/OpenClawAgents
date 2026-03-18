#!/usr/bin/env python3
"""
Cron脚本锁包装器 - Python版本
用于没有flock的macOS环境

使用方法:
    # 在bash脚本中调用:
    python3 /path/to/cron_wrapper.py --lock "lock_name" --timeout 60 -- python3 your_script.py
    
    # 或者:
    python3 /path/to/cron_wrapper.py --lock "lock_name" --timeout 60 -- bash your_script.sh
"""

import os
import sys
import time
import fcntl
import argparse
import subprocess
from pathlib import Path

# 配置
LOCK_DIR = Path.home() / "Documents/OpenClawAgents" / ".locks"
LOCK_DIR.mkdir(exist_ok=True)


class CronLock:
    """Cron锁管理器"""
    
    def __init__(self, lock_name: str, timeout: int = 60):
        self.lock_name = lock_name.replace("/", "_").replace(":", "_")
        self.lock_file = LOCK_DIR / f"{self.lock_name}.lock"
        self.timeout = timeout
        self._fd = None
        self._acquired = False
    
    def acquire(self) -> bool:
        """获取锁"""
        try:
            # 创建锁文件
            self._fd = os.open(str(self.lock_file), os.O_CREAT | os.O_RDWR)
            
            start_time = time.time()
            while True:
                try:
                    # 非阻塞获取排他锁
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self._acquired = True
                    # 写入PID
                    os.write(self._fd, f"{os.getpid()}\n".encode())
                    os.ftruncate(self._fd, os.path.getsize(self.lock_file))
                    return True
                except (BlockingIOError, OSError):
                    elapsed = time.time() - start_time
                    if elapsed >= self.timeout:
                        os.close(self._fd)
                        self._fd = None
                        return False
                    time.sleep(0.5)
        except Exception as e:
            print(f"获取锁错误: {e}", file=sys.stderr)
            return False
    
    def release(self):
        """释放锁"""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except:
                pass
            finally:
                self._fd = None
                self._acquired = False
                try:
                    self.lock_file.unlink()
                except:
                    pass
    
    def __enter__(self):
        if not self.acquire():
            raise TimeoutError(f"获取锁 '{self.lock_name}' 超时（{self.timeout}秒）")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False


def check_lock(lock_name: str) -> str:
    """检查锁状态"""
    lock_name = lock_name.replace("/", "_").replace(":", "_")
    lock_file = LOCK_DIR / f"{lock_name}.lock"
    
    if not lock_file.exists():
        return "available"
    
    try:
        fd = os.open(str(lock_file), os.O_RDWR)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
            return "available"
        except (BlockingIOError, OSError):
            os.close(fd)
            try:
                pid = lock_file.read_text().strip()
                return f"locked (PID: {pid})"
            except:
                return "locked"
    except:
        return "error"


def main():
    parser = argparse.ArgumentParser(description="Cron锁包装器")
    parser.add_argument("--lock", "-l", required=True, help="锁名称")
    parser.add_argument("--timeout", "-t", type=int, default=60, help="超时时间(秒)")
    parser.add_argument("--check", "-c", action="store_true", help="仅检查锁状态")
    parser.add_argument("--release", "-r", action="store_true", help="释放锁")
    parser.add_argument("--", dest="separator", default="--", help="分隔符")
    parser.add_argument("command", nargs="*", help="要执行的命令")
    
    args = parser.parse_args()
    
    # 检查模式
    if args.check:
        status = check_lock(args.lock)
        print(status)
        return
    
    # 释放模式
    if args.release:
        lock = CronLock(args.lock)
        lock.release()
        print(f"锁 '{args.lock}' 已释放")
        return
    
    # 执行模式
    if not args.command:
        print("错误: 请指定要执行的命令", file=sys.stderr)
        sys.exit(1)
    
    lock = CronLock(args.lock, args.timeout)
    
    try:
        if not lock.acquire():
            print(f"错误: 获取锁 '{args.lock}' 超时", file=sys.stderr)
            sys.exit(1)
        
        print(f"🔒 获取锁成功: {args.lock}")
        
        # 执行命令
        result = subprocess.run(args.command)
        sys.exit(result.returncode)
        
    finally:
        lock.release()
        print(f"🔓 释放锁: {args.lock}")


if __name__ == '__main__':
    main()
