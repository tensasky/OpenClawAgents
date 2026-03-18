#!/bin/bash
# 北风定时更新脚本 - 每5分钟执行

export PATH="/opt/homebrew/opt/postgresql@14/bin:$PATH"

cd "$HOME/.openclaw/agents/beifeng"

# 获取所有股票代码
STOCKS=$(psql -U beifeng -d beifeng_stocks -t -c "SELECT code FROM stocks LIMIT 100;" | xargs)

# 执行增量更新
python3 beifeng_pg.py $STOCKS >> logs/cron.log 2>&1

echo "[$(date)] 增量更新完成" >> logs/cron.log
