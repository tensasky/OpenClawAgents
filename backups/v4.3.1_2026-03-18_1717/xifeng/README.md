# 西风 (XiFeng) - 舆情与热点分析 Agent

## 功能
- 财经新闻抓取与语义分析
- 板块热度评分
- 爆发系数计算
- 热点分级输出

## 目录结构
```
xifeng/
├── xifeng.py           # 主程序
├── realistic_news.py   # 新闻生成器
├── heat_model.py       # 热度评分模型
├── discord_notify.py   # Discord通知
├── config/
│   └── config.json     # 配置文件
├── data/
│   ├── xifeng.db       # SQLite数据库
│   └── hot_spots.json  # 热点输出
├── logs/               # 运行日志
└── scripts/
    └── run.sh          # 定时任务脚本
```

## 使用
```bash
# 手动运行
python3 xifeng.py

# 查看热点
cat data/hot_spots.json
```

## 定时任务
```bash
# 每30分钟分析
*/30 * * * * /bin/bash ~/Documents/OpenClawAgents/xifeng/scripts/run.sh
```

## 热度算法
```
Heat_Score = 0.3 × Frequency + 0.5 × Momentum + 0.2 × Sentiment

分级:
- High: > 80
- Medium: 40-80
- Low: < 40
```
