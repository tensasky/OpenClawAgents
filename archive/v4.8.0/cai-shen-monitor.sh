#!/bin/bash
# 财神爷监督脚本 - 每晚8点汇报北风、西风、南风工作状态
# 位置: ~/.openclaw/scripts/cai-shen-monitor.sh

REPORT_TIME="20:00"
LOG_DIR="$HOME/.openclaw/logs"
DB_DIR="$HOME/.openclaw/agents/beifeng/data"
REPORT_FILE="$LOG_DIR/daily-report-$(date +%Y%m%d).txt"

# 确保日志目录存在
mkdir -p "$LOG_DIR"

# 生成日报
generate_report() {
    echo "======================================"
    echo "💰 财神爷每日监督报告"
    echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "======================================"
    echo ""
    
    # 北风状态
    echo "🌪️ 北风 (股票数据采集)"
    echo "------------------------"
    if [ -f "$DB_DIR/stocks_v2.db" ]; then
        DB_SIZE=$(du -h "$DB_DIR/stocks_v2.db" | cut -f1)
        echo "  数据库大小: $DB_SIZE"
        
        # 获取今日数据量（如果sqlite3可用）
        if command -v sqlite3 &> /dev/null; then
            TODAY_COUNT=$(sqlite3 "$DB_DIR/stocks_v2.db" "SELECT COUNT(*) FROM daily_prices WHERE date(created_at) = date('now')" 2>/dev/null || echo "N/A")
            echo "  今日新增数据: $TODAY_COUNT 条"
        fi
    else
        echo "  ⚠️ 数据库文件不存在"
    fi
    
    # 检查北风日志
    if [ -f "$LOG_DIR/beifeng.log" ]; then
        ERROR_COUNT=$(grep -c "ERROR" "$LOG_DIR/beifeng.log" 2>/dev/null || echo "0")
        echo "  今日错误数: $ERROR_COUNT"
    fi
    echo ""
    
    # 西风状态
    echo "🍃 西风 (数据分析)"
    echo "------------------------"
    if [ -d "$HOME/.openclaw/agents/xifeng" ]; then
        echo "  状态: 已部署"
        if [ -f "$LOG_DIR/xifeng.log" ]; then
            LAST_RUN=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M" "$LOG_DIR/xifeng.log" 2>/dev/null || echo "未知")
            echo "  最后运行: $LAST_RUN"
        fi
    else
        echo "  ⚠️ 未部署"
    fi
    echo ""
    
    # 南风状态
    echo "🌬️ 南风 (待部署)"
    echo "------------------------"
    if [ -d "$HOME/.openclaw/agents/nanfeng" ]; then
        echo "  状态: 已部署"
    else
        echo "  状态: 未部署"
    fi
    echo ""
    
    # 系统状态
    echo "📊 系统状态"
    echo "------------------------"
    DISK_USAGE=$(df -h "$HOME" | tail -1 | awk '{print $5}')
    echo "  磁盘使用率: $DISK_USAGE"
    
    # 检查 OpenClaw 网关
    if pgrep -f "openclaw-gateway" > /dev/null 2>&1; then
        echo "  OpenClaw 网关: ✅ 运行中"
    else
        echo "  OpenClaw 网关: ❌ 未运行"
    fi
    echo ""
    
    echo "======================================"
    echo "报告生成完毕 - 财神爷 💰"
    echo "======================================"
}

# 发送报告到 Discord
send_report() {
    local report="$1"
    # 使用 OpenClaw 消息工具发送
    # 实际发送由调用方处理
    echo "$report"
}

# 主函数
main() {
    generate_report > "$REPORT_FILE"
    cat "$REPORT_FILE"
}

# 如果直接运行
if [ "${BASH_SOURCE[0]}" == "${0}" ]; then
    main "$@"
fi
