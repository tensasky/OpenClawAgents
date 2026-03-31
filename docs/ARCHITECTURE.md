# A股智能交易系统 - 架构设计文档

## 版本: v4.3.0
## 更新日期: 2026-03-26

---

## 一、系统概述

### 1.1 设计目标
- **全量实时数据**: 覆盖全部 5,348 只 A股股票
- **9-Agent协同**: 专业化分工，端到端自动化
- **数据驱动决策**: 纯数据驱动，不依赖主观判断

### 1.2 核心KPI
- 月度盈利 ≥ 5%
- 胜率最大化
- 全量数据覆盖 (5,348只)

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户层 (Telegram)                              │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          通知层 (Unified Notifier)                       │
│                    Email / Telegram / Discord 多通道                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌─────────────┬───────────┬────────────┬──────────┐
        ▼             ▼           ▼            ▼          ▼
    ┌───────┐   ┌───────┐   ┌────────┐  ┌───────┐  ┌────────┐
    │ 北风  │   │ 西风  │   │  东风   │  │ 南风  │  │  红中  │
    │数据采集│   │板块热点│   │候选池扫描│  │策略评分│  │信号通知│
    └───────┘   └───────┘   └────────┘  └───────┘  └────────┘
        │             │           │            │          │
        └─────────────┴───────────┴────────────┴──────────┘
                                    │
                                    ▼
        ┌─────────────┬───────────┬────────────┐
        ▼             ▼           ▼            ▼
    ┌───────┐   ┌───────┐   ┌────────┐  ┌────────┐
    │ 发财  │   │  白板  │   │  判官  │  │ 财神爷 │
    │模拟交易│   │策略优化│   │数据验证│  │  监控  │
    └───────┘   └───────┘   └────────┘  └────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        数据层 (SQLite + AKShare)                        │
│              主数据库 + 连接池 + WAL模式 + 进程锁                        │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent分工

| Agent | 名称 | 职责 | 关键文件 |
|-------|------|------|----------|
| 北风 | 数据采集 | 全量5,348只股票日线/分钟数据 | beifeng/beifeng.py |
| 西风 | 板块热点 | 行业/概念/地域板块分析 | xifeng/xifeng_v2_sector.py |
| 东风 | 候选池 | 个股基本面+技术面初筛 | dongfeng/dongfeng.py |
| 南风 | 策略评分 | 多策略评分排序 | nanfeng/nanfeng_v5_1.py |
| 红中 | 信号通知 | 生成交易信号+邮件发送 | hongzhong/generate_signals_multi.py |
| 发财 | 模拟交易 | 模拟买入/卖出执行 | facai/facai.py |
| 白板 | 策略优化 | 策略回测与优化 | baiban/baiban.py |
| 判官 | 数据验证 | 数据完整性校验 | judge/judge.py |
| 财神爷 | 监控 | 系统监控+告警 | caishen/caishen.py |

---

## 三、数据采集策略

### 3.1 采集频率

#### 北风 - 数据采集 (核心)

| 数据类型 | 采集频率 | 覆盖范围 | 数据源 |
|----------|----------|----------|--------|
| 日线数据 | 每日09:30前 | 5,348只 | AKShare |
| 分钟数据 | 每5分钟 | 100只核心股 | Sina/Tencent |
| 实时快照 | 交易时段每5分钟 | 全部5,348只 | 腾讯/新浪 |

#### Cron任务配置

```crontab
# 北风 - 每5分钟采集实时数据
*/5 9-11,13-14 * * 1-5 /Users/roberto/scripts/run_beifeng.sh

# 西风 - 每30分钟板块热点
30 9-11,13-14 * * 1-5 /usr/bin/python3 .../xifeng_v2_sector.py

# 南风 - 每35分钟策略评分
35 9-11,13-14 * * 1-5 /usr/bin/python3 .../nanfeng_v5_1.py

# 红中 - 每40分钟生成信号
40 9-11,13-14 * * 1-5 /usr/bin/python3 .../generate_signals_multi.py
```

### 3.2 双重采集机制

```python
# 快速采集: 每2分钟500只 (核心股)
# 全量采集: 每小时5,348只
# 防重复: 自动跳过已采集股票
```

### 3.3 数据源

