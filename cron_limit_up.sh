#!/bin/bash
# 涨停策略实时监控定时任务
# 交易时段运行：开盘后、午盘后、收盘前

cd /Users/roberto/Documents/OpenClawAgents/nanfeng

# 运行涨停监控
/usr/bin/python3 limit_up_monitor.py >> /Users/roberto/.openclaw/workspace/logs/limit_up_monitor.log 2>&1
