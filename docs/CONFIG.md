# 配置手册

## 1. 环境要求

- macOS
- Python 3.9+
- Redis
- SQLite3

## 2. 安装步骤

```bash
# 1. 复制launchd配置
cp manager/com.openclaw.trading.plist ~/Library/LaunchAgents/

# 2. 加载
launchctl load ~/Library/LaunchAgents/com.openclaw.trading.plist

# 3. 启动
launchctl start com.openclaw.trading
```

## 3. 手动启动

```bash
python3 manager/process_manager_v2.py
```

## 4. 监控

```bash
# 查看日志
tail -f logs/manager.log

# 查看进程
launchctl list | grep openclaw

# 停止
launchctl stop com.openclaw.trading
```

## 5. 数据库路径

- 股票数据: ~/Documents/OpenClawAgents/beifeng/data/stocks_real.db
- 信号: ~/Documents/OpenClawAgents/hongzhong/data/signals_v3.db
- 策略: ~/Documents/OpenClawAgents/strategy/strategy.db
