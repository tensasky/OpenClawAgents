#!/bin/bash
# 北风 Agent 激活脚本
# 通过财神爷调用

echo "🌪️ 北风 Agent 激活"
echo "=================="
echo ""

# 检查依赖
if ! command -v python3 &> /dev/null; then
    echo "❌ 需要 Python3"
    exit 1
fi

# 安装依赖
echo "📦 检查依赖..."
pip3 install -q requests 2>/dev/null || echo "⚠️ 依赖安装可能需要手动执行: pip3 install requests"

# 显示状态
echo ""
echo "📊 状态:"
echo "  工作目录: ~/.openclaw/agents/beifeng/"
echo "  数据库: ~/.openclaw/agents/beifeng/data/stocks.db"
echo "  日志: ~/.openclaw/agents/beifeng/logs/"
echo ""
echo "💡 使用示例:"
echo "  python3 ~/.openclaw/agents/beifeng/beifeng.py sh000001 sz000001"
echo ""
