# A股智能交易系统 - 详细设计文档 (SDD)

**版本**: v4.3.0  
**日期**: 2026-03-18

---

## 1. 系统架构设计

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     OpenClaw 调度层                           │
│         (Cron定时任务 + Agent协同 + Discord通知)              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
    ┌─────────────────────────────────────────────────────────┐
    │                    数据层                               │
    │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │
    │  │ stocks_real │ │   signals   │ │  portfolio  │  │
    │  │    .db     │ │   _v3.db    │ │    .db      │  │
    │  └──────────────┘ └──────────────┘ └──────────────┘  │
    └─────────────────────────────────────────────────────────┘
                                    │
    ┌────────┬────────┬────────┬────────┬────────┬────────┐
    │        │        │        │        │        │        │
  ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐ ┌─▼──┐
  │北风 │ │西风 │ │东风 │ │南风 │ │红中 │ │发财│
  └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬─┘ └──┬┘
     │      │      │      │      │      │
     └──────┴──────┴──────┴──────┴──────┴──────┘
```

### 1.2 模块设计

---

## 2. 数据库设计

### 2.1 stocks_real.db

```sql
-- 股票主数据
CREATE TABLE master_stocks (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT,
    market TEXT,           -- 市场 (SH/SZ)
    sector TEXT,           -- 所属板块
    industry TEXT,         -- 所属行业
    company_name TEXT,     -- 公司名称
    business_scope TEXT,   -- 经营范围
    total_shares REAL,    -- 总股本
    float_shares REAL,    -- 流通股本
    updated_at TIMESTAMP
);

-- 日线数据
CREATE TABLE daily (
    id INTEGER PRIMARY KEY,
    stock_code TEXT,
    timestamp TEXT,        -- 交易日期
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    amount REAL,
    source TEXT            -- 数据来源
);

-- 分钟数据
CREATE TABLE minute (
    stock_code TEXT,
    timestamp TEXT,        -- 具体时间
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    PRIMARY KEY (stock_code, timestamp)
);
```

### 2.2 signals_v3.db

```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,         -- 信号时间
    stock_code TEXT,       -- 股票代码
    stock_name TEXT,       -- 股票名称
    strategy TEXT,         -- 策略名称
    version TEXT,         -- 版本
    entry_price REAL,     -- 买入价格
    stop_loss REAL,       -- 止损价格
    target_1 REAL,        -- 目标价1
    target_2 REAL,        -- 目标价2
    score REAL,           -- 评分
    sent_discord INTEGER   -- 是否已通知
);
```

### 2.3 portfolio.db

```sql
-- 账户
CREATE TABLE account (
    id INTEGER PRIMARY KEY,
    cash_balance REAL,     -- 现金余额
    total_assets REAL     -- 总资产
);

-- 持仓
CREATE TABLE positions (
    id INTEGER PRIMARY KEY,
    symbol TEXT,          -- 股票代码
    stock_name TEXT,
    quantity INTEGER,      -- 股数
    avg_price REAL,        -- 平均成本
    current_price REAL,   -- 当前价
    stop_loss REAL,       -- 止损价
    highest_price REAL,    -- 最高价(用于移动止损)
    entry_time TEXT,      -- 买入时间
    entry_logic TEXT      -- 买入理由
);

-- 交易记录
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    action TEXT,          -- BUY/SELL
    symbol TEXT,
    stock_name TEXT,
    price REAL,
    quantity INTEGER,
    total_amount REAL,
    fee REAL,
    profit REAL,          -- 盈亏
    logic TEXT            -- 交易逻辑
);
```

---

## 3. 核心模块设计

### 3.1 北风 (数据采集)

```python
class BeiFeng:
    """数据采集模块"""
    
    def fetch_daily(self, stocks: List[str]):
        """采集日线"""
        for stock in stocks:
            # 腾讯API → 新浪备用
            data = self.fetcher.fetch(stock, 'daily')
            self.db.save(data)
    
    def fetch_minute(self, stocks: List[str]):
        """采集分钟数据"""
        # 批量采集，每批50只
        for batch in batches(stocks, 50):
            data = self.fetcher.fetch(batch, 'minute')
            self.db.save(data)
```

### 3.2 西风 (热点板块)

```python
class XiFeng:
    """热点板块识别"""
    
    def get_hot_sectors(self) -> List[SectorData]:
        """获取热点板块"""
        # 1. 东方财富API获取板块排行
        sectors = self.eastmoney.get_sectors()
        
        # 2. 计算热度分数
        for s in sectors:
            s.heat_score = s.change_pct * 0.4 + s.volume * 0.3 + s.news_count * 0.3
        
        # 3. 返回Top5
        return sorted(sectors, key=lambda x: x.heat_score, reverse=True)[:5]
```

### 3.3 东风 (候选池)

```python
class DongFeng:
    """候选股筛选"""
    
    def filter_stocks(self, sector: str) -> List[Stock]:
        """筛选活跃股票"""
        stocks = self.get_sector_stocks(sector)
        
        # 筛选条件
        result = []
        for stock in stocks:
            # 量比 > 2
            if stock.volume_ratio > 2:
                result.append(stock)
            # 或 振幅 > 3%
            elif stock.amplitude > 3:
                result.append(stock)
        
        return result
