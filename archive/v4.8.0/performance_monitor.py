#!/usr/bin/env python3
"""
性能监控指标 - Performance Metrics
监控Agent运行性能，生成统计报告
"""

import time
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import sys

sys.path.insert(0, str(Path(__file__).parent))
from agent_logger import get_logger

log = get_logger("性能监控")


@dataclass
class MetricRecord:
    """指标记录"""
    agent: str
    operation: str
    start_time: float
    end_time: float
    success: bool
    error_message: Optional[str] = None
    
    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path.home() / ".openclaw/workspace/metrics"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self._records: List[MetricRecord] = []
        self._lock = threading.Lock()
        self._current_operations: Dict[str, float] = {}  # {agent_op: start_time}
        
        log.info("性能监控器初始化完成")
    
    def start_operation(self, agent: str, operation: str):
        """开始记录操作"""
        key = f"{agent}:{operation}"
        self._current_operations[key] = time.time()
        log.debug(f"开始操作: {agent}.{operation}")
    
    def end_operation(self, agent: str, operation: str, success: bool = True, error: str = None):
        """结束记录操作"""
        key = f"{agent}:{operation}"
        start_time = self._current_operations.pop(key, time.time())
        end_time = time.time()
        
        record = MetricRecord(
            agent=agent,
            operation=operation,
            start_time=start_time,
            end_time=end_time,
            success=success,
            error_message=error
        )
        
        with self._lock:
            self._records.append(record)
        
        log.debug(f"结束操作: {agent}.{operation}, 耗时: {record.duration_ms:.1f}ms")
        
        # 慢操作告警（超过1秒）
        if record.duration_ms > 1000:
            log.warning(f"慢操作告警: {agent}.{operation} 耗时 {record.duration_ms:.1f}ms")
    
    # 上下文管理器
    class Operation:
        """操作上下文管理器"""
        
        def __init__(self, monitor: 'PerformanceMonitor', agent: str, operation: str):
            self.monitor = monitor
            self.agent = agent
            self.operation = operation
        
        def __enter__(self):
            self.monitor.start_operation(self.agent, self.operation)
            return self
        
        def __exit__(self, exc_type, exc_val, exc_tb):
            success = exc_type is None
            error = str(exc_val) if exc_val else None
            self.monitor.end_operation(self.agent, self.operation, success, error)
    
    def operation(self, agent: str, operation: str):
        """获取操作上下文管理器"""
        return self.Operation(self, agent, operation)
    
    def get_stats(self, agent: str = None, last_n: int = 100) -> Dict:
        """获取统计信息"""
        with self._lock:
            records = self._records[-last_n:] if last_n else self._records
        
        if agent:
            records = [r for r in records if r.agent == agent]
        
        if not records:
            return {"count": 0}
        
        # 计算统计
        durations = [r.duration_ms for r in records]
        successes = sum(1 for r in records if r.success)
        
        # 按操作分组
        ops = {}
        for r in records:
            key = f"{r.agent}.{r.operation}"
            if key not in ops:
                ops[key] = []
            ops[key].append(r.duration_ms)
        
        op_stats = {}
        for op, durs in ops.items():
            op_stats[op] = {
                "count": len(durs),
                "avg_ms": sum(durs) / len(durs),
                "max_ms": max(durs),
                "min_ms": min(durs)
            }
        
        return {
            "total_count": len(records),
            "success_count": successes,
            "error_count": len(records) - successes,
            "success_rate": successes / len(records) * 100,
            "avg_duration_ms": sum(durations) / len(durations),
            "max_duration_ms": max(durations),
            "min_duration_ms": min(durations),
            "operations": op_stats
        }
    
    def generate_report(self) -> str:
        """生成性能报告"""
        stats = self.get_stats(last_n=1000)
        
        report = f"""
📊 性能监控报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

总体统计:
  总操作数: {stats['total_count']}
  成功: {stats['success_count']} ({stats.get('success_rate', 0):.1f}%)
  失败: {stats['error_count']}
  
性能指标:
  平均耗时: {stats.get('avg_duration_ms', 0):.1f}ms
  最大耗时: {stats.get('max_duration_ms', 0):.1f}ms
  最小耗时: {stats.get('min_duration_ms', 0):.1f}ms

各Agent操作统计:
"""
        
        for op, op_stat in stats.get('operations', {}).items():
            report += f"\n  {op}:\n"
            report += f"    次数: {op_stat['count']}, 平均: {op_stat['avg_ms']:.1f}ms\n"
            report += f"    最大: {op_stat['max_ms']:.1f}ms, 最小: {op_stat['min_ms']:.1f}ms\n"
        
        return report
    
    def save_metrics(self):
        """保存指标到文件"""
        filename = self.data_dir / f"metrics_{datetime.now().strftime('%Y%m%d')}.json"
        
        with self._lock:
            data = [asdict(r) for r in self._records]
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        log.info(f"指标已保存: {filename}")
    
    def clear_old_records(self, days: int = 7):
        """清理过期记录"""
        cutoff = time.time() - (days * 24 * 3600)
        
        with self._lock:
            old_count = len(self._records)
            self._records = [r for r in self._records if r.start_time > cutoff]
            new_count = len(self._records)
        
        log.info(f"清理过期记录: {old_count - new_count} 条已删除")


# 全局监控器实例
_monitor: Optional[PerformanceMonitor] = None

def get_monitor() -> PerformanceMonitor:
    """获取全局监控器实例"""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


# 快捷函数
def start_op(agent: str, operation: str):
    """开始操作"""
    get_monitor().start_operation(agent, operation)

def end_op(agent: str, operation: str, success: bool = True, error: str = None):
    """结束操作"""
    get_monitor().end_operation(agent, operation, success, error)

def monitor_op(agent: str, operation: str):
    """获取监控上下文"""
    return get_monitor().operation(agent, operation)


if __name__ == '__main__':
    # 测试性能监控
    monitor = get_monitor()
    
    # 模拟操作
    with monitor.operation("北风", "数据采集"):
        time.sleep(0.1)  # 模拟100ms操作
    
    with monitor.operation("南风", "策略计算"):
        time.sleep(0.05)  # 模拟50ms操作
    
    # 生成报告
    print(monitor.generate_report())
    
    # 保存指标
    monitor.save_metrics()
    
    print("✅ 性能监控测试完成")
