#!/bin/bash
# 涨停策略实时监控
# 带进程锁机制

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "${SCRIPT_DIR}/utils/cron_wrapper.py" -l "limit_up_monitor" -t 60 -- bash -c "
    cd '${SCRIPT_DIR}/nanfeng'
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 涨停监控启动\"
    /usr/bin/python3 limit_up_monitor.py >> /Users/roberto/.openclaw/workspace/logs/limit_up_monitor.log 2>&1
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 涨停监控完成\"
"
