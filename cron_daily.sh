#!/bin/bash
# 日线数据采集
# 带进程锁机制

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 "${SCRIPT_DIR}/utils/cron_wrapper.py" -l "beifeng_daily" -t 120 -- bash -c "
    cd '${SCRIPT_DIR}/beifeng'
    
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 日线数据采集启动\"
    
    if [ -f 'data/core100_stocks.json' ]; then
        STOCKS=\$(python3 -c \"import json; data=json.load(open('data/core100_stocks.json')); print(' '.join([s['code'] for s in data]))\")
    else
        STOCKS='sh000001 sz399001 sh600519 sz300750'
    fi
    
    echo '📊 采集日线数据...'
    python3 beifeng.py \$STOCKS --type daily >> logs/beifeng_daily.log 2>&1
    
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 日线数据采集完成\"
"
