# MEMORY.md - 永久记忆

## 🎯 核心原则（必须遵守）

### 全量实时数据
- ✅ **必须覆盖全部 5,348只股票**
- ❌ **禁止只采集20只/100只部分数据**
- ⏰ **09:30必须完成全量采集**

### 所有Agent必须正常工作
- 🌪️ **北风** - 全量实时数据采集
- 🍃 **西风** - 每30分钟热点分析
- 🌸 **东风** - 候选池初筛
- 🌬️ **南风** - 全市场策略评分
- 🀄 **红中** - 完整策略报告
- ⚖️ **判官** - 数据时效性验证
- 💰 **发财** - 模拟交易执行
- 🀆 **白板** - 策略优化

### 任务执行标准
- 09:15 系统检查
- 09:30 全量数据采集
- 09:35 全量策略评分
- 09:40 完整报告发送

### 数据质量
- 中文名称必须显示
- 价格数据必须准确
- 策略标识必须完整
- 颜色规范：止损绿/目标红

### 异常处理
- 异常立即报告
- 数据不全禁止发送
- 超30分钟必须告警

---

## 🏗️ 四大标准

### 高性能
- 使用连接池 (`db_pool.py`)

### 高可观测性
- 统一日志 (`agent_logger.py`)
- 性能监控 (`performance_monitor.py`)

### 高可维护性
- 自动化维护 (`maintenance.py`)
- 单元测试 (`test_framework.py`)

### 高安全性
- 敏感信息隔离 (`email_config.py`)

---

## 📐 统一规范

- **日志统一**: 全部使用 `agent_logger`
- **通知统一**: 使用 `unified_notifier`
- **架构统一**: 相同设计模式
- **数据库统一**: 使用 `db_pool`

---

## ⚠️ 改动原则（关键！）

**但凡改动一处，必须全量检测影响，所有相关Agent一起修复！**

---

## 🤖 Agent命令清单

```bash
# 测试所有Agent
bash test_all_agents.sh

# 1. 北风 - 数据采集
python3 beifeng/beifeng.py <股票> --type daily|minute

# 2. 西风 - 板块热点
python3 xifeng/multi_source_fetcher.py

# 3. 东风 - 候选池扫描
python3 dongfeng/dongfeng.py --scan

# 4. 南风 - 策略评分
python3 nanfeng/priority_stocks_monitor.py
python3 nanfeng/limit_up_monitor.py

# 5. 红中 - 信号通知
python3 hongzhong/generate_signals_v3.py

# 6. 发财 - 模拟交易
python3 facai/facai.py

# 7. 白板 - 策略优化
python3 baiban/baiban.py
```

---

## 🎯 核心KPI

- **月度盈利 ≥ 5%**
- **胜率最大化**
- **所有Agent为此服务**

---

## 🔧 技术修复 (2026-03-18)

### Cron冲突修复
- 进程锁：`utils/process_lock.py`
- 连接池增强：`utils/db_pool.py` (WAL模式+重试)
- 锁包装器：`utils/cron_wrapper.py`
- 监控：`cron_monitor.py`

### beifeng.py minute支持
- 添加 `MinuteDataFetcher` 集成
- 修复时间格式保存

### 全量数据采集优化
- minute采集优化为100只核心股
- 44秒完成，避免超时

---

## 项目概述

**A股智能交易系统** - 9-Agent协同工作流

### Agent分工
- **北风**: 数据采集 (5,348只)
- **西风**: 板块分析
- **东风**: 股票筛选
- **南风**: 策略评分
- **红中**: 交易信号
- **发财**: 交易系统
- **白板**: 复盘系统
- **判官**: 数据验证
- **财神爷**: 监控

### 版本
- **v4.1.0** (2026-03-18) - cron锁修复 + minute支持 + Agent测试通过
- **v4.0.0** (2026-03-16) - 主数据库+9-Agent完备

---

## 📦 全量更新备份流程

### 备份文件
每次全量更新时必须备份:
- `~/.openclaw/workspace/MEMORY.md` - 永久记忆
- `~/.openclaw/workspace/SOUL.md` - 灵魂配置
- `~/.openclaw/openclaw.json` - OpenClaw配置

### 备份位置
- 本地: `~/Documents/OpenClawAgents/backups/{版本号}_{日期}_{时间}/`
- 远程: Git仓库 `backups/` 目录

### 备份命令
```bash
bash backup_core.sh v4.3.0
```

### 版本号命名
格式: `v{MAJOR}.{MINOR}.{PATCH}_{YYYY-MM-DD}_{HHMMSS}`
例: `v4.3.0_2026-03-18_160747`
