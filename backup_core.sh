#!/bin/bash
# 备份脚本 - 全量更新时自动备份核心文件
# 备份到: ~/Documents/OpenClawAgents/backups/

BACKUP_DIR="$HOME/Documents/OpenClawAgents/backups"
VERSION=${1:-"v4.3.0"}
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H%M%S)
BACKUP_NAME="${VERSION}_${DATE}_${TIME}"

# 创建备份目录
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# 备份文件
echo "📦 备份核心文件..."

# 1. MEMORY.md
cp "$HOME/.openclaw/workspace/MEMORY.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null
echo "  ✅ MEMORY.md"

# 2. SOUL.md  
cp "$HOME/.openclaw/workspace/SOUL.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null
echo "  ✅ SOUL.md"

# 3. openclaw.json
cp "$HOME/.openclaw/openclaw.json" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null
echo "  ✅ openclaw.json"

# 4. 当日memory
cp -r "$HOME/.openclaw/workspace/memory/"* "$BACKUP_DIR/" 2>/dev/null
echo "  ✅ memory/*"

echo ""
echo "📍 备份位置: $BACKUP_DIR/$BACKUP_NAME/"
echo "🖥️ 远程备份: Git仓库 backups/$BACKUP_NAME/"

# Git远程备份
cd "$HOME/Documents/OpenClawAgents"
git add -A > /dev/null 2>&1
git commit -m "backup: $BACKUP_NAME" > /dev/null 2>&1
echo "☁️ Git远程备份: 已提交"

echo ""
echo "✅ 备份完成!"