| 数据源 | 用途 | 特点 |
|--------|------|------|
| AKShare | 日线数据 | 稳定，覆盖全 |
| 新浪财经 | 实时行情 | 快速，免费 |
| 腾讯财经 | 实时行情 | 快速，备用 |
| Baostock | 基本面数据 | 行业/板块信息 |

---

## 四、数据库设计

### 4.1 主数据库: stocks_real.db

**路径**: `~/Documents/OpenClawAgents/beifeng/data/stocks_real.db`

#### 表结构

```sql
-- K线数据表 (日线/分钟)
CREATE TABLE kline_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,           -- 股票代码 (e.g. sh600519)
    data_type TEXT,            -- daily/minute/5min/60min
    timestamp TIMESTAMP,       -- 时间戳
    open REAL,                 -- 开盘价
    high REAL,                 -- 最高价
    low REAL,                 -- 最低价
    close REAL,               -- 收盘价
    volume INTEGER,           -- 成交量
    amount REAL,              -- 成交额
    source TEXT,              -- 数据源
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(stock_code, data_type, timestamp)
);

-- 同步状态表
CREATE TABLE sync_status (
    stock_code TEXT,
    data_type TEXT,
    last_sync TIMESTAMP,
    last_success TIMESTAMP,
    record_count INTEGER DEFAULT 0,
    PRIMARY KEY (stock_code, data_type)
);

-- 抓取日志
CREATE TABLE fetch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,
    data_type TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT,
    records_count INTEGER,
    source TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 错误任务表
CREATE TABLE error_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,
    data_type TEXT,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    error_msg TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- 数据缺口表
CREATE TABLE data_gaps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,
    data_type TEXT,
    gap_start TIMESTAMP,
    gap_end TIMESTAMP,
    status TEXT DEFAULT 'OPEN',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- 股票基本信息
CREATE TABLE master_stocks (
    stock_code TEXT PRIMARY KEY,
    stock_name TEXT NOT NULL,
    market TEXT,               -- 上海/深圳/北京
    sector TEXT,              -- 所属行业
    industry TEXT,           -- 细分行业
    list_date TEXT,           -- 上市日期
    total_shares REAL,        -- 总股本(亿股)
    float_shares REAL,        -- 流通股本(亿股)
    company_name TEXT,        -- 公司全称
    business_scope TEXT,      -- 经营范围
    updated_at TEXT,
    data_source TEXT
);

-- 板块映射
CREATE TABLE stock_sector_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,
    sector_name TEXT,
    sector_type TEXT,         -- industry/concept/region
    is_primary INTEGER,        -- 1=主要板块
    updated_at TEXT
);

-- 板块信息
CREATE TABLE master_sectors (
    sector_code TEXT PRIMARY KEY,
    sector_name TEXT NOT NULL,
    parent_sector TEXT,
    description TEXT,
    hot_stocks TEXT,          -- JSON格式存储热门股票
    updated_at TEXT
);
```

### 4.2 信号数据库: signals_v3.db

**路径**: `~/Documents/OpenClawAgents/hongzhong/data/signals_v3.db`

```sql
-- 交易信号表
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    signal_type TEXT,         -- BUY/SELL
    strategy TEXT,           -- 策略名称
    score REAL,              -- 策略评分
    price REAL,              -- 当前价格
    target_price REAL,       -- 目标价
    stop_loss REAL,          -- 止损价
    reason TEXT,             -- 信号原因
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'PENDING'  -- PENDING/EXECUTED/EXPIRED
);
```

### 4.3 组合数据库: portfolio.db

**路径**: `~/Documents/OpenClawAgents/facai/data/portfolio.db`

