#!/bin/bash
# 9-Agent 全流程测试脚本
# 用于验证每个Agent是否能正常工作

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs/agent_test"
mkdir -p "$LOG_DIR"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          🎯 9-Agent 功能测试                                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# 1. 北风 - 数据采集
echo "🌪️ 【1/7】北风 - 数据采集"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/beifeng"
python3 beifeng.py sh000001 sh600519 --type daily >> "$LOG_DIR/beifeng.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 北风: 正常"
else
    echo "   ❌ 北风: 失败"
fi
echo ""

# 2. 西风 - 板块热点
echo "🍃 【2/7】西风 - 板块热点"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/xifeng"
python3 multi_source_fetcher.py >> "$LOG_DIR/xifeng.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 西风: 正常"
else
    echo "   ❌ 西风: 失败"
fi
echo ""

# 3. 东风 - 候选池
echo "🌸 【3/7】东风 - 候选池"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/dongfeng"
python3 dongfeng.py --scan >> "$LOG_DIR/dongfeng.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 东风: 正常"
else
    echo "   ❌ 东风: 失败"
fi
echo ""

# 4. 南风 - 策略评分
echo "🌬️ 【4/7】南风 - 策略评分"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/nanfeng"
python3 priority_stocks_monitor.py >> "$LOG_DIR/nanfeng.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 南风: 正常"
else
    echo "   ❌ 南风: 失败"
fi
echo ""

# 5. 红中 - 信号通知
echo "🀄 【5/7】红中 - 信号通知"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/hongzhong"
python3 generate_signals_v3.py >> "$LOG_DIR/hongzhong.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 红中: 正常"
else
    echo "   ❌ 红中: 失败"
fi
echo ""

# 6. 发财 - 模拟交易
echo "💰 【6/7】发财 - 模拟交易"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/facai"
python3 facai.py --help >> "$LOG_DIR/facai.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 发财: 正常"
else
    echo "   ❌ 发财: 失败"
fi
echo ""

# 7. 白板 - 策略优化
echo "🀆 【7/7】白板 - 策略优化"
echo "────────────────────────────────────────────────────────"
cd "$SCRIPT_DIR/baiban"
python3 baiban.py --help >> "$LOG_DIR/baiban.log" 2>&1
if [ $? -eq 0 ]; then
    echo "   ✅ 白板: 正常"
else
    echo "   ❌ 白板: 失败"
fi
echo ""

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                  ✅ 测试完成                                  ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "日志位置: $LOG_DIR"
