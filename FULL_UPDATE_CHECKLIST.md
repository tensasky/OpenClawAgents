# 全量更新检查清单 - 2026-03-17

## 已完成的修复

### 1. 数据库修复
- [x] 修复daily表换行符问题 (5,240条记录)
- [x] 修复stock_names表换行符问题 (5,235条记录)
- [x] 删除重复记录 (14条)

### 2. 代码修复
- [x] nanfeng_v5_1.py - 移除data_type查询条件
- [x] backtest_v5_1.py - kline_data -> daily
- [x] batch_backtest.py - kline_data -> daily
- [x] nanfeng.py - kline_data -> daily
- [x] param_optimize.py - kline_data -> daily
- [x] quick_backtest.py - kline_data -> daily
- [x] realtime_aggregator.py - kline_data -> daily
- [x] strategy_backtest.py - kline_data -> daily
- [x] beifeng/batch_fill_all.py - kline_data -> daily
- [x] beifeng/emergency_fix.py - kline_data -> daily
- [x] beifeng/fill_history.py - kline_data -> daily
- [x] beifeng/status.py - kline_data -> daily

### 3. 判官Agent升级
- [x] 添加validate_data_freshness() - 数据时效性检查
- [x] 添加validate_before_send() - 发送前验证
- [x] 集成到报告生成流程

## 待修复问题

### 日志统一 (高优先级)
以下文件仍使用独立logging配置，应改为使用agent_logger：
- [ ] nanfeng/backtest_v5_1.py
- [ ] nanfeng/batch_backtest.py
- [ ] nanfeng/nanfeng.py
- [ ] nanfeng/nanfeng_production.py
- [ ] nanfeng/param_optimize.py
- [ ] nanfeng/realtime_aggregator.py
- [ ] nanfeng/strategy_backtest.py
- [ ] beifeng/beifeng.py
- [ ] beifeng/beifeng_pg.py
- [ ] beifeng/fetcher.py
- [ ] beifeng/fill_history.py
- [ ] beifeng/resilient_fetcher.py

### 版本标签
- [ ] 创建标签: v4.1.0-production
- [ ] 更新VERSION.md
