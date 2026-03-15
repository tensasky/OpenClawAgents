#!/bin/bash
# 十五五板块监控定时任务
# 交易时段每30分钟运行一次

cd /Users/roberto/Documents/OpenClawAgents/nanfeng

# 运行板块监控
/usr/bin/python3 sector_15th_monitor.py >> /Users/roberto/.openclaw/workspace/logs/15th_sector_monitor.log 2>&1
