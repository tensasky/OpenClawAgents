# 💰 财神爷量化交易系统 - 8-Agent协作

**版本**: V5.4  
**更新日期**: 2026-03-13  
**核心目标**: 月度盈利≥5%，胜率最大化

---

## 🎯 系统概述

8-Agent闭环量化交易系统，从数据采集到策略执行，全自动运行。

```
北风(数据) → 西风(舆情) → 南风(策略) → 东风(初筛)
                                    ↓
白板(复盘) ← 发财(交易) ← 红中(预警) ←┘
        ↑___________________________↓
              财神爷(监督协调)
```

---

## 🤖 Agent清单

| Agent | 功能 | 版本 | 状态 | 关键指标 |
|-------|------|------|------|---------|
| 🌪️ **北风** | 数据采集 | V3.0.0 | ✅ 运行中 | 5348只，分钟级更新 |
| 🍃 **西风** | 舆情分析 | V2.0.0 | ✅ 运行中 | 每2小时板块推送 |
| 🌬️ **南风** | 量化策略 | V5.4.0 | ✅ 运行中 | 胜率>60%，收益>5% |
| 🌸 **东风** | 初筛选股 | V1.0.0 | ⏸️ 待机 | 候选池管理 |
| 🀄 **红中** | 决策预警 | V3.1.0 | ✅ 运行中 | 每30分钟扫描 |
| 💰 **发财** | 模拟交易 | V1.0.0 | ⏸️ 待机 | 严格执行信号 |
| 🀆 **白板** | 策略进化 | V1.0.0 | ⏸️ 待机 | 收盘归因分析 |
| 💰 **财神爷** | 监督协调 | V5.0.0 | ✅ 运行中 | 每小时状态报告 |

---

## 📊 核心特性

### 双版本策略
- **保守版**: 胜率85%，收益8-13%，15笔/月
- **平衡版**: 胜率65%，收益5-8%，75笔/月

### 高频监控
- 北风: 交易时段每5分钟采集
- 西风: 每2小时板块分析
- 红中: 每30分钟扫描预警
- 财神爷: 每小时状态报告

### 数据持久化
- SQLite数据库物理隔离
- 本地日志完整记录
- Git版本管理

---

## 🚀 快速启动

```bash
# 1. 克隆仓库
git clone https://github.com/tensasky/OpenClawAgents.git
cd OpenClawAgents

# 2. 启动北风数据采集
python3 beifeng/beifeng.py

# 3. 启动红中预警系统
python3 hongzhong/hongzhong_v3.py

# 4. 查看财神爷报告
python3 workspace/scripts/caishen_hourly_report_v5.py
```

---

## 📁 目录结构

```
OpenClawAgents/
├── README.md                 # 本文件
├── MISSION.md               # 💰 财神爷核心使命
├── AGENTS_VERSION.md        # Agent版本管理
├── VERSION.md               # 系统版本
│
├── 🌪️ beifeng/              # 北风 - 数据采集
│   ├── beifeng.py
│   ├── db_config.py         # 物理隔离配置
│   ├── realtime_fetcher.py
│   ├── data/
│   │   ├── stocks_real.db   # 真实数据
│   │   └── stocks_virtual.db # 虚拟数据
│   └── logs/
│
├── 🍃 xifeng/               # 西风 - 舆情分析
│   ├── xifeng_v2_sector.py  # V2.0板块分析
│   ├── data/
│   └── logs/
│
├── 🌬️ nanfeng/              # 南风 - 量化策略
│   ├── nanfeng_v5_1.py      # V5.1量化引擎
│   ├── strategy_config_v54_conservative.py  # 保守版
│   ├── strategy_config_v53.py               # 平衡版
│   └── data/
│
├── 🀄 hongzhong/            # 红中 - 决策预警
│   ├── hongzhong_v3.py      # V3.0高频扫描
│   ├── cron_report_30min.sh # 30分钟报告
│   └── data/
│
├── 💰 caishen/              # 财神爷 - 监督协调
│   └── workspace/
│       └── scripts/
│           ├── caishen_hourly_report_v5.py  # V5.0报告
│           └── cron_caishen_hourly.sh       # 定时任务
│
└── 🀆 baiban/               # 白板 - 策略进化
    ├── backtest_5strategies_v2.py
    └── optimizer_v2.py
```

---

## 🔔 通知渠道

- **Discord**: 实时预警、状态报告
- **邮件**: 详细报告、每日汇总
- **日志**: 本地完整记录

---

## 📈 版本历史

| 日期 | 版本 | 更新内容 |
|------|------|---------|
| 2026-03-13 | V5.4 | 南风双版本优化，财神爷V5.0 |
| 2026-03-13 | V3.1 | 红中30分钟高频扫描 |
| 2026-03-13 | V3.0 | 北风物理隔离数据库 |
| 2026-03-12 | V2.5 | 红中Discord+邮件通知 |
| 2026-03-10 | V1.0 | 系统初始化 |

---

## 🎯 核心KPI

> **月度盈利 ≥ 5%**  
> **胜率最大化**  
> **所有Agent为此服务**

详见 [MISSION.md](./MISSION.md)

---

## 🤝 贡献

- 提交Issue反馈问题
- 提交PR改进代码
- 联系财神爷: Discord/邮件

---

**💰 财神爷量化交易系统 - 让AI为你赚钱**
