#!/bin/bash
# 西风V2 - 每2小时板块分析推送（完整版）
# 交易时段: 9:30, 11:30, 13:30, 15:30

XIFENG_DIR="/Users/roberto/Documents/OpenClawAgents/xifeng"
LOG_FILE="$XIFENG_DIR/logs/sector_v2.log"

mkdir -p "$XIFENG_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 西风V2板块分析启动..." >> "$LOG_FILE"

cd "$XIFENG_DIR"

# 使用完整版
python3 xifeng_v2_sector.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 成功" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 失败，尝试简化版..." >> "$LOG_FILE"
    python3 xifeng_v2_simple.py >> "$LOG_FILE" 2>&1
fi

echo "---" >> "$LOG_FILE"
