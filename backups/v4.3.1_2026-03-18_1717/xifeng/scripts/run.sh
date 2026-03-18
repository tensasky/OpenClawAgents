#!/bin/bash
# 西风 Skill - 定时任务脚本
# 每30分钟运行一次

SKILL_DIR="$HOME/.openclaw/skills/xifeng"
LOG_FILE="$SKILL_DIR/logs/cron.log"

cd "$SKILL_DIR"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 🌪️ 西风分析启动" >> "$LOG_FILE"

# 执行分析
if python3 xifeng.py >> "$LOG_FILE" 2>&1; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✅ 完成" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ❌ 失败" >> "$LOG_FILE"
fi

echo "" >> "$LOG_FILE"
