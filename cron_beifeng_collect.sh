#!/bin/bash
# 北风数据采集定时任务 - 交易时段运行
# 采集日线和分钟数据

cd /Users/roberto/Documents/OpenClawAgents/beifeng

# 获取当前时间
HOUR=$(date +%H)
MINUTE=$(date +%M)
TIME_VAL=$((10#$HOUR * 100 + 10#$MINUTE))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 北风数据采集启动"

# 加载核心股票列表
if [ -f "data/core100_stocks.json" ]; then
    # 提取前20只核心股票（避免过于频繁）
    STOCKS=$(python3 -c "import json; data=json.load(open('data/core100_stocks.json')); print(' '.join([s['code'] for s in data[:20]]))")
else
    # 默认股票
    STOCKS="sh000001 sz399001 sh600519 sz300750"
fi

# 采集日线数据（每天一次，开盘后不久）
if [ $TIME_VAL -ge 930 ] && [ $TIME_VAL -lt 1000 ]; then
    echo "📊 采集日线数据..."
    python3 beifeng.py $STOCKS --type daily >> logs/beifeng_daily.log 2>&1
fi

# 采集分钟数据（交易时段每30分钟）
if [ $TIME_VAL -ge 930 ] && [ $TIME_VAL -lt 1130 ] || [ $TIME_VAL -ge 1300 ] && [ $TIME_VAL -lt 1500 ]; then
    echo "⏱️ 采集分钟数据..."
    python3 beifeng.py $STOCKS --type minute >> logs/beifeng_minute.log 2>&1
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 北风数据采集完成"
