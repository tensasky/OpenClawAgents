# OpenClaw Agents - 多 Agent 协作系统

## 概述
7-Agent 系统中的前 4 个 Agent，结构化共享，方便自行处理。

## Agent 列表

### 1. 北风 (BeiFeng) 🌪️
- **功能**: 股票数据采集
- **状态**: ✅ 运行中
- **数据**: 2,470只A股，122万条日线
- **定时**: 每5分钟更新
- **目录**: `beifeng/`

### 2. 西风 (XiFeng) 🌪️
- **功能**: 舆情与热点分析
- **状态**: ✅ 运行中
- **数据**: 10个板块热度评分
- **定时**: 每30分钟分析
- **目录**: `xifeng/`

### 3. 码农 (Coder) 👨‍💻
- **功能**: 代码开发与审查
- **状态**: 📝 待开发
- **目录**: `coder/`

### 4. 监控 (Monitor) 👁️
- **功能**: 系统监控与告警
- **状态**: 📝 基础框架
- **目录**: `monitor/`

## 目录结构
```
OpenClawAgents/
├── README.md           # 本文件
├── beifeng/            # 股票数据Agent
│   ├── README.md
│   ├── beifeng.py
│   ├── fetcher.py
│   ├── config/
│   ├── data/
│   ├── logs/
│   └── scripts/
├── xifeng/             # 舆情分析Agent
│   ├── README.md
│   ├── xifeng.py
│   ├── config/
│   ├── data/
│   ├── logs/
│   └── scripts/
├── coder/              # 代码开发Agent
│   ├── README.md
│   └── coder.py
└── monitor/            # 监控Agent
    ├── README.md
    └── monitor.py
```

## 快速开始

### 查看状态
```bash
# 北风状态
cd beifeng && python3 status.py

# 西风热点
cat xifeng/data/hot_spots.json

# 监控报告
cd monitor && python3 monitor.py
```

### 手动运行
```bash
# 运行北风
cd beifeng && python3 beifeng.py sh000001

# 运行西风
cd xifeng && python3 xifeng.py
```

### 定时任务
```bash
# 查看当前定时任务
crontab -l

# 北风: 每5分钟
*/5 * * * * /bin/bash ~/Documents/OpenClawAgents/beifeng/scripts/cron_update_sqlite.sh

# 西风: 每30分钟
*/30 * * * * /bin/bash ~/Documents/OpenClawAgents/xifeng/scripts/run.sh
```

## 数据文件

### 北风
- `data/stocks.db` - SQLite数据库 (221MB)
- `data/all_stocks.json` - 股票列表
- `data/hot_spots.json` - 热点数据

### 西风
- `data/xifeng.db` - SQLite数据库
- `data/hot_spots.json` - 热点输出

## 自定义

所有 Agent 都是独立的，可以：
- 修改配置文件
- 调整定时任务
- 扩展功能模块
- 添加新数据源

## 注意

- 北风数据库较大 (221MB)，备份时注意
- 西风使用模拟数据，可接入真实RSS源
- 所有日志在 `logs/` 目录

---
*Created by 财神爷 - OpenClaw*
