# 监控 (Monitor) - 系统监控 Agent

## 功能
- 监控所有 Agent 运行状态
- 检查日志更新
- 异常告警
- 生成健康报告

## 目录结构
```
monitor/
├── monitor.py          # 主程序
├── alerts/             # 告警配置
└── README.md           # 本文件
```

## 使用
```bash
# 检查所有 Agent
python3 monitor.py

# 定时监控（每小时）
0 * * * * python3 ~/Documents/OpenClawAgents/monitor/monitor.py
```

## 监控指标
- Agent 目录是否存在
- 日志文件更新时间
- 数据库连接状态
- 磁盘空间

## Emoji
👁️
