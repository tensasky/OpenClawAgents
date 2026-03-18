#!/bin/bash
# 重点股票监控
# 带进程锁机制

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "${SCRIPT_DIR}/utils/cron_wrapper.py" -l "priority_stocks_monitor" -t 60 -- bash -c "
    cd '${SCRIPT_DIR}/nanfeng'
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 重点股票监控启动\"
    /usr/bin/python3 priority_stocks_monitor.py >> /Users/roberto/.openclaw/workspace/logs/priority_stocks_monitor.log 2>&1
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 重点股票监控完成\"
"
