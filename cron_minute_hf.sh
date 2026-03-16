#!/bin/bash
# 北风 - 高频分钟数据采集（每5分钟）
# 交易时段高频运行

cd /Users/roberto/Documents/OpenClawAgents/beifeng

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 分钟数据采集启动"

# 加载核心股票列表（前50只，平衡覆盖面和速度）
if [ -f "data/core100_stocks.json" ]; then
    STOCKS=$(python3 -c "import json; data=json.load(open('data/core100_stocks.json')); print(' '.join([s['code'] for s in data[:50]]))")
else
    STOCKS="sh000001 sz399001 sh600519 sz300750 sh600036 sh601318 sz000858"
fi

# 采集分钟数据
echo "⏱️ 采集分钟数据: $STOCKS"
python3 beifeng.py $STOCKS --type minute >> logs/beifeng_minute_hf.log 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 分钟数据采集完成"
