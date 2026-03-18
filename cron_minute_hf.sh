#!/bin/bash
# 北风 - 高频分钟数据采集
# 优化版：快速批量采集 + 后台运行 + 不阻塞

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_FILE="${SCRIPT_DIR}/logs/minute_$(date +%Y%m%d).log"

# 检查是否已有运行中的任务
LOCK_FILE="${SCRIPT_DIR}/.locks/minute_running.lock"
if [ -f "$LOCK_FILE" ]; then
    PID=$(cat "$LOCK_FILE" 2>/dev/null)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] 已有采集进程运行中，跳过" >> "$LOG_FILE"
        exit 0
    fi
fi

# 记录PID
echo $$ > "$LOCK_FILE"

# 后台运行采集，不阻塞
(
    cd "${SCRIPT_DIR}/beifeng"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 分钟数据采集启动" >> "$LOG_FILE"
    
    python3 -c "
import subprocess
import sqlite3
from pathlib import Path
import time

WORKSPACE = Path('${SCRIPT_DIR}/beifeng')
DB_PATH = WORKSPACE / 'data' / 'stocks_real.db'

# 获取今日有minute数据的股票（优先更新）
conn = sqlite3.connect(str(DB_PATH))
cursor = conn.cursor()

# 优先采集今日还没有数据的股票
cursor.execute('''
    SELECT stock_code FROM master_stocks
    WHERE stock_code NOT IN (
        SELECT DISTINCT stock_code FROM minute 
        WHERE timestamp LIKE \"2026-03-18%\"
    )
    ORDER BY stock_code
    LIMIT 200
''')

stocks = [row[0] for row in cursor.fetchall()]

# 如果不足200只，采集更多的
if len(stocks) < 200:
    cursor.execute('''
        SELECT stock_code FROM master_stocks
        ORDER BY stock_code
        LIMIT 500
    ''')
    stocks = [row[0] for row in cursor.fetchall()]

conn.close()

print(f'目标采集: {len(stocks)} 只股票')

# 分批快速采集（每批50只）
BATCH_SIZE = 50
for i in range(0, len(stocks), BATCH_SIZE):
    batch = stocks[i:i+BATCH_SIZE]
    codes = ' '.join(batch)
    
    try:
        result = subprocess.run(
            f'python3 beifeng.py {codes} --type minute',
            shell=True,
            capture_output=True,
            text=True,
            timeout=60
        )
        print(f'批次{(i//BATCH_SIZE)+1}: OK')
    except Exception as e:
        print(f'批次{(i//BATCH_SIZE)+1}: FAIL')

print('采集完成')
" >> "$LOG_FILE" 2>&1

    # 聚合minute数据到daily
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 判官聚合启动" >> "$LOG_FILE"
    python3 "${SCRIPT_DIR}/judge/data_validator.py" >> "$LOG_FILE" 2>&1

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 采集完成" >> "$LOG_FILE"
    
    # 删除锁文件
    rm -f "$LOCK_FILE"
) &

# 立即退出，不等待后台完成
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 后台任务已启动 (PID: $!)"
exit 0
