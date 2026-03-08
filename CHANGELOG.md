# Changelog - OpenClaw Agents

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