```sql
-- 持仓表
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT NOT NULL,
    stock_name TEXT,
    quantity INTEGER,
    avg_cost REAL,
    current_price REAL,
    pnl REAL,
    open_date TEXT,
    status TEXT DEFAULT 'OPEN'
);

-- 交易记录
CREATE TABLE trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code TEXT,
    trade_type TEXT,          -- BUY/SELL
    quantity INTEGER,
    price REAL,
    trade_date TEXT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 板块数据库: xifeng.db

**路径**: `~/Documents/OpenClawAgents/xifeng/data/xifeng.db`

```sql
-- 板块热度
CREATE TABLE sector_heat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sector_name TEXT,
    heat_score REAL,
    up_count INTEGER,        -- 上涨股票数
    down_count INTEGER,       -- 下跌股票数
    total_stocks INTEGER,
    avg_change REAL,         -- 平均涨幅
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 板块成分股
CREATE TABLE sector_stocks (
    sector_name TEXT,
    stock_code TEXT,
    weight REAL,             -- 权重
    PRIMARY KEY (sector_name, stock_code)
);
```

---

## 五、工作流设计

### 5.1 日间交易流程 (09:30-15:00)

```
时间          Agent          操作
────────────────────────────────────────────
09:15         判官           系统自检 + 数据校验
09:30         北风           全量日线数据采集 (5,348只)
09:32         西风           板块热点分析
09:35         南风           全量策略评分 (Top 100)
09:40         红中           生成交易信号 + 发送通知
09:45         东风           候选池更新
────────────────────────────────────────────
每5分钟       北风           实时行情快照
每30分钟      西风           板块热点刷新
每35分钟      南风           策略评分刷新
每40分钟      红中           信号刷新
────────────────────────────────────────────
14:55         发财           收盘前检查
15:00         判官           日终数据校验
15:05         白板           策略复盘
```

### 5.2 数据流向

```
AKShare/Sina/Tencent
        │
        ▼
   ┌─────────┐
   │  北风   │ ──抓取──▶ kline_data表
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  判官   │ ──校验──▶ data_gaps表
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  西风   │ ──分析──▶ sector_heat表
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  东风   │ ──筛选──▶ candidate_pool
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  南风   │ ──评分──▶ signals表 (Top 100)
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  红中   │ ──通知──▶ Email/Telegram
   └─────────┘
        │
        ▼
   ┌─────────┐
   │  发财   │ ──执行──▶ portfolio.db
   └─────────┘
```

### 5.3 关键工作流实现

#### 5.3.1 北风数据采集工作流

```python
# beifeng/beifeng.py
def run():
    # 1. 自检 - 检查数据源健康状态
    health = check_sources()
    
    # 2. 测速 - 测试数据源响应时间
    latency = test_latency()
    
    # 3. 抓取 - 根据优先级采集
    if is_trading_time():
        fetch_realtime()    # 实时行情
        fetch_minute()     # 分钟数据 (核心100只)
    
    # 4. 日线采集 (每日一次)
    if should_fetch_daily():
        fetch_all_daily()   # 全量5,348只
    
    # 5. 校验 - 写入数据库 + 校验完整性
    validate_and_save()
```

#### 5.3.2 红中信号生成工作流

```python
# hongzhong/generate_signals_multi.py
def generate_signals():
    # 1. 获取候选股票 (Top 100 from 南风)
    candidates = get_top_candidates(100)
    
    # 2. 多策略评分
    for stock in candidates:
        score = calculate_strategy_score(stock)
        
        # 3. 信号判断
        if score > threshold:
            signal = create_signal(stock, score)
            
            # 4. 计算目标价/止损价
            signal.target_price = stock.close * 1.05
            signal.stop_loss = stock.close * 0.95
            
            # 5. 写入数据库
            save_signal(signal)
    
    # 6. 发送通知
    send_notifications(signals)
```

---

## 六、关键模块设计

### 6.1 连接池 (db_pool.py)

```python
# 特性: WAL模式 + 重试机制 + 进程锁
class DBPool:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA busy_timeout=30000")
```

### 6.2 统一日志 (agent_logger.py)

```python
# 特性: 统一格式 + 文件轮转 + 多handler
logger = get_logger("北风")
logger.info("采集完成", extra={"stock_count": 5348, "duration": "45s"})
```

### 6.3 统一通知 (unified_notifier.py)

```python
# 特性: 多通道 (Email/Telegram/Discord)
notify.send(
    channel="email",
    title="交易信号",
    content=signal_text
)
```

### 6.4 进程锁 (process_lock.py)

```python
# 特性: 防止Cron任务冲突
with ProcessLock("beifeng"):
    run_beifeng()
```

### 6.5 Cron包装器 (cron_wrapper.py)

```python
# 特性: 错误捕获 + 超时控制 + 重试
@cron_wrapper(timeout=300, retry=3)
def run():
    pass
