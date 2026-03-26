#!/bin/bash
# 北风扩展采集脚本 - 500只核心股票

export PYTHONPATH=/Users/roberto/Documents/OpenClawAgents
cd /Users/roberto/Documents/OpenClawAgents
LOG_FILE="/Users/roberto/Documents/OpenClawAgents/logs/beifeng_full.log"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 北风扩展采集 ===" >> "$LOG_FILE"

# 获取前500只股票代码
STOCKS=$(sqlite3 /Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db "SELECT code FROM stocks LIMIT 500;" 2>/dev/null)

if [ -z "$STOCKS" ]; then
    echo "获取股票列表失败" >> "$LOG_FILE"
    exit 1
fi

# 运行扩展采集
python3 beifeng/beifeng.py $STOCKS --type minute >> "$LOG_FILE" 2>&1

echo "=== $(date '+%Y-%m-%d %H:%M:%S') 扩展采集完成 ===" >> "$LOG_FILE"
