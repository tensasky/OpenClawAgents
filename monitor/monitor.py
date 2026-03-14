#!/usr/bin/env python3
"""
监控 (Monitor) - 系统监控 Agent
功能：监控所有 Agent 状态，异常告警
"""

import os
import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("System")


AGENTS_DIR = Path.home() / "Documents/OpenClawAgents"


class MonitorAgent:
    """监控 Agent"""
    
    def __init__(self):
        self.name = "监控"
        self.emoji = "👁️"
        self.agents = ["beifeng", "xifeng", "coder"]
    
    def check_agent_status(self, agent_name: str) -> dict:
        """检查 Agent 状态"""
        agent_dir = AGENTS_DIR / agent_name
        
        status = {
            "name": agent_name,
            "exists": agent_dir.exists(),
            "last_run": None,
            "healthy": False
        }
        
        # 检查日志
        log_dir = agent_dir / "logs"
        if log_dir.exists():
            log_files = list(log_dir.glob("*.log"))
            if log_files:
                latest = max(log_files, key=lambda p: p.stat().st_mtime)
                status["last_run"] = datetime.fromtimestamp(latest.stat().st_mtime).isoformat()
                # 如果最近1小时有日志，认为健康
                if latest.stat().st_mtime > (datetime.now() - timedelta(hours=1)).timestamp():
                    status["healthy"] = True
        
        return status
    
    def check_all(self) -> list:
        """检查所有 Agent"""
        results = []
        for agent in self.agents:
            results.append(self.check_agent_status(agent))
        return results
    
    def generate_report(self) -> str:
        """生成监控报告"""
        statuses = self.check_all()
        
        report = []
        report.append("=" * 60)
        report.append("👁️ 系统监控报告")
        report.append("=" * 60)
        report.append(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")
        
        for status in statuses:
            icon = "✅" if status["healthy"] else "❌"
            report.append(f"{icon} {status['name']}")
            report.append(f"   存在: {'是' if status['exists'] else '否'}")
            report.append(f"   健康: {'是' if status['healthy'] else '否'}")
            if status["last_run"]:
                report.append(f"   最后运行: {status['last_run']}")
            report.append("")
        
        return "\n".join(report)


def main():
    """命令行入口"""
    monitor = MonitorAgent()
    print(monitor.generate_report())


if __name__ == '__main__':
    main()
