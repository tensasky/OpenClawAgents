# OpenClawAgents 目录结构

**版本**: V3.3.0  
**更新日期**: 2026-03-14  
**系统**: 财神爷量化交易系统

---

## 📁 根目录

```
OpenClawAgents/
├── README.md              # 系统说明文档
├── CHANGELOG.md           # 版本历史记录
├── MISSION.md             # 核心使命文档
├── STRUCTURE.md           # 本文件 - 目录结构
├── archive/               # 历史版本归档
└── [Agent目录...]
```

---

## 🤖 Agent目录结构

### 🌪️ 北风 (beifeng/) - 数据采集 V3.0
```
beifeng/
├── beifeng.py             # 主采集程序
├── db_config.py           # 数据库配置
├── data/
│   ├── stocks_real.db     # 真实数据（物理隔离）
│   └── stocks_virtual.db  # 虚拟数据
└── logs/                  # 运行日志
```

### ⚖️ 判官 (judge/) - 数据验证 V1.0
```
judge/
├── judge_agent.py         # 数据验证Agent
├── README.md              # 判官说明文档
└── reports/               # 验证报告
```

### 🍃 西风 (xifeng/) - 舆情分析 V2.0
```
xifeng/
├── xifeng_v2_sector.py    # 板块分析（当前版本）
├── discord_notify.py      # Discord推送
├── data/
│   └── hot_spots.json     # 热点数据
└── [其他采集器...]
```

### 🌬️ 南风 (nanfeng/) - 量化策略 V5.4
```
nanfeng/
├── nanfeng_v5_1.py                    # 主策略程序（当前版本）
├── strategy_config_v53.py             # 平衡版配置
├── strategy_config_v54_conservative.py # 保守版配置
├── backtest_v5_1.py                   # 回测程序
├── data/                              # 策略数据
└── logs/                              # 运行日志
```

### 🌸 东风 (dongfeng/) - 盘中监控 V2.0
```
dongfeng/
└── dongfeng_v2.py         # 盘中监控+资金流向（当前版本）
```

### 🀄 红中 (hongzhong/) - 决策预警 V3.3
```
hongzhong/
├── hongzhong_v33.py       # 预警主程序（当前版本）
├── discord_table_format.py # Discord表格格式
├── data/
│   └── signals_v3.db      # 信号数据库
└── reports/               # 预警报告
```

### 💰 发财 (facai/) - 模拟交易 V2.0
```
facai/
├── facai_v2.py            # 交易主程序（当前版本）
└── data/
    └── portfolio_v2.db    # 持仓数据库
```

### 🀆 白板 (baiban/) - 策略进化 V1.0
```
baiban/
└── reports/               # 复盘报告
```

### 💰 财神爷 (workspace/scripts/) - 监督协调 V5.1
```
workspace/scripts/
├── caishen_hourly_report_v5.py  # 每小时报告（V5.0）
├── caishen_monitor_v51.py       # 静默监控（V5.1）
├── cron_caishen_monitor.sh      # 监控定时脚本
└── logs/                        # 监控日志
```

---

## 📦 archive/ 归档目录

```
archive/
├── nanfeng/               # 南风历史版本
│   ├── nanfeng_v2.py
│   ├── nanfeng_v3.py
│   ├── nanfeng_v4.py
│   └── nanfeng_v5.py
├── hongzhong/             # 红中历史版本
│   ├── hongzhong_v2.py
│   ├── hongzhong_v3.py
│   └── hongzhong_v32_notification.py
├── beifeng/               # 北风历史版本
│   └── [历史文件...]
├── xifeng/                # 西风历史版本
│   └── [历史文件...]
├── dongfeng/              # 东风历史版本
├── facai/                 # 发财历史版本
└── workspace/             # 工作空间历史
    └── [历史脚本...]
```

---

## 🔄 版本管理规范

### 当前版本文件
- 保留在Agent根目录
- 命名规范: `{agent}_v{版本号}.py`

### 历史版本归档
- 移动到 `archive/{agent}/`
- 保留完整历史，便于回溯
- 归档时保留原文件名

### 版本标签
- GitHub保留最新3个版本tag
- 命名规范: `{agent}-v{版本号}` 或 `v{版本号}`

---

## 🚀 快速导航

| 需要查看... | 访问路径 |
|------------|---------|
| 最新策略代码 | `nanfeng/nanfeng_v5_1.py` |
| 预警信号 | `hongzhong/data/signals_v3.db` |
| 监控日志 | `workspace/scripts/logs/` |
| 历史版本 | `archive/` |
| 系统文档 | `README.md`, `MISSION.md` |

---

**最后更新**: 2026-03-14  
**维护者**: 财神爷
