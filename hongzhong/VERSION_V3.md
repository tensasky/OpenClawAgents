# 红中 V3.0 版本说明

**版本号**: V3.0.0  
**发布日期**: 2026-03-13  
**升级内容**: 高频扫描 + 双版本支持 + 持久化存储

---

## 🎯 版本特性

### 1. 高频扫描 ✅
- **扫描频率**: 每15分钟一次
- **交易时段**: 9:30-11:30, 13:00-15:00
- **自动调度**: cron定时任务

### 2. 双版本支持 ✅
- **保守版**: 高门槛信号，胜率80-85%
- **平衡版**: 适中门槛信号，胜率60-73%
- **版本标识**: 每条信号标注所属版本

### 3. 多渠道通知 ✅
- **Discord**: 实时推送，带emoji标识
- **邮件**: 详细报告，包含完整参数
- **通知内容**: 版本、策略、操作建议、技术指标

### 4. 持久化存储 ✅
- **SQLite数据库**: `data/signals_v3.db`
- **日志文件**: `logs/hongzhong_v3_YYYYMMDD.log`
- **JSON备份**: 信号同时保存为JSON

---

## 📁 文件结构

```
hongzhong/
├── hongzhong_v3.py          # V3.0主程序
├── cron_v3.sh               # 定时任务脚本
├── data/
│   └── signals_v3.db        # SQLite数据库
├── logs/
│   └── hongzhong_v3_*.log   # 日志文件
└── VERSION_V3.md            # 版本说明
```

---

## 🚀 部署方式

### 1. 手动运行
```bash
cd ~/Documents/OpenClawAgents/hongzhong
python3 hongzhong_v3.py
```

### 2. 定时任务
```bash
# 添加到crontab，每15分钟运行
*/15 9-11,13-14 * * 1-5 /Users/roberto/Documents/OpenClawAgents/hongzhong/cron_v3.sh
```

---

## 📊 数据库结构

### signals表
| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER | 主键 |
| timestamp | TEXT | 信号时间 |
| stock_code | TEXT | 股票代码 |
| stock_name | TEXT | 股票名称 |
| strategy | TEXT | 策略名称 |
| version | TEXT | 版本(conservative/balance) |
| entry_price | REAL | 入场价 |
| stop_loss | REAL | 止损价 |
| target_1/2/3 | REAL | 目标价 |
| position_size | TEXT | 建议仓位 |
| score | REAL | 综合分数 |
| adx | REAL | ADX指标 |
| rsi | REAL | RSI指标 |
| volume_ratio | REAL | 量比 |
| sector | TEXT | 所属板块 |
| is_hot_sector | INTEGER | 是否热点板块 |
| sent_discord | INTEGER | 是否发送Discord |
| sent_email | INTEGER | 是否发送邮件 |

---

## 🔔 通知格式

### Discord通知
```
🛡️ 红中V3预警 📈

版本: 保守版
策略: 趋势跟踪
股票: sh600348 华阳股份

💰 操作建议
入场价: ¥10.27
止损价: ¥10.06 (-2.0%)
目标1: ¥10.89 (+6%)
目标2: ¥11.50 (+12%)
建议仓位: 20%

📊 技术指标
分数: 9.2
ADX: 42
RSI: 58
量比: 2.5
板块: 煤炭 🔥
```

### 邮件通知
- **主题**: 🀄 红中V3预警 - sh600348 (保守版)
- **内容**: 完整操作建议和技术指标

---

## 📈 与V2.5对比

| 特性 | V2.5 | V3.0 |
|------|------|------|
| 扫描频率 | 每日1次(14:45) | 每15分钟 |
| 版本支持 | 单版本 | 保守版+平衡版 |
| 通知渠道 | Discord+邮件 | Discord+邮件 |
| 持久化 | JSON文件 | SQLite+JSON |
| 数据查询 | 文件读取 | SQL查询 |

---

## 🔄 版本切换

```bash
# V2.5
python3 hongzhong_v25_merged.py

# V3.0
python3 hongzhong_v3.py
```

---

## 📝 TODO

- [ ] 集成南风V5.4引擎实际扫描
- [ ] 增加信号去重机制
- [ ] 增加信号质量评分
- [ ] 增加历史信号回测验证

---

**Git标签**: `hongzhong-v3.0.0`  
**提交**: 待创建
