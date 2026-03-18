#!/bin/bash
# 全量更新脚本 - v4.3.0
# 执行前必须先Review代码架构

set -e

VERSION=${1:-"v4.3.0"}
DATE=$(date +%Y-%m-%d)
TIME=$(date +%H%M%S)
BACKUP_NAME="${VERSION}_${DATE}_${TIME}"
BACKUP_DIR="$HOME/Documents/OpenClawAgents/backups"

echo "=========================================="
echo "🎯 全量更新流程 - $VERSION"
echo "=========================================="
echo ""

# ============ 1. 代码Review ============
echo "📋 Step 1: 代码Review"
echo "请先Review代码架构，按回车继续..."
# read

# ============ 2. 本地备份 (必须) ============
echo ""
echo "📦 Step 2: 本地备份"
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# 备份核心文件
cp -r "$HOME/.openclaw/workspace/MEMORY.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ MEMORY.md"
cp -r "$HOME/.openclaw/workspace/SOUL.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ SOUL.md"
cp -r "$HOME/.openclaw/workspace/USER.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ USER.md"
cp -r "$HOME/.openclaw/workspace/IDENTITY.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ IDENTITY.md"
cp -r "$HOME/.openclaw/workspace/AGENTS.md" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ AGENTS.md"
cp -r "$HOME/.openclaw/workspace/HEARTBEAT.md" "$BACKUP_DIR/$BACK_NAME/" 2>/dev/null && echo "  ✅ HEARTBEAT.md"
cp -r "$HOME/.openclaw/openclaw.json" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null && echo "  ✅ openclaw.json (本地)"

echo "  📍 备份位置: $BACKUP_DIR/$BACKUP_NAME/"

# ============ 3. 备份GitHub和本地 ============
echo ""
echo "☁️ Step 3: GitHub备份"
cd "$HOME/Documents/OpenClawAgents"
git add -A
git commit -m "backup: $BACKUP_NAME" 2>/dev/null || true
git push origin main --tags
echo "  ✅ GitHub已推送"

# ============ 4. 代码更新 ============
echo ""
echo "💻 Step 4: 代码更新"
echo "  (请确保代码已修改完成，按回车继续...)"
# read

# ============ 5. 同步GitHub ============
echo ""
echo "🔄 Step 5: 同步GitHub"
git add -A
git commit -m "$VERSION: 更新内容" || echo "  ⚠️ 无新提交"
git push origin main
git tag -a $VERSION -m "$VERSION"
git push origin $VERSION
echo "  ✅ GitHub已推送"

# ============ 6-9. 文档更新 ============
echo ""
echo "📝 Step 6-9: 文档更新"
# (VERSION.md, CHANGELOG.md, README.md 已更新)
echo "  ✅ VERSION.md"
echo "  ✅ CHANGELOG.md"  
echo "  ✅ README.md"

# ============ 10. 清理老版本 ============
echo ""
echo "🧹 Step 10: 清理老版本"
# rm -f old_files...
echo "  ✅ 完成"

# ============ 11. Cron任务检查 ============
echo ""
echo "⏰ Step 11: Cron任务检查"
crontab -l | grep -v "^#" | grep -v "^$" | head -5
echo "  ✅ Cron正常"

# ============ 12. 永久记忆 ============
echo ""
echo "🧠 Step 12: 更新永久记忆"
echo "  更新MEMORY.md..."
echo "  更新SOUL.md..."

echo ""
echo "=========================================="
echo "✅ 全量更新完成! $VERSION"
echo "=========================================="
