# A股智能交易系统 - 详细设计文档 (SDD)

**版本**: v4.6.1  
**日期**: 2026-03-18

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OpenClaw 调度层                              │
│         (Cron定时任务 + Agent协同 + Redis事件驱动)               │
└─────────────────────────────────────────────────────────────────────┘
                                    │
    ┌─────────────────────────────────────────────────────────────┐
    │                    数据层                                   │
    │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
    │  │ stocks_real │ │   signals   │ │  portfolio  │     │
    │  │    .db     │ │   _v3.db    │ │    .db      │     │
    │  └──────────────┘ └──────────────┘ └──────────────┘     │
    └─────────────────────────────────────────────────────────────┘
                                    │
    ┌────────┬────────┬────────┬────────┬────────┬────────┐
    │        │        │        │        │        │        │
  ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐
  │北风 │ │西风 │ │东风 │ │南风 │ │红中 │ │发财│
  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬┘
     │      │      │      │      │      │
     └──────┴──────┴──────┴──────┴──────┴──────┘
```

---

## 2. 数据库设计

### 2.1 stocks_real.db

```sql
-- 股票主数据
CREATE TABLE master_stocks (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    market TEXT,
    sector TEXT,
    industry TEXT,
    updated_at TIMESTAMP
);

-- 日线数据
CREATE TABLE daily (
    stock_code TEXT,
    timestamp TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER, amount REAL,
    PRIMARY KEY (stock_code, timestamp)
);

-- 分钟数据
CREATE TABLE minute (
    stock_code TEXT,
    timestamp TEXT,
    open REAL, high REAL, low REAL, close REAL,
    volume INTEGER,
    PRIMARY KEY (stock_code, timestamp)
);
```

### 2.2 signals_v3.db

```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    stock_code TEXT,
    stock_name TEXT,
    strategy TEXT,
    version TEXT,
    entry_price REAL,
    stop_loss REAL,
    score REAL,
    sent_discord INTEGER
);
```

### 2.3 portfolio.db

```sql
-- 账户
CREATE TABLE account (
    id INTEGER PRIMARY KEY,
    cash_balance REAL,
    total_assets REAL
);

-- 持仓 (带追踪)
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT UNIQUE,
    name TEXT,
    quantity INTEGER,
    avg_price REAL,
    current_price REAL,
    stop_loss REAL,
    highest_price REAL,
    entry_time TIMESTAMP,
    entry_logic TEXT,
    sector TEXT,
    sector_heat TEXT,
    signal_id INTEGER,    -- 新增: 关联信号ID
    strategy TEXT,        -- 新增: 策略名称
    score REAL,          -- 新增: 评分
    updated_at TIMESTAMP
);

-- 交易记录 (带追踪)
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    action TEXT,
    symbol TEXT,
    name TEXT,
    price REAL,
    quantity INTEGER,
    total_amount REAL,
    fee REAL,
    logic TEXT,
    total_assets REAL,
    cash_balance REAL,
    signal_id INTEGER,   -- 新增
    strategy TEXT,       -- 新增
    score REAL           -- 新增
);
```

---

## 3. 核心模块设计

### 3.1 ATR计算器

```python
class ATRCalculator:
    def calculate_atr(self, stock_code: str, period: int = 14) -> float:
        """
        ATR = Average(True Range)
        True Range = max(H-L, |H-PC|, |L-PC|)
        """
        data = self.get_daily_data(stock_code, period + 1)
        tr_list = []
        for i in range(1, len(data)):
            tr = max(
                data[i]['high'] - data[i]['low'],
                abs(data[i]['high'] - data[i-1]['close']),
                abs(data[i]['low'] - data[i-1]['close'])
            )
            tr_list.append(tr)
        return sum(tr_list) / len(tr_list)
    
    def calculate_dynamic_stop_loss(
        self, stock_code, current_price, highest_price, k=2.0
    ) -> float:
        """动态止损 = 最高价 - k * ATR"""
        atr = self.calculate_atr(stock_code)
        return highest_price - (k * atr)
```

### 3.2 风险控制器

```python
class PortfolioRiskController:
    SECTOR_LIMIT = 0.30      # 行业30%
    DAILY_TRADE_LIMIT = 5    # 每日5笔
    
    def check_buy_risk(self, signal: Dict) -> (bool, str):
        # 1. 每日限额
        if self.get_today_trades_count() >= DAILY_TRADE_LIMIT:
            return False, "每日限额已达"
        
        # 2. 行业限制
        if not self.check_sector_limit(signal['code']):
            return False, "行业仓位超限"
        
        return True, "通过"
```

### 3.3 事件驱动

```python
class SignalPublisher:
    def publish_signal(self, signal: Dict):
        """发布信号到Redis"""
        self.redis.publish('trade_signals', json.dumps(signal))

class SignalSubscriber:
    def subscribe(self, callback):
        """订阅信号并执行"""
        self.redis.subscribe('trade_signals', callback)
```

---

## 4. 交易流程

### 4.1 买入流程

```
1. 红中生成信号 (score >= 65)
       ↓
2. Redis发布信号
       ↓
3. 发财订阅信号
       ↓
4. 风险检查 (每日限额/行业限制/资金)
       ↓
5. 涨停检查 (>=9.9% 禁止)
       ↓
6. 计算滑点 (price * 1.002)
       ↓
7. 写入持仓 + 交易记录 (含signal_id, strategy, score)
       ↓
8. 更新ATR动态止损
```

### 4.2 卖出流程

```
1. 触发止损条件
       ↓
2. 检查ATR动态止损
       ↓
3. 计算滑点 (price * 0.998)
       ↓
4. 扣除手续费 (amount * 0.0003)
       ↓
5. 更新交易记录 (含signal_id, strategy, score)
       ↓
6. 移除持仓
```

---

## 5. 流控设计

### 5.1 限流器

```python
class RateLimiter:
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window = window_seconds
        self.calls = deque()
    
    def allow(self) -> bool:
        """滑动窗口限流"""
        now = time.time()
        while self.calls and self.calls[0] < now - self.window:
            self.calls.popleft()
        
        if len(self.calls) >= self.max_calls:
            return False
        self.calls.append(now)
        return True
```

### 5.2 断路器

```python
class CircuitBreaker:
    def call(self, func):
        if self.state == OPEN:
            raise CircuitOpenError()
        
        try:
            result = func()
            self.on_success()
            return result
        except:
            self.on_failure()
            raise
```

---

## 6. 部署配置

### 6.1 Cron任务

| 任务 | 表达式 | 功能 |
|------|--------|------|
| minute | */5 9-11,13-14 | 分钟数据 |
| xifeng | */30 9-14 | 热点板块 |
| linked | 30 9-14 | 联动选股 |
| sentinel | 0 * * * * | 哨兵检测 |

### 6.2 Redis

```bash
# 启动
redis-server --daemonize yes

# 订阅
redis-cli subscribe trade_signals
```

---

*文档版本: v4.6.1*  
*最后更新: 2026-03-18*
