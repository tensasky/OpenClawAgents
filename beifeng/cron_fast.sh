#!/bin/bash
# 北风快速采集脚本 - 核心500只 (2分钟完成)

export PYTHONPATH=/Users/roberto/Documents/OpenClawAgents
cd /Users/roberto/Documents/OpenClawAgents
LOG_FILE="/Users/roberto/Documents/OpenClawAgents/logs/beifeng_fast.log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 北风快速采集 ===" >> "$LOG_FILE"

# 核心500只股票列表 (沪深300 + 热门板块 + ETF)
python3 -c "
import json
import sqlite3
import time
from datetime import datetime, timedelta

# 读取全部股票
with open('beifeng/data/all_stocks.json', 'r') as f:
    all_stocks = json.load(f)

# 获取今日已采集的股票
conn = sqlite3.connect('beifeng/data/stocks_real.db')
cursor = conn.cursor()
today = datetime.now().strftime('%Y-%m-%d')
cursor.execute('SELECT DISTINCT stock_code FROM minute WHERE timestamp LIKE ?', (today + '%',))
done = set(row[0] for row in cursor.fetchall())
conn.close()

# 优先采集未完成的
undone = [s['code'] for s in all_stocks if s['code'] not in done]
print(' '.join(undone[:500]))
" > /tmp/fast_stocks.txt

STOCKS=$(cat /tmp/fast_stocks.txt)

if [ -n "$STOCKS" ]; then
    /usr/bin/python3 beifeng/beifeng.py $STOCKS --type minute >> "$LOG_FILE" 2>&1
    echo "=== $(date '+%Y-%m-%d %H:%M:%S') 快速采集完成 ===" >> "$LOG_FILE"
fi
