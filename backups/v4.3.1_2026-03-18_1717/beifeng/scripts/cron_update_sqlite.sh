#!/bin/bash
# 北风定时更新脚本 - 确保数据最新
# 建议：每5分钟运行一次

set -e

WORKSPACE="$HOME/.openclaw/agents/beifeng"
LOG_FILE="$WORKSPACE/logs/cron.log"
LOCK_FILE="$WORKSPACE/.update.lock"
PID=$$

# 确保日志目录存在
mkdir -p "$WORKSPACE/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$PID] $1" | tee -a "$LOG_FILE"
}

# 检查是否已有实例在运行
check_lock() {
    if [ -f "$LOCK_FILE" ]; then
        OLD_PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "0")
        if ps -p "$OLD_PID" > /dev/null 2>&1; then
            log "⚠️ 已有更新进程在运行 (PID: $OLD_PID)，跳过本次"
            exit 0
        else
            log "🧹 清理过期锁文件"
            rm -f "$LOCK_FILE"
        fi
    fi
    echo $PID > "$LOCK_FILE"
}

# 清理锁
cleanup() {
    rm -f "$LOCK_FILE"
    log "🔓 锁已释放"
}
trap cleanup EXIT

# 主逻辑
main() {
    log "🌪️ 北风定时更新启动"
    
    cd "$WORKSPACE"
    
    # 检查数据库健康
    if [ ! -f "data/stocks.db" ]; then
        log "❌ 数据库不存在，需要初始化"
        exit 1
    fi
    
    # 获取需要更新的股票（最近5分钟未更新的）
    STOCKS=$(sqlite3 data/stocks.db "SELECT DISTINCT stock_code FROM kline_data WHERE datetime(timestamp) < datetime('now', '-5 minutes') GROUP BY stock_code ORDER BY MAX(timestamp) ASC LIMIT 50;" 2>/dev/null || echo "")
    
    # 如果没有需要更新的，获取活跃股票列表
    if [ -z "$STOCKS" ]; then
        STOCKS=$(sqlite3 data/stocks.db "SELECT DISTINCT stock_code FROM kline_data ORDER BY RANDOM() LIMIT 20;" 2>/dev/null || echo "")
    fi
    
    # 如果数据库中股票不足3137只，从 all_stocks.json 补充新股票
    DB_COUNT=$(sqlite3 data/stocks.db "SELECT COUNT(DISTINCT stock_code) FROM kline_data;" 2>/dev/null || echo "0")
    if [ "$DB_COUNT" -lt "3137" ]; then
        NEW_STOCKS=$(python3 -c "
import json
import sqlite3
with open('data/all_stocks.json') as f:
    all_stocks = [s['code'] for s in json.load(f)]
conn = sqlite3.connect('data/stocks.db')
cursor = conn.execute('SELECT DISTINCT stock_code FROM kline_data')
existing = {r[0] for r in cursor.fetchall()}
conn.close()
new = [s for s in all_stocks if s not in existing][:10]
print(' '.join(new))
" 2>/dev/null)
        if [ -n "$NEW_STOCKS" ]; then
            STOCKS="$NEW_STOCKS"
            log "🆕 补充新股票 ($DB_COUNT/3137): $NEW_STOCKS"
        fi
    fi
    
    # 默认至少更新上证指数
    if [ -z "$STOCKS" ]; then
        STOCKS="sh000001"
    fi
    
    log "📊 本次更新股票: $(echo $STOCKS | wc -w) 只"
    
    # 执行更新
    if python3 beifeng.py $STOCKS --type daily >> "$LOG_FILE" 2>&1; then
        log "✅ 更新成功"
        
        # 清理旧日志（保留30天）
        find "$WORKSPACE/logs" -name "*.log" -mtime +30 -delete 2>/dev/null || true
    else
        log "❌ 更新失败，查看日志: $LOG_FILE"
        exit 1
    fi
}

# 执行
check_lock
main
