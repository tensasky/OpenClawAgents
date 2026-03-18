#!/bin/bash
# auto_push.sh - 自动推送脚本
# 每次代码更新后自动推送到 GitHub

set -e

REPO_DIR="/Users/roberto/Documents/OpenClawAgents"
cd "$REPO_DIR"

# 检查是否有变更
if [ -z "$(git status --porcelain)" ]; then
    echo "✅ 没有变更需要推送"
    exit 0
fi

# 生成提交信息（带时间戳）
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")
VERSION=$(git describe --tags --abbrev=0 2>/dev/null || echo "v1.3.0")

# 添加所有变更
git add -A

# 提交
git commit -m "auto: 代码更新 $TIMESTAMP [$VERSION]"

# 推送
git push origin main --tags

echo "✅ 自动推送完成: $TIMESTAMP"
