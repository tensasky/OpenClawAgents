#!/bin/bash
# 重点股票监控定时任务
# 交易时段运行：开盘后、午盘后、收盘前

cd /Users/roberto/Documents/OpenClawAgents/nanfeng

# 运行重点股票监控
/usr/bin/python3 priority_stocks_monitor.py >> /Users/roberto/.openclaw/workspace/logs/priority_stocks_monitor.log 2>&1
