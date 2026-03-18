# 代码逻辑解释文档

**版本**: v4.7.0  
**日期**: 2026-03-18

---

## 1. 核心模块

### 1.1 Redis Streams 事件驱动

**vs Pub/Sub**:
- Pub/Sub: 发后即忘，消息可能丢失
- Streams: 持久化 + ACK确认

```python
# 发布
msg_id = redis.xadd('trade_signals', signal)

# 消费
redis.xread({stream: last_id})
redis.xack(stream, group, msg_id)
```

---

### 1.2 T+1 交易限制

**逻辑**:
```python
# 买入
INSERT INTO positions (is_sellable) VALUES (0)

# 卖出前检查
IF is_sellable == 0:
    raise "T+1限制"

# 15:00后解锁
UPDATE positions SET is_sellable = 1
```

---

### 1.3 ATR动态止损

**公式**:
```
StopLoss = HighestPrice - (k × ATR)
k = 2.0 (可调整)
```

**优势**: 自动适应波动率

---

### 1.4 板块相关性

**集群划分**:
- 科技集群: 半导体/AI/电子
- 新能源集群: 光伏/锂电/电池
- 消费集群: 白酒/食品/家电
- 金融集群: 银行/保险/证券
- 医药集群: 医药/医疗器械

**限制**: 单集群 ≤ 40%

---

### 1.5 跌停预警

**检测**:
```python
if change_pct <= -9.9:
    # 触发预警
    notify_alert("跌停", f"{symbol}跌停{change_pct}%")
```

---

### 1.6 滑点分析

**计算**:
```python
# 买入滑点 = (成交价 - 信号价) / 信号价
expected = entry_price * 1.002  # 上浮0.2%
slippage = (actual_price - expected) / expected * 100
```

---

## 2. 交易流程

```
信号生成 → Redis Streams → 消费检查 → T+1 → 行业/相关性 → 买入
                                          ↓
                              15:00后解锁is_sellable
```

---

## 3. 核心参数

| 参数 | 值 | 说明 |
|------|------|------|
| ATR周期 | 14 | |
| ATR倍数 | 2.0 | 止损 |
| 滑点 | 0.2% | 买入上浮/卖出下浮 |
| 手续费 | 0.03% | 仅卖出 |
| 集群上限 | 40% | 相关性限制 |
| T+1容差 | 0.1% | 对账 |

---

*文档版本: v4.7.0*
