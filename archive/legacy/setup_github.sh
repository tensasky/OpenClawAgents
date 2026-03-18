#!/bin/bash
# GitHub 仓库配置脚本
# 用户: tensasky
# 仓库: OpenClawAgents (私有)

set -e

echo "=========================================="
echo "OpenClaw Agents - GitHub 配置脚本"
echo "=========================================="
echo ""
echo "请确保你已经:"
echo "1. 在 GitHub 创建了仓库: https://github.com/new"
echo "   - Repository name: OpenClawAgents"
echo "   - Visibility: Private"
echo "   - 不要初始化 README"
echo ""
echo "2. 创建了 Personal Access Token:"
echo "   https://github.com/settings/tokens/new"
echo "   - 勾选 'repo' 权限"
echo "   - 复制 token"
echo ""
echo "=========================================="
echo ""

# 检查是否在正确目录
if [ ! -d ".git" ]; then
    echo "❌ 错误: 当前目录不是 Git 仓库"
    echo "请先运行: cd /Users/roberto/Documents/OpenClawAgents"
    exit 1
fi

echo "✅ 当前目录: $(pwd)"
echo ""

# 配置 Git 用户信息
echo "配置 Git 用户信息..."
git config user.name "tensasky"
git config user.email "tensasky@gmail.com"
echo "✅ Git 用户信息已配置"
echo ""

# 添加远程仓库
echo "添加 GitHub 远程仓库..."
if git remote | grep -q "origin"; then
    echo "远程仓库 origin 已存在，更新 URL..."
    git remote set-url origin https://github.com/tensasky/OpenClawAgents.git
else
    git remote add origin https://github.com/tensasky/OpenClawAgents.git
fi
echo "✅ 远程仓库已配置"
echo ""

# 显示当前状态
echo "当前仓库状态:"
git remote -v
echo ""

# 推送代码
echo "=========================================="
echo "准备推送代码到 GitHub"
echo "=========================================="
echo ""
echo "你需要输入 GitHub Personal Access Token 作为密码"
echo ""
echo "推送命令:"
echo "  git push -u origin main --tags"
echo ""
read -p "按 Enter 开始推送，或按 Ctrl+C 取消..."

# 推送
git push -u origin main --tags

echo ""
echo "=========================================="
echo "✅ 推送完成!"
echo "=========================================="
echo ""
echo "GitHub 仓库地址:"
echo "  https://github.com/tensasky/OpenClawAgents"
echo ""
echo "本地仓库位置:"
echo "  /Users/roberto/Documents/OpenClawAgents"
echo ""
