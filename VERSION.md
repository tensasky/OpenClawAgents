# 版本管理说明

## 版本号规则
采用语义化版本控制 (Semantic Versioning)

格式：`MAJOR.MINOR.PATCH`

- **MAJOR** (主版本): 重大功能变更，不兼容的API修改
- **MINOR** (次版本): 新增功能，向后兼容
- **PATCH** (补丁): Bug修复，向后兼容

## 当前版本

### v1.3.0 (2026-03-10)
- 北风 V3 - 准实时数据（1-5分钟延迟，接近交易所级别）
- 南风 V3 - 实时量化分析引擎
- 西风 v1.0 - 舆情分析
- 码农 v0.1 - 代码开发（框架）
- 监控 v0.1 - 系统监控（框架）
- Telegram 双通道接入

### v1.2.0 (2026-03-09)
- 南风V3 - 实时量化引擎
- 北风 - storage_v2修复

### v1.1.0 (2026-03-09)
- 北风 V2 - 股票数据采集（分钟数据支持）
- 西风 v1.0 - 舆情分析
- 码农 v0.1 - 代码开发（框架）
- 监控 v0.1 - 系统监控（框架）
- Telegram 双通道接入

### v1.0.0 (2026-03-09)
- 北风 v1.0 - 股票数据采集
- 西风 v1.0 - 舆情分析
- 码农 v0.1 - 代码开发（框架）
- 监控 v0.1 - 系统监控（框架）

## Git 仓库

```bash
# 查看版本历史
git log --oneline

# 查看标签
git tag

# 切换到指定版本
git checkout v1.0.0

# 查看当前状态
git status
```

## 数据备份

大文件（数据库）单独备份：
- 位置：`~/Documents/OpenClawAgents-Data/`
- 格式：`{agent}-data-v{版本}.tar.gz`
- 当前：`beifeng-data-v1.0.0.tar.gz` (35MB)

## 升级流程

1. 修改代码
2. 测试验证
3. 更新 CHANGELOG.md
4. 提交 Git: `git add -A && git commit -m "v1.x.x: 描述"`
5. 打标签: `git tag -a v1.x.x -m "描述"`
6. 备份数据（如有变更）

## 回滚流程

```bash
# 回滚到指定版本
git checkout v1.0.0

# 恢复数据（如有需要）
cd ~/Documents/OpenClawAgents-Data
tar xzf beifeng-data-v1.0.0.tar.gz
cp beifeng-stocks-v1.0.0.db ~/Documents/OpenClawAgents/beifeng/data/stocks.db
```

---
*版本管理：Git*
*备份策略：代码+数据分离*
