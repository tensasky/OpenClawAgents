#!/bin/bash
# 北风 - 后台批量初始化任务
# 用于首次全量数据抓取

WORKSPACE="$HOME/.openclaw/agents/beifeng"
LOG_FILE="$WORKSPACE/logs/batch_init.log"
PID_FILE="$WORKSPACE/.batch_init.pid"

# 检查是否已在运行
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "批量初始化已在运行 (PID: $OLD_PID)"
        echo "查看日志: tail -f $LOG_FILE"
        exit 0
    fi
fi

echo "$$" > "$PID_FILE"

cd "$WORKSPACE"

echo "🌪️ 北风批量初始化启动 ($(date))" >> "$LOG_FILE"
echo "📊 共 3113 只股票，分批处理..." >> "$LOG_FILE"

# 分批抓取，每批10只，间隔5秒
python3 -c "
import json
import subprocess
import time
import sys

with open('data/all_stocks.json') as f:
    stocks = json.load(f)

codes = [s['code'] for s in stocks]
total = len(codes)
batch_size = 10

print(f'共 {total} 只股票')

for i in range(0, total, batch_size):
    batch = codes[i:i+batch_size]
    batch_num = i // batch_size + 1
    total_batches = (total + batch_size - 1) // batch_size
    
    print(f'[{batch_num}/{total_batches}] {batch[0]}...{batch[-1]}')
    
    cmd = f\"python3 beifeng.py {' '.join(batch)} --type daily\"
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.returncode == 0:
        print(f'  ✅ 成功')
    else:
        print(f'  ❌ 失败')
    
    # 休息避免请求过快
    time.sleep(3)

print('批量初始化完成')
" >> "$LOG_FILE" 2>&1

echo "✅ 批量初始化完成 ($(date))" >> "$LOG_FILE"
rm -f "$PID_FILE"
