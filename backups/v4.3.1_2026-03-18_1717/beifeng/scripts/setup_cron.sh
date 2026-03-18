#!/bin/bash
# 北风 - 添加到 crontab

CRON_FILE="/tmp/beifeng_cron.tmp"

# 导出当前 crontab（去掉旧的北风任务）
crontab -l 2>/dev/null | grep -v "beifeng" | grep -v "北风" > "$CRON_FILE" || true

# 添加北风任务
cat >> "$CRON_FILE" << 'EOF'

# 北风股票数据采集系统
# 每5分钟更新数据
*/5 * * * * /Users/roberto/.openclaw/agents/beifeng/cron_update_sqlite.sh >> /tmp/beifeng_cron.log 2>&1

# 每小时运行监控检查
0 * * * * /usr/bin/python3 /Users/roberto/.openclaw/agents/beifeng/monitor.py >> /tmp/beifeng_monitor.log 2>&1
EOF

# 安装新 crontab
crontab "$CRON_FILE"
rm -f "$CRON_FILE"

echo "✅ 北风定时任务已配置"
echo ""
echo "任务列表:"
echo "  - 每5分钟: 数据更新"
echo "  - 每小时:  监控检查"
echo ""
crontab -l | grep -A5 "北风"
