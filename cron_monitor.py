#!/usr/bin/env python3
"""
Cron任务监控系统
确保定时任务正常运行，自动处理崩溃和冲突

功能:
- 监控进程状态
- 检测并解决锁冲突
- 自动重启失败任务
- 记录运行日志
"""

import os
import sys
import time
import json
import signal
import subprocess
import psutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 配置
SCRIPT_DIR = Path.home() / "Documents/OpenClawAgents"
LOG_DIR = SCRIPT_DIR / "logs" / "cron_monitor"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 监控配置
MONITOR_INTERVAL = 60  # 检查间隔（秒）
MAX_RESTART_PER_HOUR = 3  # 每小时最大重启次数
LOCK_CHECK_INTERVAL = 10  # 锁检查间隔（秒）


@dataclass
class CronTask:
    """定时任务配置"""
    name: str
    script_path: str
    working_dir: str
    interval: int  # 运行间隔（秒）
    enabled: bool = True
    max_runtime: int = 600  # 最大运行时间（秒）
    restart_cooldown: int = 300  # 重启冷却时间（秒）


@dataclass
class TaskStatus:
    """任务状态"""
    name: str
    pid: Optional[int]
    status: str  # running, stopped, crashed, idle
    start_time: Optional[datetime]
    last_run: Optional[datetime]
    last_exit_code: Optional[int]
    restart_count: int
    error_message: Optional[str]


