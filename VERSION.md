# 版本管理说明

## 版本号规则
采用语义化版本控制 (Semantic Versioning)

格式：`MAJOR.MINOR.PATCH`

- **MAJOR** (主版本): 重大功能变更，不兼容的API修改
- **MINOR** (次版本): 新增功能，向后兼容
- **PATCH** (补丁): Bug修复，向后兼容

## 当前版本

### v4.1.0 (2026-03-17) - 生产级修复版
**全量更新 - 数据质量与系统稳定性**

**修复内容:**
- 数据库清理: 修复5,240条daily表 + 5,235条stock_names表换行符问题
- SQL查询修复: 南风V5.1移除data_type条件，统一使用daily表
- 批量修复: 10个文件 kline_data → daily
- 判官Agent升级: 添加数据时效性验证 (30分钟阈值)
- 数据发送前自动验证，超时禁止发送

**Agent状态:**
- 北风 V3.0 - 健壮性数据采集系统 (断路器+重试队列+多数据源)
- 南风 V5.1 - 量化大脑 (趋势跟踪/突破策略/涨停监控)
- 红中 V3.0 - 交易信号系统 (保守版/平衡版双版本)
- 西风 V2.0 - 板块分析 (每2小时推送)
- 判官 V1.1 - 数据验证Agent (新增时效性验证)
- 白板 V1.0 - 策略进化
- 发财 V1.0 - 模拟交易
- 东风 V1.0 - 数据展示
- 财神爷 V5.2 - 监控与报告

### v4.0.0 (2026-03-16) - 生产级里程碑
- 9-Agent全系统修复与优化
- 修复42个文件语法错误
- 全A股数据采集系统 (5,356只股票)
- 健壮性数据采集系统 (断路器模式)
- 主数据库系统 (master_stocks: 5,347只)

### v3.x (历史版本)
- 详见Git历史

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
