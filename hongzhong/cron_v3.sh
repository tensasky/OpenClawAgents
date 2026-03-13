#!/bin/bash
# 红中V3 - 每15分钟扫描定时任务
# 交易时段: 9:30-11:30, 13:00-15:00

HONGZHONG_DIR="$HOME/Documents/OpenClawAgents/hongzhong"
LOG_FILE="$HONGZHONG_DIR/logs/cron_v3.log"

mkdir -p "$HONGZHONG_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 红中V3扫描启动..." >> "$LOG_FILE"

cd "$HONGZHONG_DIR"
python3 hongzhong_v3.py >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
