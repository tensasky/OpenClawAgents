# 代码逻辑解释文档

**版本**: v4.6.1  
**日期**: 2026-03-18

---

## 1. 核心模块

### 1.1 utils/risk_control.py - 风险控制

#### ATR计算器 (ATRCalculator)

**作用**: 计算平均真实波幅，用于动态止损

```python
# 核心公式
ATR = Σ(True Range) / N

# True Range = max(H-L, |H-PC|, |L-PC|)
# H: 当日最高价
# L: 当日最低价
# PC: 前一日收盘价
```

**动态止损公式**:
```
StopLoss = HighestPrice - (k × ATR)
k = 2.0 (可调整)
```

**示例**:
```
贵州茅台 (sh600519):
- 最高价: 1550.00
- ATR: 28.24
- 动态止损: 1550 - (2 × 28.24) = 1493.52
```

#### 组合风控 (PortfolioRiskController)

**行业限制**:
- 单一行业持仓 ≤ 30%
- 目的: 防止行业集中风险

**每日限额**:
- 每日最多 5 笔交易
- 目的: 防止极端行情下频繁操作

---

### 1.2 utils/event_bus.py - 事件驱动

#### 发布/订阅模式

```
发布者(红中) → Redis Channel → 订阅者(发财)
```

**优点**:
- 实时响应 (秒级)
- 解耦系统组件
- 支持多订阅者

---

### 1.3 utils/flow_control.py - 流控

#### RateLimiter (限流器)

**算法**: 滑动窗口

```
时间轴: ──────────────────────────────>
        [←── window ──→]
        |  1  |  2  |  3  |  4  |  5  |
        
超过max_calls时拒绝请求
```

#### CircuitBreaker (断路器)

**状态机**:

```
CLOSED (正常) ──失败5次──→ OPEN (断开)
   ↑                      │
   │                      ↓
   └──成功2次── HALF_OPEN (半开) ──失败──→ OPEN
```

---

### 1.4 utils/sentinel.py - 哨兵

#### 心跳监测

**分钟数据**:
- 超时阈值: 10分钟
- 状态: ok / warning / critical

**数据对账**:
```
账户总额 = 现金 + 持仓市值
差异容差: 100元
```

---

### 1.5 facai/facai.py - 交易模块

#### 买入逻辑

```python
# 1. 风险检查
can_buy, reason = check_buy_risk(signal)
if not can_buy:
    return False

# 2. 涨停检查
if is_limit_up(code, price):
    return False

# 3. 计算滑点
actual_price = price * 1.002  # 上浮0.2%

# 4. 计算股数 (100股整数)
quantity = int(cash * 0.5 / actual_price / 100) * 100

# 5. 记录持仓 (含signal_id, strategy, score)
```

#### 卖出逻辑

```python
# 1. 止损检查
if current_price < position.stop_loss:
    reason = "止损"

# 2. ATR动态止损更新
new_sl = update_stop_loss(symbol, current_price, highest)

# 3. 滑点计算
actual_price = price * 0.998  # 下浮0.2%

# 4. 手续费
fee = amount * 0.0003  # 万分之3

# 5. 记录交易 (含追踪字段)
```

---

## 2. 数据库追踪

### 2.1 信号→持仓→交易

```sql
-- 1. 红中生成信号
INSERT INTO signals (score, strategy) 
VALUES (85, '趋势跟踪');
-- 返回 signal_id = 123

-- 2. 发财买入，记录signal_id
INSERT INTO positions (symbol, signal_id, strategy, score)
VALUES ('sh600519', 123, '趋势跟踪', 85);

-- 3. 卖出时追溯
INSERT INTO trades (symbol, signal_id, strategy, score)
VALUES ('sh600519', 123, '趋势跟踪', 85);
```

### 2.2 复盘分析

```sql
-- 按策略统计收益
SELECT 
    strategy,
    AVG(profit) as avg_profit,
    COUNT(*) as trade_count
FROM trades
WHERE action = 'SELL'
GROUP BY strategy;

-- 按信号评分统计
SELECT 
    CASE 
        WHEN score >= 80 THEN '高评分'
        WHEN score >= 70 THEN '中评分'
        ELSE '低评分'
    END as score_level,
    AVG(profit) as avg_profit
FROM trades
GROUP BY score_level;
```

---

## 3. 交易规则详解

### 3.1 滑点

| 方向 | 公式 | 示例 |
|------|------|------|
| 买入 | price × 1.002 | 1000 → 1002 |
| 卖出 | price × 0.998 | 1000 → 998 |

### 3.2 手续费

- 仅卖出收取
- 费率: 0.03% (万分之3)
- 计算: 卖出金额 × 0.0003

### 3.3 止损

| 类型 | 公式 |
|------|------|
| 固定止损 | price × 0.95 |
| ATR动态 | highest - k × ATR |

---

## 4. 流程图

### 4.1 完整交易流程

```
┌─────────────┐
│  北风采集   │ ──→ stocks_real.db
└─────────────┘
      ↓
┌─────────────┐
│  西风热点   │ ──→ hot_spots.json
└─────────────┘
      ↓
┌─────────────┐
│  东风筛选   │ ──→ candidates.db
└─────────────┘
      ↓
┌─────────────┐
│  南风评分   │ ──→ signals_v3.db
└─────────────┘
      ↓
┌─────────────┐
│  红中信号   │ ──→ Redis发布
└─────────────┘
      ↓
┌─────────────┐
│  发财交易   │ ←── 风险检查
│             │ ←── 涨停检查
│             │ ←── ATR止损
└─────────────┘
      ↓
┌─────────────┐
│  哨兵监控   │ ──→ Discord告警
└─────────────┘
```

---

## 5. 配置参数

| 参数 | 值 | 说明 |
|------|------|------|
| ATR_PERIOD | 14 | ATR计算周期 |
| ATR_MULTIPLIER | 2.0 | ATR倍数 |
| SECTOR_LIMIT | 0.30 | 行业限制 |
| DAILY_TRADE_LIMIT | 5 | 每日限额 |
| STRATEGY_INITIAL_CAPITAL | 100000 | 策略资金 |
| SLIPPAGE | 0.002 | 滑点 |
| SELL_FEE_RATE | 0.0003 | 手续费 |
| MIN_SCORE | 65 | 信号阈值 |

---

*文档版本: v4.6.1*
