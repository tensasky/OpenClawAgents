# 北风 (BeiFeng) - 股票数据采集 Agent

## 功能
- A股日线数据抓取
- 多数据源支持（腾讯财经、新浪财经）
- 自动补全历史数据
- 定时更新保持最新

## 目录结构
```
beifeng/
├── beifeng.py          # 主程序
├── fetcher.py          # 数据抓取模块
├── monitor.py          # 监控模块
├── status.py           # 状态查看
├── discord_notify.py   # Discord通知
├── config/
│   └── config.ini      # 配置文件
├── data/
│   ├── stocks.db       # SQLite数据库
│   ├── all_stocks.json # 股票列表
│   └── hot_spots.json  # 热点数据
├── logs/               # 运行日志
└── scripts/
    ├── cron_update_sqlite.sh  # 定时任务
    └── setup_cron_manual.sh   # 配置脚本
```

## 使用
```bash
# 手动运行
python3 beifeng.py sh000001 --type daily

# 查看状态
python3 status.py

# 监控检查
python3 monitor.py
```

## 定时任务
```bash
# 每5分钟更新
*/5 * * * * /bin/bash ~/Documents/OpenClawAgents/beifeng/scripts/cron_update_sqlite.sh
```

## 数据说明
- 已入库: 2,470只股票
- 总记录: 122万条日线
- 数据库: 221MB