```

---

## 七、技术规范

### 7.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件 | 小写+下划线 | beifeng.py, generate_signals_multi.py |
| 类 | 大驼峰 | Database, DataFetcher |
| 函数 | 小写+下划线 | fetch_data(), validate_db() |
| 常量 | 大写+下划线 | MAX_RETRIES, DEFAULT_TIMEOUT |

### 7.2 日志规范

```
# 格式
2026-03-26 09:35:12 - 北风 - INFO - 采集完成: 5348只, 耗时45.2s

# 级别
DEBUG: 详细调试信息
INFO: 正常运行信息
WARNING: 警告信息
ERROR: 错误信息
CRITICAL: 严重错误
```

### 7.3 错误处理

```python
# 1. 重试机制
for attempt in range(MAX_RETRIES):
    try:
        fetch()
        break
    except Exception as e:
        if attempt == MAX_RETRIES - 1:
            raise
        time.sleep(RETRY_DELAY)

# 2. 错误日志
logger.error(f"采集失败: {stock_code}", exc_info=True)

# 3. 告警通知
if is_critical_error(e):
    notify.alert(f"严重错误: {e}")
```

---

## 八、部署与运维

### 8.1 目录结构

```
~/Documents/OpenClawAgents/
├── beifeng/          # 北风 - 数据采集
│   ├── data/        # 数据库文件
│   ├── logs/        # 日志文件
│   └── beifeng.py   # 主程序
├── xifeng/          # 西风 - 板块分析
├── dongfeng/        # 东风 - 候选池
├── nanfeng/         # 南风 - 策略评分
├── hongzhong/       # 红中 - 信号通知
├── facai/           # 发财 - 模拟交易
├── baiban/          # 白板 - 策略优化
├── judge/           # 判官 - 数据验证
├── caishen/         # 财神爷 - 监控
├── utils/           # 公共工具
│   ├── db_pool.py
│   ├── agent_logger.py
│   ├── unified_notifier.py
│   └── process_lock.py
└── logs/            # 全局日志
```

### 8.2 备份策略

```bash
# 核心文件每日备份
bash backup_core.sh v4.3.0

# 备份位置
~/Documents/OpenClawAgents/backups/{version}_{date}_{time}/
```

### 8.3 监控告警

| 指标 | 阈值 | 动作 |
|------|------|------|
| 分钟数据 < 5000条 | 告警 | 触发更新 |
| Cron error | 告警 | 自动修复 |
| 账户异常 | 告警 | 通知用户 |

---

## 九、待优化项

### 9.1 短期优化 (v4.4.0)
- [ ] 分钟数据覆盖从100只扩展到500只
- [ ] 增加北向资金数据
- [ ] 龙虎榜数据集成
- [ ] 涨停板监控强化

### 9.2 中期优化 (v5.0.0)
- [ ] 引入机器学习策略
- [ ] 回测系统完善
- [ ] 实盘交易接口
- [ ] 多账户管理

### 9.3 长期优化 (v6.0.0)
- [ ] 量化因子库
- [ ] 组合优化器
- [ ] 风险管理模块
- [ ] 绩效归因分析

---

## 十、附录

### 10.1 命令清单

```bash
# 测试所有Agent
bash test_all_agents.sh

# 手动运行各Agent
python3 beifeng/beifeng.py
python3 xifeng/xifeng_v2_sector.py
python3 nanfeng/nanfeng_v5_1.py
python3 hongzhong/generate_signals_multi.py
python3 facai/facai.py

# 查看Cron状态
crontab -l

# 查看日志
tail -f logs/beifeng.log
tail -f logs/nanfeng.log
```

### 10.2 数据源API

| 数据源 | API | 状态 |
|--------|-----|------|
| AKShare | akshare.stock_zh_a_hist | ✅ 正常 |
| 新浪 | hq.sinajs.cn | ✅ 正常 |
| 腾讯 | qt.gtimg.cn | ✅ 正常 |
| Baostock | bs.pro | ✅ 正常 |

### 10.3 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v4.3.0 | 2026-03-18 | 9-Agent协同 + 进程锁 |
| v4.2.0 | 2026-03-16 | 主数据库+多Agent |
| v4.1.0 | 2026-03-14 | Cron优化 |
| v4.0.0 | 2026-03-12 | 初始版本 |

---

*文档生成时间: 2026-03-26*
*维护者: Roberto*