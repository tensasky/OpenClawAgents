# Changelog - OpenClaw Agents

## [v1.1.0] - 2026-03-09

### 新增
- **北风 V2** - 股票数据采集系统升级
  - 真实A股列表（5815只，使用akshare）
  - 分钟数据抓取（1min/5min/15min/30min/60min）
  - 交易时段高频更新（每分钟）
  - 批量写入优化（V2存储层）
  - 双通道通知（Discord + Telegram）

- **Telegram 官方接入**
  - Bot Token 配置
  - 双通道备份（Discord + Telegram）
  - 配对模式安全认证

### 修改
- 股票列表：从20万候选码 → 5815只真实A股
- 定时任务：交易时段每分钟更新分钟数据
- 数据存储：新增分钟数据表

### 技术升级
- storage_v2.py - 批量写入、连接池、WAL模式
- stock_universe_v2.py - akshare真实A股列表
- fill_minute_all.py - 分钟数据补全脚本

### 数据规模
- 日线数据：1,225,118条（2,470只股票）
- 分钟数据：补全中（5815只 × 5天 × 240分钟）

### 版本管理
- 变更日志：CHANGELOG_2026-03-09.md
- 系统状态：MEMORY.md
- 版本号：v1.1.0

---

## [v1.2.0] - 2026-03-09

### 新增
- **南风V3** - 实时量化分析引擎
  - 分钟数据实时汇聚成日线
  - 自适应技术指标（根据市场状态调整参数）
  - 量化策略输出（入场价/止损价/目标价/盈亏比）
  - 盘中实时选股
  - 策略类型：趋势跟踪/均值回归/MACD金叉

### 修复
- **storage_v2.py** - 修复分钟数据写入bug
  - 原问题：异步写入导致数据未落盘
  - 修复：改为同步直接写入

### 文件
- nanfeng_v3.py - 实时量化引擎
- nanfeng/AGENT.md - 更新V3文档

---

## [v1.0.0] - 2026-03-09

### 新增
- **北风 (BeiFeng) v1.0** - 股票数据采集 Agent
  - 支持 2,470 只 A 股日线数据
  - 多数据源（腾讯财经、新浪财经）
  - 自动补全历史数据
  - 定时更新（每5分钟）
  - Discord 通知

- **西风 (XiFeng) v1.0** - 舆情分析 Agent
  - 10个板块热度监控
  - 热度评分算法（频率+动量+情感）
  - 分级输出（High/Medium/Low）
  - 定时分析（每30分钟）
  - hot_spots.json 输出

- **码农 (Coder) v0.1** - 代码开发 Agent
  - 基础框架
  - 代码审查接口
  - 代码生成功能

- **监控 (Monitor) v0.1** - 系统监控 Agent
  - Agent 状态检查
  - 健康报告生成

### 技术栈
- Python 3.9+
- SQLite
- Requests / RSS
- Cron 定时任务

### 数据规模
- 股票数据：122万条日线，221MB
- 监控股票：2,470只
- 舆情板块：10个

### 目录结构
```
OpenClawAgents/
├── beifeng/      # 股票数据 (222MB)
├── xifeng/       # 舆情分析 (108KB)
├── coder/        # 代码开发 (8KB)
└── monitor/      # 系统监控 (8KB)
```

### 定时任务
```bash
# 北风 - 每5分钟
*/5 * * * * beifeng/scripts/cron_update_sqlite.sh

# 西风 - 每30分钟
*/30 * * * * xifeng/scripts/run.sh
```

---
*版本管理：Git*
*创建时间：2026-03-09 06:30*
