#!/bin/bash
# 北风 - 日线数据采集（每小时一次）

cd /Users/roberto/Documents/OpenClawAgents/beifeng

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日线数据采集启动"

# 加载核心股票列表（前100只）
if [ -f "data/core100_stocks.json" ]; then
    STOCKS=$(python3 -c "import json; data=json.load(open('data/core100_stocks.json')); print(' '.join([s['code'] for s in data]))")
else
    STOCKS="sh000001 sz399001 sh600519 sz300750"
fi

# 采集日线数据
echo "📊 采集日线数据..."
python3 beifeng.py $STOCKS --type daily >> logs/beifeng_daily.log 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 日线数据采集完成"
