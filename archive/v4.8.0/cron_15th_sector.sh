#!/bin/bash
# 十五五板块监控
# 带进程锁机制

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "${SCRIPT_DIR}/utils/cron_wrapper.py" -l "15th_sector_monitor" -t 60 -- bash -c "
    cd '${SCRIPT_DIR}/nanfeng'
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 十五五板块监控启动\"
    /usr/bin/python3 sector_15th_monitor.py >> /Users/roberto/.openclaw/workspace/logs/15th_sector_monitor.log 2>&1
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 十五五板块监控完成\"
"
