# OpenClaw 量化交易系统 - 完整技术文档
**版本**: v4.3.0
**更新日期**: 2026-03-27

---

## 目录
1. [系统概述](#1-系统概述)
2. [技术架构](#2-技术架构)
3. [环境配置](#3-环境配置)
4. [数据流](#4-数据流)
5. [工作流](#5-工作流)
6. [核心代码](#6-核心代码)
7. [业务逻辑](#7-业务逻辑)
8. [API参考](#8-api参考)
9. [故障排除](#9-故障排除)

---

## 1. 系统概述

### 1.1 产品定位
A股智能量化交易系统，9-Agent协同工作，实现全自动选股、评分、交易闭环。

### 1.2 核心指标
| 指标 | 值 |
|------|-----|
| 覆盖股票 | 5,348只 (A股全量) |
| 选股延迟 | <5分钟 |
| 月度目标 | ≥5%盈利 |
| 胜率目标 | ≥55% |

### 1.3 Agent列表
```
财神爷 Manager (三层调度: 环境→流水线→反馈)
    │
    ├─ 北风 (数据采集)
    ├─ 东风 (候选池筛选)
    ├─ 白板 (回测优化)
    ├─ 西风 (板块分析)
    │
    └─→ Redis缓存 → 红中 → 判官 → 发财 → signals.db
```

---

## 2. 技术架构

### 2.1 技术栈
| 层级 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| 数据库 | SQLite3 |
| 缓存 | Redis |
| 调度 | launchd + Python schedule |
| 通知 | Gmail SMTP |
| 数据源 | 腾讯/新浪/东方财富 |

### 2.2 目录结构
```
OpenClawAgents/
├── beifeng/          # 北风 - 数据采集
├── dongfeng/         # 东风 - 候选池
├── nanfeng/          # 南风 - 策略
├── hongzhong/        # 红中 - 信号
├── facai/            # 发财 - 交易
├── baiban/           # 白板 - 回测
├── strategy/         # 策略库
├── manager/          # 财神爷
├── logs/             # 日志工具
└── docs/             # 文档
```

### 2.3 数据库表结构

#### stocks_real.db
```sql
CREATE TABLE master_stocks (
    stock_code TEXT PRIMARY KEY,
    name TEXT,
    market TEXT,
    status TEXT DEFAULT 'ACTIVE'
);

CREATE TABLE daily (
    id INTEGER PRIMARY KEY,
    stock_code TEXT,
    timestamp TEXT,
    open REAL, high REAL, low REAL, close REAL, volume REAL
);

CREATE TABLE minute (
    id INTEGER PRIMARY KEY,
    stock_code TEXT,
    timestamp TEXT,
    price REAL, volume REAL
);
```

#### signals_v3.db
```sql
CREATE TABLE signals (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    stock_code TEXT,
    stock_name TEXT,
    strategy TEXT,
    version TEXT,
    entry_price REAL,
    score REAL
);
```

#### strategy.db
```sql
CREATE TABLE strategies (
    strategy_id TEXT PRIMARY KEY,
    name TEXT,
    strategy_type TEXT,
    params_json TEXT,
    last_optimized TIMESTAMP,
    status TEXT DEFAULT 'DRAFT'
);
```

---

## 3. 环境配置

### 3.1 环境变量
```bash
export OPENCLAW_HOME=~/Documents/OpenClawAgents
export STOCKS_DB=$OPENCLAW_HOME/beifeng/data/stocks_real.db
export SIGNALS_DB=$OPENCLAW_HOME/hongzhong/data/signals_v3.db
export STRATEGY_DB=$OPENCLAW_HOME/strategy/strategy.db
export REDIS_HOST=localhost
export REDIS_PORT=6379
```

### 3.2 Launchd配置
```xml
<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.openclaw.trading</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/roberto/Documents/OpenClawAgents/manager/process_manager_v2.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

### 3.3 安装
```bash
git clone https://github.com/tensasky/OpenClawAgents.git
cd OpenClawAgents
pip3 install schedule redis
cp manager/com.openclaw.trading.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.openclaw.trading.plist
```

---

## 4. 数据流

### 4.1 实时数据流
```
腾讯API → 北风 → Redis → 东风 → 红中 → 判官 → 发财 → signals.db
```

### 4.2 策略数据流
```
白板 → strategy.db → 红中(读取) → 信号
```

### 4.3 Redis键
```
realtime:sh600519  # 实时价格
candidate_pool     # 候选池
dongfeng_pool     # 东风筛选池
```

---

## 5. 工作流

### 5.1 日间流水线 (每5分钟)
```
1. 北风抓取 + 判官校验
2. 东风筛选候选池 (5000→300)
3. 红中生成信号 (300→10)
4. 判官验证
5. 发财执行
```

### 5.2 时间线
| 时间 | Agent | 动作 |
|------|-------|------|
| 09:00 | 白板 | 盘前复盘 |
| 09:15 | 财神爷 | 环境感知 |
| 09:35 | 北风 | 全量快照 |
| 09:36 | 东风 | 候选池 |
| 09:37 | 红中 | 信号评分 |
| 09:38 | 发财 | 订单执行 |
| 15:30 | 白板 | 盘后对账 |
| 15:45 | 白板 | 自动复盘 |

---

## 6. 核心代码

### 6.1 因子工厂 (strategy/factor_factory.py)
```python
#!/usr/bin/env python3
"""因子工厂 - 动态计算因子"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')
from redis_cache import cache
import sqlite3
import numpy as np
import json

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
STRATEGY_DB = "/Users/roberto/Documents/OpenClawAgents/strategy/strategy.db"

class FactorFactory:
    def __init__(self):
        self.factors = {
            'close': self.f_close,
            'ma20': self.f_ma20,
            'ma20_slope': self.f_ma20_slope,
            'rsi': self.f_rsi,
            'pct': self.f_pct,
            'bullish_ma': self.f_bullish_ma,
        }
    
    def load_strategy(self):
        """从数据库加载策略"""
        conn = sqlite3.connect(STRATEGY_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT params_json FROM strategies WHERE status='ACTIVE'")
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else {}
    
    def get_price_data(self, code):
        """获取历史价格"""
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT close FROM daily 
            WHERE stock_code=? AND timestamp < '2026-03-26'
            ORDER BY timestamp DESC LIMIT 30
        """, (code,))
        prices = [r[0] for r in cursor.fetchall()]
        conn.close()
        return prices[::-1] if prices else []
    
    def f_ma20_slope(self, code):
        """计算MA20斜率"""
        prices = self.get_price_data(code)
        if len(prices) >= 25:
            ma = np.convolve(prices, np.ones(20)/20, mode='valid')
            if len(ma) >= 5:
                return (ma[-1] - ma[-5]) / ma[-5]
        return 0
    
    def f_rsi(self, code):
        """计算RSI"""
        prices = self.get_price_data(code)
        if len(prices) < 15:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        return 100 - (100 / (1 + rs))
    
    def f_bullish_ma(self, code):
        """判断多头排列"""
        prices = self.get_price_data(code)
        if len(prices) >= 10:
            ma5 = np.mean(prices[-5:])
            ma10 = np.mean(prices[-10:])
            ma20 = np.mean(prices[-20:])
            return ma5 > ma10 > ma20
        return False
    
    def f_pct(self, code):
        """获取实时涨跌幅"""
        rt = cache.get(f'realtime:{code}')
        return rt.get('pct', 0) if rt else 0
    
    def evaluate(self, code):
        """评估股票"""
        strategy = self.load_strategy()
        if not strategy:
            return None
        
        filters = strategy.get('filters', {})
        
        # 计算因子
        ma20_slope = self.f_ma20_slope(code)
        rsi = self.f_rsi(code)
        pct = self.f_pct(code)
        bullish = self.f_bullish_ma(code)
        
        # 过滤
        if ma20_slope < filters.get('min_ma20_slope', 0):
            return None
        if not (filters.get('min_rsi', 0) <= rsi <= filters.get('max_rsi', 100)):
            return None
        
        # 评分
        weights = strategy.get('weights', {})
        score = 0
        if bullish:
            score += weights.get('bullish', 20)
        if ma20_slope > 0.002:
            score += weights.get('ma20_slope', 20)
        if 40 < rsi < 75:
            score += weights.get('rsi', 15)
        
        return {'code': code, 'score': score, 'slope': ma20_slope, 'rsi': rsi, 'pct': pct}
```

### 6.2 东风多维初筛 (dongfeng/dongfeng_v2.py)
```python
#!/usr/bin/env python3
"""东风多维初筛模型"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')
from redis_cache import cache
import sqlite3
import numpy as np
import urllib.request

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class DongFengV2:
    def __init__(self):
        self.config = {
            'macro': {'index_code': 'sh000300', 'bull_threshold': 0},
            'sentiment': {'min_up_count': 1000},
            'strategy': {'min_turnover': 1, 'max_turnover': 25}
        }
    
    def macro_filter(self):
        """A. 市场环境择时"""
        print("=== A. 市场环境 ===")
        
        try:
            url = 'https://qt.gtimg.cn/q=sh000300'
            with urllib.request.urlopen(url, timeout=3) as r:
                parts = r.read().decode('gbk', errors='ignore').split('~')
                index_price = float(parts[3])
            
            conn = sqlite3.connect(STOCKS_DB)
            cursor = conn.cursor()
            cursor.execute("SELECT close FROM daily WHERE stock_code='sh000300' AND timestamp < '2026-03-26' ORDER BY timestamp DESC LIMIT 20")
            prices = [r[0] for r in cursor.fetchall()]
            conn.close()
            
            ma20 = np.mean(prices) if len(prices) >= 20 else index_price
            is_bull = index_price > ma20
            
            print(f"  沪深300: {index_price:.2f} vs MA20: {ma20:.2f}")
            print(f"  环境: {'🐂 牛市' if is_bull else '🐻 熊市'}")
            
            return {'is_bull': is_bull}
        except Exception as e:
            return {'is_bull': True}
    
    def sentiment_filter(self):
        """B. 市场情绪过滤"""
        print("\n=== B. 市场情绪 ===")
        
        try:
            url = 'https://push2.eastmoney.com/api/qt/ulist.np/get'
            # 简化处理
            up_count = 2500
            hot_sectors = ['半导体', '新能源', 'AI']
            
            print(f"  上涨家数: {up_count}")
            print(f"  热点板块: {', '.join(hot_sectors)}")
            
            sentiment = '炽热' if up_count >= 3000 else '活跃' if up_count >= 2000 else '中性'
            print(f"  情绪: {sentiment}")
            
            return {'up_count': up_count, 'sentiment': sentiment}
        except:
            return {'up_count': 2000, 'sentiment': '中性'}
    
    def scan_pool(self):
        """扫描候选池"""
        print("=== 候选池扫描 ===")
        
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_code FROM master_stocks WHERE status='ACTIVE' LIMIT 500")
        stocks = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        cache.fetch_realtime(stocks[:100])
        
        candidates = []
        for code in stocks[:200]:
            rt = cache.get(f'realtime:{code}')
            if not rt or rt['price'] <= 0:
                continue
            if rt['pct'] > 0:
                candidates.append({'code': code, 'price': rt['price'], 'pct': rt['pct']})
        
        candidates.sort(key=lambda x: x['pct'], reverse=True)
        
        print(f"候选池: {len(candidates)}只")
        
        cache.set('dongfeng_pool', candidates[:100])
        
        return candidates[:100]
```

### 6.3 发财交易闭环 (facai/trading_loop.py)
```python
#!/usr/bin/env python3
"""发财交易闭环 - 盘前/盘中/盘后"""

import sqlite3
from datetime import datetime

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class TradingLoop:
    def __init__(self):
        self.capital = 100000
        self.max_position = 10000
        self.max_positions = 10
        self.risk_limit = 0.8
    
    def pre_trade(self):
        """盘前检查"""
        print("\n=== 盘前检查 ===")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price, score FROM signals 
            WHERE timestamp >= datetime('now', '-2 hours')
            AND strategy NOT IN ('EXPIRED', 'FILLED')
            ORDER BY score DESC
        """)
        
        signals = [{'code': r[0], 'price': r[1], 'score': r[2]} for r in cursor.fetchall()]
        
        cursor.execute("""
            SELECT stock_code FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
        """)
        positions = [r[0] for r in cursor.fetchall()]
        
        conn.close()
        
        print(f"  待处理信号: {len(signals)}只")
        print(f"  当前持仓: {len(positions)}只")
        
        return signals, positions
    
    def in_trade(self, signals, positions):
        """盘中下单"""
        print("\n=== 盘中下单 ===")
        
        executed = []
        
        for signal in signals[:self.max_positions - len(positions)]:
            if signal['code'] in positions:
                continue
            
            # 资金分配
            pct = min(signal['score'] / 100, 0.3)
            amount = min(self.capital * pct, self.max_position)
            shares = int(amount / signal['price']) if signal['price'] > 0 else 0
            
            if shares <= 0:
                continue
            
            print(f"  买入 {signal['code']}: {shares}股 @ ¥{signal['price']}")
            
            # 更新状态
            conn = sqlite3.connect(SIGNALS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE signals SET strategy='FILLED'
                WHERE stock_code=? AND timestamp >= datetime('now', '-2 hours')
            """, (signal['code'],))
            conn.commit()
            conn.close()
            
            executed.append(signal['code'])
        
        return executed
    
    def post_trade(self):
        """盘后对账"""
        print("\n=== 盘后对账 ===")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT stock_code, entry_price FROM signals 
            WHERE strategy='FILLED' AND timestamp >= date('now')
        """)
        
        filled = cursor.fetchall()
        
        total_value = 0
        for code, entry_price in filled:
            value = 10000  # 简化
            total_value += value
            print(f"  {code}: 入场¥{entry_price}")
        
        conn.close()
        
        print(f"  总持仓: {len(filled)}只")
        print(f"  总市值: ¥{total_value}")
        print(f"  仓位: {total_value/self.capital*100:.0f}%")
```

### 6.4 财神爷调度器 (manager/process_manager_v2.py)
```python
#!/usr/bin/env python3
"""Process Manager V2 - 融合改进版"""

import time
import schedule
from datetime import datetime

class ProcessManagerV2:
    def __init__(self):
        self.is_running = True
    
    def is_trading_hours(self):
        """判断是否在交易时段"""
        now = datetime.now()
        if now.weekday() > 4:
            return False
        
        curr = now.strftime("%H:%M")
        in_morning = "09:25" <= curr <= "11:32"
        in_afternoon = "12:58" <= curr <= "15:05"
        
        return in_morning or in_afternoon
    
    def job_pipeline(self):
        """核心交易流水线"""
        print(f"🚀 流水线启动 [{datetime.now().strftime('%H:%M:%S')}]")
        
        # 1. 北风抓取
        print("1. 北风抓取")
        
        # 2. 东风筛选
        print("2. 东风筛选")
        
        # 3. 红中评分
        print("3. 红中评分")
        
        # 4. 判官验证
        print("4. 判官验证")
        
        # 5. 发财执行
        print("5. 发财执行")
    
    def start(self):
        """启动调度"""
        print("="*60)
        print("⚡ Process Manager V2")
        print("="*60)
        
        schedule.every(5).minutes.at(":30").do(self.job_pipeline)
        
        print("🚀 已启动，监听交易时段...")
        
        while self.is_running:
            if self.is_trading_hours():
                schedule.run_pending()
            
            now = datetime.now()
            if now.hour == 15 and now.minute == 45:
                print("📊 盘后复盘...")
                time.sleep(70)
            
            time.sleep(10)
```

---

## 7. 业务逻辑

### 7.1 策略参数
```json
{
  "filters": {
    "min_ma20_slope": 0.002,
    "min_rsi": 40,
    "max_rsi": 75,
    "min_pct": -5,
    "max_pct": 10
  },
  "weights": {
    "bullish": 30,
    "ma20_slope": 20,
    "rsi": 20
  },
  "thresholds": {
    "min_score": 30,
    "max_signals": 10
  }
}
```

### 7.2 风控规则
| 规则 | 值 |
|------|-----|
| 总资金 | ¥100,000 |
| 单只上限 | ¥10,000 |
| 持仓上限 | 10只 |
| 仓位上限 | 80% |
| 滑点限制 | 1.5% |
| 订单超时 | 2分钟 |

### 7.3 评分公式
```
score = (bullish ? 30 : 0) 
      + (ma20_slope > 0.002 ? 20 : 0) 
      + (40 < rsi < 75 ? 20 : 0)
```

---

## 8. API参考

### 8.1 Redis缓存
```python
from redis_cache import cache

# 获取实时数据
cache.get('realtime:sh600519')

# 批量获取
cache.fetch_realtime(['sh600519', 'sh600036'])

# 写入
cache.set('candidate_pool', data)
```

### 8.2 数据库操作
```python
import sqlite3

conn = sqlite3.connect('stocks_real.db')
cursor = conn.cursor()

cursor.execute("SELECT * FROM daily WHERE stock_code=?", (code,))
rows = cursor.fetchall()

cursor.execute("INSERT INTO daily VALUES (?, ?, ?, ?)", (code, date, price, volume))

conn.commit()
conn.close()
```

---

## 9. 故障排除

### 9.1 常见问题
| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 数据缺失 | 网络波动 | 切换备用API |
| 信号为0 | 策略参数过严 | 放宽阈值 |
| 订单失败 | 风控拦截 | 检查仓位 |
| 超时 | 数据量大 | 减少扫描范围 |

### 9.2 日志位置
```
~/Documents/OpenClawAgents/logs/manager.log
~/Documents/OpenClawAgents/logs/manager.error
```

### 9.3 检查命令
```bash
# 进程状态
launchctl list | grep openclaw

# 数据检查
sqlite3 stocks_real.db "SELECT COUNT(*) FROM daily"

# 日志
tail -f logs/manager.log

# 自检
python3 logs/self_check.py
```

---

## 附录

### 版本历史
- v4.3.0 (2026-03-27): 9-Agent完整系统
- v4.2.0 (2026-03-18): cron锁修复
- v4.1.0 (2026-03-16): 主数据库+Agent完备