```

### 3.4 南风 (策略评分)

```python
class NanFeng:
    """策略评分"""
    
    STRATEGIES = {
        '趋势跟踪': {'weight': 0.3, 'factors': ['ma20', 'ma60']},
        '突破策略': {'weight': 0.25, 'factors': ['break_high']},
        '涨停监控': {'weight': 0.2, 'factors': ['limit_up']},
        '均值回归': {'weight': 0.15, 'factors': ['pe_ratio']},
        '热点追击': {'weight': 0.1, 'factors': ['sector_heat']},
    }
    
    def calculate_score(self, stock: Stock) -> float:
        """计算综合评分"""
        score = 50.0  # 基础分
        
        for strategy, config in self.STRATEGIES.items():
            factor_score = self.calculate_factor(stock, config['factors'])
            score += factor_score * config['weight']
        
        return min(score, 100)
```

### 3.5 红中 (交易信号)

```python
class HongZhong:
    """交易信号生成"""
    
    def generate_signals(self, stocks: List[Stock]) -> List[Signal]:
        """生成信号"""
        signals = []
        
        for stock in stocks:
            score = self.nanfeng.calculate_score(stock)
            
            # 评分>=65分生成信号
            if score >= 65:
                signal = Signal(
                    stock_code=stock.code,
                    stock_name=stock.name,
                    score=score,
                    entry_price=stock.price * 1.02,  # 开盘+2%
                    stop_loss=stock.price * 0.95,   # 止损-5%
                    strategy='南风V5.5'
                )
                signals.append(signal)
        
        return signals
```

### 3.6 发财 (模拟交易)

```python
class FaCai:
    """模拟交易"""
    
    SLIPPAGE = 0.002      # 滑点0.2%
    SELL_FEE = 0.0003     # 手续费万分之3
    MAX_POSITION = 0.5     # 单股最大50%
    
    def buy(self, signal: Signal):
        """买入"""
        # 滑点: 买入价上浮
        price = signal.price * (1 + self.SLIPPAGE)
        
        # 计算股数(100股整数)
        amount = self.cash * self.MAX_POSITION
        quantity = int(amount / price / 100) * 100
        
        # 扣手续费
        total = quantity * price
        fee = total * self.SELL_FEE
        
        if self.cash >= total + fee:
            self.cash -= (total + fee)
            self.positions.append(Position(...))
    
    def sell(self, position: Position, reason: str):
        """卖出"""
        # 滑点: 卖出价下浮
        price = position.current_price * (1 - self.SLIPPAGE)
        
        # 扣手续费
        total = position.quantity * price
        fee = total * self.SELL_FEE
        profit = total - position.cost - fee
        
        self.cash += (total - fee)
        self.trades.append(Trade(...))
```

### 3.7 联动选股

```python
class LinkedWorkflow:
    """联动选股工作流"""
    
    def run(self):
        # Step 1: 西风 - 热点板块
        sectors = XiFeng().get_hot_sectors()
        
        # Step 2: 东风 - 板块选股
        candidates = []
        for sector in sectors:
            stocks = DongFeng().filter_stocks(sector)
            candidates.extend(stocks)
        
        # Step 3: 南风 - 策略评分
        scored = [s for s in candidates if NanFeng().calculate_score(s) >= 60]
        
        # Step 4: 红中 - 生成信号
        signals = HongZhong().generate_signals(scored)
        
        # Step 5: 发财 - 执行交易
        for signal in signals:
            FaCai().buy(signal)
```

---

## 4. API设计

### 4.1 统一日志

```python
from utils.agent_logger import get_logger

log = get_logger("模块名")
log.info("信息")
log.warning("警告")
log.error("错误")
log.success("成功")
```

### 4.2 统一数据库

```python
from utils.db_pool import get_pool

pool = get_pool(db_path)
conn = pool.get_connection()
# 使用数据库
pool.release_connection(conn)
```

### 4.3 统一通知

```python
from utils.notify import send_discord, send_email

# Discord通知
send_discord("消息内容")

# 邮件通知
send_email("主题", "内容")
```

---

## 5. 部署配置

### 5.1 环境变量

```bash
# Discord
HONGZHONG_DISCORD_WEBHOOK=...

# Email
HONGZHONG_EMAIL_PASSWORD=...

# 数据库
DATABASE_PATH=...
```

### 5.2 Cron配置

```bash
# 分钟数据
*/5 9-11,13-14 * * 1-5 ./cron_minute_hf.sh

# 热点板块
*/30 9-11,13-14 * * 1-5 python3 xifeng/xifeng_v2_sector.py

# 联动选股
30 9-11,13-14 * * 1-5 python3 linked_workflow.py

# 系统监控
0 * * * * python3 scripts/caishen_monitor_v52.py
```

---

## 6. 异常处理

### 6.1 断路器模式

```python
class CircuitBreaker:
    def call(self, func):
        if self.failure_count > 5:
            # 连续5次失败，熔断
            return self.fallback()
        
        try:
            result = func()
            self.success()
            return result
        except Exception as e:
            self.failure()
            raise
```

### 6.2 重试机制

```python
def retry(max_attempts=3, delay=1):
    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            if attempt < max_attempts - 1:
                time.sleep(delay * 2 ** attempt)  # 指数退避
            raise
```

---

## 7. 版本管理

### 7.1 Git分支

- `main` - 生产分支
- `develop` - 开发分支

### 7.2 版本标签

```bash
git tag -a v4.3.0 -m "版本描述"
git push origin v4.3.0
```

### 7.3 备份

```bash
# 本地备份
bash backup_core.sh v4.3.0

# 远程备份
git push origin main --tags
```

---

*文档版本: v4.3.0*  
*最后更新: 2026-03-18*