class CronMonitor:
    """Cron任务监控器"""
    
    def __init__(self):
        self.tasks: Dict[str, CronTask] = {}
        self.status: Dict[str, TaskStatus] = {}
        self.restart_history: Dict[str, List[datetime]] = {}
        self.running_processes: Dict[str, subprocess.Popen] = {}
        
        # 加载任务配置
        self._load_tasks()
        
        # 创建状态文件
        self.status_file = LOG_DIR / "status.json"
        self._load_status()
    
    def _load_tasks(self):
        """加载任务配置"""
        # 定义需要监控的任务
        task_configs = [
            CronTask(
                name="beifeng_collect",
                script_path=str(SCRIPT_DIR / "cron_beifeng_collect.sh"),
                working_dir=str(SCRIPT_DIR / "beifeng"),
                interval=3600,
                max_runtime=1800
            ),
            CronTask(
                name="beifeng_minute_hf",
                script_path=str(SCRIPT_DIR / "cron_minute_hf.sh"),
                working_dir=str(SCRIPT_DIR / "beifeng"),
                interval=300,
                max_runtime=180
            ),
            CronTask(
                name="daily_report",
                script_path=str(SCRIPT_DIR / "cron_daily.sh"),
                working_dir=str(SCRIPT_DIR),
                interval=86400,
                max_runtime=3600
            ),
            CronTask(
                name="limit_up_monitor",
                script_path=str(SCRIPT_DIR / "cron_limit_up.sh"),
                working_dir=str(SCRIPT_DIR / "nanfeng"),
                interval=1800,
                max_runtime=600
            ),
        ]
        
        for task in task_configs:
            self.tasks[task.name] = task
            self.restart_history[task.name] = []
            
            # 初始化状态
            if task.name not in self.status:
                self.status[task.name] = TaskStatus(
                    name=task.name,
                    pid=None,
                    status="idle",
                    start_time=None,
                    last_run=None,
                    last_exit_code=None,
                    restart_count=0,
                    error_message=None
                )
    
    def _load_status(self):
        """从文件加载状态"""
        if self.status_file.exists():
            try:
                data = json.loads(self.status_file.read_text())
                # 转换datetime
                for name, s in data.items():
                    if s.get("start_time"):
                        s["start_time"] = datetime.fromisoformat(s["start_time"])
                    if s.get("last_run"):
                        s["last_run"] = datetime.fromisoformat(s["last_run"])
                    self.status[name] = TaskStatus(**s)
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_status(self):
        """保存状态到文件"""
        data = {}
        for name, s in self.status.items():
            d = asdict(s)
            # 转换datetime为字符串
            if d.get("start_time"):
                d["start_time"] = d["start_time"].isoformat()
            if d.get("last_run"):
                d["last_run"] = d["last_run"].isoformat()
            data[name] = d
        
        self.status_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def check_and_start_task(self, task_name: str) -> bool:
        """
        检查并启动任务
        
        Returns:
            True if task was started
        """
        task = self.tasks.get(task_name)
        if not task or not task.enabled:
            return False
        
        status = self.status[task_name]
        
        # 检查是否已经在运行
        if status.pid and status.status == "running":
            try:
                proc = psutil.Process(status.pid)
                if proc.is_running():
                    # 检查是否超时
                    if status.start_time:
                        elapsed = (datetime.now() - status.start_time).total_seconds()
                        if elapsed > task.max_runtime:
                            print(f"⚠️ 任务 {task_name} 运行超时 {elapsed:.0f}s，终止")
                            proc.terminate()
                            time.sleep(2)
                            if proc.is_running():
                                proc.kill()
                            status.status = "crashed"
                            status.error_message = "运行超时"
                    return False  # 已在运行
            except psutil.NoSuchProcess:
                pass
        
        # 检查重启冷却
        if status.last_run:
            cooldown = (datetime.now() - status.last_run).total_seconds()
            if cooldown < task.restart_cooldown:
                print(f"⏸️ 任务 {task_name} 冷却中 ({cooldown:.0f}s)")
                return False
        
        # 检查重启频率
        self._cleanup_restart_history(task_name)
        recent_restarts = len(self.restart_history[task_name])
        if recent_restarts >= MAX_RESTART_PER_HOUR:
            print(f"⛔ 任务 {task_name} 重启过于频繁，跳过")
            return False
        
        # 启动任务
        return self._start_task(task_name)
    
    def _start_task(self, task_name: str) -> bool:
        """启动任务"""
        task = self.tasks[task_name]
        status = self.status[task_name]
        
        print(f"🚀 启动任务: {task_name}")
        
        try:
            # 使用nohup后台运行
            log_file = LOG_DIR / f"{task_name}.log"
            
            with open(log_file, "a") as f:
                f.write(f"\n{'='*50}\n")
                f.write(f"启动时间: {datetime.now().isoformat()}\n")
                f.write(f"脚本: {task.script_path}\n")
                
                proc = subprocess.Popen(
                    ["/bin/bash", task.script_path],
                    cwd=task.working_dir,
                    stdout=f,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )
            
            status.pid = proc.pid
            status.status = "running"
            status.start_time = datetime.now()
            status.error_message = None
            
            # 记录重启
            self.restart_history[task_name].append(datetime.now())
            
            print(f"   PID: {proc.pid}")
            return True
            
        except Exception as e:
            print(f"   ❌ 启动失败: {e}")
            status.status = "crashed"
            status.error_message = str(e)
            return False
    
    def check_process_status(self, task_name: str):
        """检查进程状态"""
        task = self.tasks.get(task_name)
        if not task:
            return
        
        status = self.status[task_name]
        
        if not status.pid:
            status.status = "idle"
            return
        
        try:
            proc = psutil.Process(status.pid)
            
            if proc.is_running():
                # 检查状态
                if proc.status() == psutil.STATUS_ZOMBIE:
                    status.status = "zombie"
                else:
                    status.status = "running"
                
                # 检查是否超时
                if status.start_time:
                    elapsed = (datetime.now() - status.start_time).total_seconds()
                    if elapsed > task.max_runtime:
                        print(f"⚠️ 任务 {task_name} 超时，终止")
                        try:
                            proc.terminate()
                            time.sleep(2)
                            if proc.is_running():
                                proc.kill()
                        except:
                            pass
                        status.status = "crashed"
            else:
                # 进程已结束
                status.status = "stopped"
                status.last_run = datetime.now()
                status.start_time = None
                
                # 获取退出码
                try:
                    status.last_exit_code = proc.wait(timeout=1)
                except:
                    status.last_exit_code = -1
                
                status.pid = None
                
        except psutil.NoSuchProcess:
            status.status = "stopped"
            status.last_run = datetime.now()
            status.start_time = None
            status.pid = None
    
    def _cleanup_restart_history(self, task_name: str):
        """清理过期的重启记录"""
        cutoff = datetime.now() - timedelta(hours=1)
        self.restart_history[task_name] = [
            t for t in self.restart_history[task_name]
            if t > cutoff
        ]
    
    def get_status_report(self) -> str:
        """获取状态报告"""
        lines = ["📊 Cron监控状态", "=" * 30]
        
        for name, task in self.tasks.items():
            status = self.status[name]
            status_str = {
                "running": "🟢 运行中",
                "idle": "⚪ 空闲",
                "stopped": "🔴 已停止",
                "crashed": "💥 崩溃",
                "zombie": "🧟 僵尸"
            }.get(status.status, status.status)
            
            last_run = status.last_run.strftime("%H:%M:%S") if status.last_run else "无"
            
            lines.append(f"\n{name}:")
            lines.append(f"  状态: {status_str}")
            lines.append(f"  PID: {status.pid or '无'}")
            lines.append(f"  上次运行: {last_run}")
            if status.error_message:
                lines.append(f"  错误: {status.error_message}")
        
        return "\n".join(lines)
    
    def run_once(self):
        """运行一次检查"""
        print(f"\n{'='*40}")
        print(f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        for task_name in self.tasks:
            # 检查进程状态
            self.check_process_status(task_name)
            
            # 尝试启动
            self.check_and_start_task(task_name)
        
        # 保存状态
        self._save_status()
        
        # 输出状态
        print(self.get_status_report())


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Cron任务监控")
    parser.add_argument("--once", action="store_true", help="只运行一次")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--start", type=str, help="启动指定任务")
    parser.add_argument("--stop", type=str, help="停止指定任务")
    args = parser.parse_args()
    
    monitor = CronMonitor()
    
    if args.status:
        print(monitor.get_status_report())
        return
    
    if args.start:
        monitor._start_task(args.start)
        return
    
    if args.stop:
        status = monitor.status.get(args.stop)
        if status and status.pid:
            try:
                proc = psutil.Process(status.pid)
                proc.terminate()
                print(f"✅ 任务 {args.stop} 已终止")
            except:
                print(f"❌ 无法终止任务")
        return
    
    if args.once:
        monitor.run_once()
    else:
        # 循环运行
        print("🔄 启动Cron监控...")
        try:
            while True:
                monitor.run_once()
                time.sleep(MONITOR_INTERVAL)
        except KeyboardInterrupt:
            print("\n👋 监控已停止")


if __name__ == '__main__':
    main()
