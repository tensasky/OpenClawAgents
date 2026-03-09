#!/bin/bash
# 北风 - 分钟数据定时更新脚本
# 每5分钟运行一次，更新核心股票分钟数据

WORKSPACE="$HOME/.openclaw/agents/beifeng"
LOG_FILE="$WORKSPACE/logs/minute_cron.log"
PID=$$

# 核心股票列表（可根据需要调整）
STOCKS="sz300480 sh600519 sz000858 sz002594 sh601318"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$PID] 🌪️ 北风分钟数据更新启动" >> "$LOG_FILE"

cd "$WORKSPACE"

# 更新每只股票分钟数据
for stock in $STOCKS; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 更新 $stock 分钟数据..." >> "$LOG_FILE"
    python3 minute_fetcher.py "$stock" >> "$LOG_FILE" 2>&1
done

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$PID] ✅ 完成" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
