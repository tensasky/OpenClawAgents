#!/bin/bash
# 北风数据采集定时任务
# 带进程锁机制

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 使用Python锁
python3 "${SCRIPT_DIR}/utils/cron_wrapper.py" -l "beifeng_collect" -t 120 -- bash -c "
    cd '${SCRIPT_DIR}/beifeng'
    
    HOUR=\$(date +%H)
    MINUTE=\$(date +%M)
    TIME_VAL=\$((10#\$HOUR * 100 + 10#\$MINUTE))
    
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 北风数据采集启动\"
    
    # 加载核心股票列表
    if [ -f 'data/core100_stocks.json' ]; then
        STOCKS=\$(python3 -c \"import json; data=json.load(open('data/core100_stocks.json')); print(' '.join([s['code'] for s in data[:20]]))\")
    else
        STOCKS='sh000001 sz399001 sh600519 sz300750'
    fi
    
    # 采集日线数据（每天一次，开盘后不久）
    if [ \$TIME_VAL -ge 930 ] && [ \$TIME_VAL -lt 1000 ]; then
        echo '📊 采集日线数据...'
        python3 beifeng.py \$STOCKS --type daily >> logs/beifeng_daily.log 2>&1
    fi
    
    # 采集分钟数据
    if ([ \$TIME_VAL -ge 930 ] && [ \$TIME_VAL -lt 1130 ]) || ([ \$TIME_VAL -ge 1300 ] && [ \$TIME_VAL -lt 1500 ]); then
        echo '⏱️ 采集分钟数据...'
        python3 beifeng.py \$STOCKS --type minute >> logs/beifeng_minute.log 2>&1
    fi
    
    echo \"[\$(date '+%Y-%m-%d %H:%M:%S')] 北风数据采集完成\"
"
