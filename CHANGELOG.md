# 更新日志

## v4.6.1 (2026-03-18) - 数据库追踪版

### 数据库优化
- trades表增加: signal_id, strategy, score
- positions表增加: signal_id, strategy, score
- 支持交易复盘追溯

### 文档更新
- BRD.md - 商业需求文档
- PRD.md - 产品需求文档
- SDD.md - 详细设计文档
- CODE_LOGIC.md - 代码逻辑解释

---

# 更新日志

## v4.6.0 (2026-03-18) - 风控增强版

### ATR动态止损
- ATR (Average True Range) 计算
- 动态止损: StopLoss = HighestPrice - (k * ATR)
- k=2, 自动适应波动率

### 组合风控
- 行业30%仓位限制
- 每日交易限额 (5笔/日)
- 策略独立资金池 (每策略10万)

### 风控模块
- utils/risk_control.py
- check_buy_risk() 综合风险检查

---

# 更新日志

## v4.5.0 (2026-03-18) - 流控增强版

### 流控方案
- RateLimiter: 滑动窗口限流
- CircuitBreaker: 断路器模式
- FlowController: 统一流控管理

### 限流配置
- 信号发布: 20次/秒
- 信号处理: 100次/分
- 断路器阈值: 连续5次失败

### 故障恢复
- 自动半开探测
- 60秒恢复超时
- 2次成功自动闭合

---

# 更新日志

## v4.4.0 (2026-03-18) - 架构增强版

### P0 哨兵机制
- utils/sentinel.py
- 心跳监测: 北风分钟/日线数据更新监控
- 数据对账: 持仓与账户余额实时校验
- 告警: 异常状态Discord通知

### P1 事件驱动
- utils/event_bus.py
- Redis Pub/Sub信号推送
- 数据库轮询降级模式
- 信号实时处理

---

# 更新日志

## v4.3.1 (2026-03-18)

### 新增功能
- 联动选股系统 linked_workflow.py
  - 西风→东风→南风→红中→发财完整工作流
  - 从hot_spots.json读取热点板块
  - 从数据库获取股票名称
- 股票信息模块 utils/stock_info.py
  - 统一API获取实时价格、市值、板块
- 设计文档
  - docs/PRD.md 产品需求文档
  - docs/SDD.md 详细设计文档

### 系统配置
- OpenClaw Cron定时任务
  - 东风: 每小时 (0 9,10,11,13,14 * * 1-5)
  - 西风: 每30分钟 (30 9,10,11,13,14 * * 1-5)
  - 联动选股: (30 9,10,11,13,14 * * 1-5)
- exec审批full模式

---

# 更新日志

## v4.3.0 (2026-03-18)

### 版本更新
- 南风: V5.1 → V5.5 (多策略支持)
- 红中: V3.0 → V3.4 (表格通知格式)

### 新增功能
- 通知系统统一模板 (utils/notify.py)
- 表格通知格式
- 多策略配置 (8种策略)

---

## v4.2.0 (2026-03-18)

### 🎯 新增功能

#### 发财自动交易系统
- 连接红中信号数据库，实时读取信号
- 根据信号自动买入（评分≥65分）
- 移动止损止盈策略

#### 通知系统
- 统一通知模板 (utils/notify.py)
- Discord webhook集成
- Email SMTP集成

#### 价格优化
- 实时价格获取（优先minute表）
- 涨停股过滤（≥9.9%禁止买入）
- 滑点计算（买入0.2%上浮，卖出0.2%下浮）

### 🔧 Bug修复

#### beifeng.py
- 添加minute类型支持
- 修复时间格式保存

#### 红中信号
- 非交易时段使用最近交易日数据
- 信号保存到数据库功能

#### Cron冲突
- 全部6个脚本添加进程锁
- 后台运行+自动聚合

#### 判官
- 自动聚合minute→daily
- 数据质量校验

### 📁 文件变更

**新增:**
- utils/notify.py - 统一通知
- utils/process_lock.py - 进程锁
- utils/cron_wrapper.py - 锁包装器
- judge/data_validator.py - 数据校验
- cron_monitor.py - 监控

**修改:**
- beifeng/beifeng.py
- hongzhong/generate_signals_v3.py
- facai/facai.py
- cron_*.sh (6个)

---

## v4.1.0 (2026-03-17)

- 数据库清理
- SQL查询修复
- 判官升级

---

## v4.0.0 (2026-03-16)

- 9-Agent全系统
- 全A股5,356只
- 主数据库系统
