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
