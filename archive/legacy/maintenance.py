#!/usr/bin/env python3
"""
系统维护脚本 - System Maintenance
整合所有维护功能：日志清理、性能监控、健康检查
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/utils"))
from agent_logger import get_logger

log = get_logger("系统维护")


def run_log_cleanup(days: int = 7):
    """运行日志清理"""
    log.step("运行日志清理")
    from log_cleaner import LogCleaner
    
    cleaner = LogCleaner()
    result = cleaner.cleanup(days=days, dry_run=False)
    
    print(f"\n清理结果:")
    print(f"  扫描文件: {result['scanned']}")
    print(f"  删除文件: {result['to_delete']}")
    print(f"  释放空间: {result['delete_size_mb']:.1f} MB")
    
    return result


def run_health_check():
    """运行健康检查"""
    log.step("运行健康检查")
    
    import subprocess
    result = subprocess.run(
        ['python3', str(Path.home() / 'Documents/OpenClawAgents/system_flow_simulator.py')],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.returncode != 0:
        log.fail("健康检查发现问题")
        return False
    
    log.success("健康检查通过")
    return True


def run_tests():
    """运行单元测试"""
    log.step("运行单元测试")
    
    import subprocess
    result = subprocess.run(
        ['python3', str(Path.home() / 'Documents/OpenClawAgents/tests/test_framework.py')],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    
    return result.returncode == 0


def generate_metrics_report():
    """生成性能报告"""
    log.step("生成性能报告")
    from performance_monitor import get_monitor
    
    monitor = get_monitor()
    report = monitor.generate_report()
    print(report)
    
    # 保存到文件
    report_file = Path.home() / ".openclaw/workspace/reports" / f"metrics_{datetime.now().strftime('%Y%m%d')}.txt"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report, encoding='utf-8')
    
    log.success(f"报告已保存: {report_file}")
    return True


def full_maintenance():
    """执行完整维护"""
    log.step("开始完整系统维护")
    print("="*70)
    
    # 1. 日志清理
    print("\n[1/4] 日志清理...")
    run_log_cleanup(days=7)
    
    # 2. 健康检查
    print("\n[2/4] 健康检查...")
    run_health_check()
    
    # 3. 性能报告
    print("\n[3/4] 性能报告...")
    generate_metrics_report()
    
    # 4. 单元测试
    print("\n[4/4] 单元测试...")
    run_tests()
    
    print("\n" + "="*70)
    log.success("完整维护完成！")
    print("="*70)


if __name__ == '__main__':
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description='系统维护工具')
    parser.add_argument('--cleanup', action='store_true', help='清理日志')
    parser.add_argument('--days', type=int, default=7, help='日志保留天数')
    parser.add_argument('--health', action='store_true', help='健康检查')
    parser.add_argument('--test', action='store_true', help='运行测试')
    parser.add_argument('--metrics', action='store_true', help='生成性能报告')
    parser.add_argument('--full', action='store_true', help='完整维护')
    
    args = parser.parse_args()
    
    if args.full:
        full_maintenance()
    elif args.cleanup:
        run_log_cleanup(days=args.days)
    elif args.health:
        run_health_check()
    elif args.test:
        run_tests()
    elif args.metrics:
        generate_metrics_report()
    else:
        # 默认运行完整维护
        full_maintenance()
