# OpenClaw 量化交易系统 v4.3.0

## 📋 目录
1. [PRD产品需求](#1-prd产品需求)
2. [架构文档](#2-架构文档)
3. [代码逻辑](#3-代码逻辑)
4. [环境配置](#4-环境配置)
5. [工作流](#5-工作流)
6. [数据流](#6-数据流)
7. [配置手册](#7-配置手册)

---

## 1. PRD产品需求

### 产品定位
A股智能交易系统，9-Agent协同工作，实现全自动选股交易。

### 核心功能
- **数据采集**: 北风全量5,348只股票
- **候选池筛选**: 东风多维初筛
- **信号生成**: 红中策略评分
- **交易执行**: 发财风控下单
- **回测优化**: 白板自动进化
- **调度管理**: 财神爷三层架构

### KPI指标
- 月度盈利 ≥ 5%
- 选股延迟 < 5分钟
- 胜率 ≥ 55%

---

## 2. 架构文档

### Agent分工
| Agent | 职责 |
|-------|------|
| 北风 | 数据采集 |
| 西风 | 板块热点 |
| 东风 | 候选池筛选 |
| 南风 | 策略生成 |
| 红中 | 信号发射 |
| 发财 | 交易执行 |
| 白板 | 回测优化 |
| 判官 | 数据校验 |
| 财神爷 | 调度管理 |

### 架构图
```
财神爷(Manager)
    ↓
北风/东风/白板 → Redis → 红中 → 判官 → 发财 → signals.db
```

---

## 3. 代码逻辑

### 核心脚本
```bash
# 数据采集
python3 beifeng/beifeng.py <股票>

# 候选池
python3 dongfeng/dongfeng_v2.py

# 信号生成
python3 logs/quick_scan.py

# 交易执行
python3 facai/trading_loop.py

# 调度器
python3 manager/process_manager_v2.py
```

### 关键逻辑
- **因子工厂**: 动态计算MA20斜率、RSI等
- **价格保护**: 滑点>1.5%放弃
- **订单追踪**: 2分钟超时撤单
- **严格模式**: 数据缺口拒绝成交

---

## 4. 环境配置

### 依赖
- Python 3.9+
- Redis
- SQLite3
- macOS

### 路径
- 工作目录: ~/Documents/OpenClawAgents
- 数据: stocks_real.db (3.1GB)
- 信号: signals_v3.db
- 策略: strategy.db

### 安装
```bash
# launchd
cp manager/com.openclaw.trading.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.openclaw.trading.plist
```

---

## 5. 工作流

### 日间 (09:30-15:00)
```
每5分钟循环:
  1. 北风抓取数据 → Redis
  2. 东风筛选候选池
  3. 红中生成信号
  4. 判官校验
  5. 发财执行
```

### 盘后 (15:30+)
```
  1. 白板对账
  2. 生成daily_report.csv
  3. 参数优化
```

---

## 6. 数据流

### 实时数据
```
API → 北风 → Redis缓存 → 东风/红中 → signals表
```

### 策略流
```
白板(优化) → strategy.db → 红中(读取) → 信号
```

### 交易流
```
红中(信号) → 判官(校验) → 发财(执行) → signals(FILLED)
```

---

## 7. 配置手册

### 策略参数 (strategy.db)
```json
{
  "filters": {
    "min_ma20_slope": 0.002,
    "min_rsi": 40,
    "max_rsi": 75
  }
}
```

### 风控参数
| 参数 | 值 |
|------|-----|
| 总资金 | ¥100,000 |
| 单只上限 | ¥10,000 |
| 持仓上限 | 10只 |
| 仓位上限 | 80% |
| 滑点限制 | 1.5% |

### 启动命令
```bash
# 调度器
python3 manager/process_manager_v2.py

# 快速选股
python3 logs/quick_scan.py

# 对账
python3 facai/reconciliation.py
```
