#!/usr/bin/env python3
"""
健壮性系统监控面板
实时显示断路器状态、重试队列、任务执行情况
"""

import sys
import time
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/beifeng')

from resilient_fetcher import ResilientFetcher, CircuitState
from datetime import datetime

def monitor_status():
    """监控系统状态"""
    fetcher = ResilientFetcher()
    
    print("\033[2J\033[H")  # 清屏
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║          🛡️ 健壮性数据采集系统 - 实时监控面板                   ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 1. 断路器状态
    print("📊 断路器状态:")
    print("-" * 70)
    for name, cb in fetcher.circuit_breakers.items():
        state_emoji = {
            CircuitState.CLOSED: "🟢",
            CircuitState.OPEN: "🔴",
            CircuitState.HALF_OPEN: "🟡"
        }.get(cb.state, "⚪")
        
        print(f"  {state_emoji} {name:10s} | 状态: {cb.state.value:12s} | "
              f"失败: {cb.failure_count}/{cb.failure_threshold}")
    print()
    
    # 2. 任务统计
    print("📈 采集统计:")
    print("-" * 70)
    stats = fetcher.get_stats()
    print(f"  ✅ 成功:    {stats['success']:6d}")
    print(f"  📦 缓存:    {stats['cached']:6d}")
    print(f"  🔄 重试:    {stats['retried']:6d}")
    print(f"  ❌ 失败:    {stats['failed']:6d}")
    print(f"  🏃 运行中:  {stats['running_tasks']:6d}")
    print()
    
    # 3. 重试队列
    print("⏳ 重试队列:")
    print("-" * 70)
    retry_stats = stats['retry_queue']
    print(f"  待处理: {retry_stats['pending']} 只")
    print(f"  平均重试: {retry_stats['avg_retry']:.1f} 次")
    print(f"  彻底失败: {retry_stats['permanently_failed']} 只")
    print()
    
    # 4. 系统健康度
    total = stats['success'] + stats['cached'] + stats['failed'] + stats['retried']
    if total > 0:
        health = (stats['success'] + stats['cached']) / total * 100
        health_emoji = "🟢" if health > 90 else "🟡" if health > 70 else "🔴"
        print(f"💚 系统健康度: {health_emoji} {health:.1f}%")
    print()
    
    print("═" * 70)
    print("提示: 按 Ctrl+C 退出监控")
    print("═" * 70)

def continuous_monitor(interval: int = 5):
    """持续监控"""
    try:
        while True:
            monitor_status()
            time.sleep(interval)
            print("\033[2J\033[H")  # 清屏
    except KeyboardInterrupt:
        print("\n👋 监控已停止")

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='健壮性系统监控')
    parser.add_argument('--interval', type=int, default=5, help='刷新间隔(秒)')
    parser.add_argument('--once', action='store_true', help='只显示一次')
    
    args = parser.parse_args()
    
    if args.once:
        monitor_status()
    else:
        continuous_monitor(args.interval)
