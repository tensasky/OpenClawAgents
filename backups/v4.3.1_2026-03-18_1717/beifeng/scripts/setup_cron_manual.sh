#!/bin/bash
# 北风 - 配置定时任务
# 运行方式: bash setup_cron_manual.sh

echo "🌪️ 配置北风定时任务..."
echo ""

# 创建临时文件
TMP_CRON=$(mktemp)

# 导出当前 crontab
crontab -l > "$TMP_CRON" 2>/dev/null || echo "# 新建 crontab" > "$TMP_CRON"

# 移除旧的北风配置
grep -v "beifeng" "$TMP_CRON" | grep -v "北风" > "$TMP_CRON.tmp"
mv "$TMP_CRON.tmp" "$TMP_CRON"

# 添加北风任务
cat >> "$TMP_CRON" << 'EOF'

# 北风股票数据采集系统
*/5 * * * * /bin/bash /Users/roberto/.openclaw/agents/beifeng/cron_update_sqlite.sh >> /tmp/beifeng_cron.log 2>&1
0 * * * * /usr/bin/python3 /Users/roberto/.openclaw/agents/beifeng/monitor.py >> /tmp/beifeng_monitor.log 2>&1
EOF

# 安装新配置
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "✅ 定时任务已配置！"
echo ""
echo "📋 当前 crontab:"
crontab -l | tail -10
echo ""
echo "⏰ 任务说明:"
echo "  - 每5分钟: 数据更新"
echo "  - 每小时:  监控检查"
