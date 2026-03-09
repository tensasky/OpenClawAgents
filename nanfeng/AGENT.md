# AGENT.md - 南风V3 (NanFeng V3)

## 身份
- **Name:** 南风V3
- **Role:** 实时量化分析引擎
- **Emoji:** 🌪️
- **Parent:** 财神爷系统
- **进化**: 从"打分器"进化为"量化策略引擎"

## 核心进化

### V1 → V2 → V3
- **V1**: 基础技术指标打分
- **V2**: 西风舆情 + 北风数据 + LAMI尾盘异动
- **V3**: 实时量化引擎 + 自适应指标 + 具体交易参数

## V3核心功能

### 1. 分钟数据实时汇聚
- 1分钟数据 → 小时线 → 日线
- 实时计算盘中状态
- 量比、涨跌幅、趋势实时更新

### 2. 自适应技术指标
根据市场状态自动调整参数:
- **趋势市(trending)**: 短周期均线(5/10/20)
- **震荡市(ranging)**: 长周期均线(10/20/60)
- **高波动(volatile)**: 超短周期(3/8/15) + 快速RSI

### 3. 量化策略输出
不只是打分，输出具体交易参数:
```python
{
    'signal_type': 'BUY',
    'entry_price': 10.5,
    'entry_range': (10.4, 10.6),
    'stop_loss': 9.98,
    'take_profit': 11.34,
    'risk_reward': 2.5,
    'strategy': '趋势跟踪',
    'confidence': 0.75,
    'holding_period': 5
}
```

### 4. 策略类型
- **趋势跟踪**: 均线多头排列 + MACD水上
- **均值回归**: 布林带下轨 + RSI超卖
- **MACD金叉**: 底背离 + 放量

### 5. 风控参数
- **止损**: 2倍ATR或5%固定
- **止盈**: 3倍ATR或8%固定
- **盈亏比**: 强制≥1.5

## 使用方式

### 盘中实时扫描
```bash
# 扫描全市场，找出置信度≥0.6的信号
python3 nanfeng_v3.py --scan --min-confidence 0.6
```

### 单只股票分析
```bash
python3 nanfeng_v3.py --stock sh600519
```

### 定时任务（交易时段每30分钟）
```bash
*/30 9,10,11,13,14 * * 1-5 /usr/bin/python3 /Users/roberto/Documents/OpenClawAgents/nanfeng/nanfeng_v3.py --scan >> /tmp/nanfeng_v3.log 2>&1
```

## 数据依赖

### 实时数据
- **分钟数据**: 北风实时采集（交易时段每分钟更新）
- **日线数据**: 北风历史数据 + 分钟数据聚合

### 数据源
- 北风数据库: `~/.openclaw/agents/beifeng/data/stocks.db`
- 分钟表: `kline_data` (data_type='1min')
- 日表: `kline_data` (data_type='daily')

## 输出文件
- 信号文件: `~/Documents/OpenClawAgents/nanfeng/signals/signals_YYYYMMDD_HHMMSS.json`
- 日志文件: `~/Documents/OpenClawAgents/nanfeng/logs/nanfeng_v3_YYYYMMDD.log`

## 关键指标说明

### 自适应参数
| 市场状态 | 均线周期 | MACD参数 | RSI周期 |
|---------|---------|---------|---------|
| 趋势市 | 5/10/20 | 12/26/9 | 14 |
| 震荡市 | 10/20/60 | 12/26/9 | 14 |
| 高波动 | 3/8/15 | 8/17/9 | 6 |

### ATR止损
- 止损价 = 入场价 - 2×ATR
- 止盈价 = 入场价 + 3×ATR
- 盈亏比 = 3:2 = 1.5

## 版本
- v3.0.0 (2026-03-09) - 实时量化引擎
- v2.0.0 (2026-03-09) - 西风+北风+LAMI
- v1.0.0 (2026-03-09) - 基础技术指标

## 工作目录
`/Users/roberto/Documents/OpenClawAgents/nanfeng/`
