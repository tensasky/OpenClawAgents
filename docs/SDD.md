# A股智能交易系统 - 详细设计文档 (SDD)

**版本**: v4.7.0  
**日期**: 2026-03-18

---

## 1. 系统架构

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OpenClaw 调度层                              │
│         (Cron + Agent协同 + Redis Streams)                    │
└─────────────────────────────────────────────────────────────────────┘
                                    │
    ┌─────────────────────────────────────────────────────────────┐
    │                    数据层                                    │
    │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │
    │  │ stocks_real │ │   signals   │ │  portfolio  │     │
    │  │    .db     │ │   _v3.db    │ │    .db      │     │
    │  └──────────────┘ └──────────────┘ └──────────────┘     │
    └─────────────────────────────────────────────────────────────┘
```

---

## 2. 核心模块

### 2.1 事件驱动 (Redis Streams)

```python
class SignalPublisher:
    def publish_signal(self, signal):
        # 添加到Stream
        msg_id = self.redis.xadd(STREAM_SIGNALS, signal)
        return msg_id

class SignalSubscriber:
    def on_message(self, msg):
        # 处理消息
        self.redis.xack(STREAM_SIGNALS, CONSUMER_GROUP, msg_id)
```

### 2.2 T+1交易限制

```python
# 买入时设置
INSERT INTO positions (..., is_sellable) VALUES (..., 0)

# 15:00后解锁
UPDATE positions SET is_sellable = 1 WHERE is_sellable = 0

# 卖出前检查
IF is_sellable == 0:
    return False  # T+1限制
```

### 2.3 ATR动态止损

```python
def calculate_atr(stock_code, period=14):
    # ATR = Average(True Range)
    # True Range = max(H-L, |H-PC|, |L-PC|)
    return sum(tr_list) / len(tr_list)

def dynamic_stop_loss(price, highest, atr, k=2.0):
    return highest - (k * atr)
```

### 2.4 板块相关性

```python
SECTOR_CORRELATION = {
    "科技集群": ["半导体", "人工智能", "电子"],
    "新能源集群": ["光伏", "锂电", "电池"],
    "消费集群": ["白酒", "食品", "家电"],
}

# 限制单集群≤40%
if cluster_exposure / total > 0.40:
    return False
```

### 2.5 跌停预警

```python
def check_limit_down(symbol):
    # 获取实时涨跌幅
    if change_pct <= -9.9:
        # 触发预警
        notify_alert("跌停", f"{symbol}跌停{change_pct}%")
```

---

## 3. 数据库设计

### 3.1 portfolio.db

```sql
-- 持仓
CREATE TABLE positions (
    ...
    is_sellable INTEGER DEFAULT 0,  -- T+1
    signal_id INTEGER,
    strategy TEXT,
    score REAL
);
```

---

## 4. 部署配置

### 4.1 Cron任务

| 任务 | 表达式 | 功能 |
|------|--------|------|
| sentinel | 0 * * * * | 哨兵检测 |
| xifeng | */30 9-14 | 热点板块 |
| linked | 30 9-14 | 联动选股 |

---

*文档版本: v4.7.0*  
*最后更新: 2026-03-18*
