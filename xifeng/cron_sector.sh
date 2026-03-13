#!/bin/bash
# 西风V2 - 每2小时板块分析推送
# 添加到crontab: 0 */2 * * * /path/to/cron_sector.sh

XIFENG_DIR="$HOME/Documents/OpenClawAgents/xifeng"
LOG_FILE="$XIFENG_DIR/logs/sector_cron.log"

mkdir -p "$XIFENG_DIR/logs"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 西风V2板块分析启动..." >> "$LOG_FILE"

cd "$XIFENG_DIR"
python3 xifeng_v2_sector.py >> "$LOG_FILE" 2>&1

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 完成" >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
