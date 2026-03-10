# 红中 (Red Dragon) - 决策预警与自动化通信专家

🀄 **职责**：收盘前精英筛选、综合打分、多渠道推送预警

## 核心工作时段

- **启动时间**：14:30（收盘前30分钟）开始最终打分
- **推送窗口**：14:45 - 14:55
- **推送频率**：每5分钟一次（14:45, 14:50, 14:55）
- **截止时刻**：14:55强制停止

## 核心功能逻辑

### 1. 精英筛选 (Top 3 Filter)
- 获取东风的候选池列表
- 调用南风打分逻辑即时重算（14:30后数据最接近收盘价）
- 仅推送 Top 1-3 且分数 > 8.0 的标的

### 2. 稳健推送机制
- **并发推送**：邮件、飞书、Discord 三管齐下
- **超时重试**：单渠道30s超时，最多3次重试
- **容错处理**：失败记录日志，不耽误下一轮推送

### 3. 预警模板
包含四Agent智慧结晶：
- 西风：题材热度
- 南风：技术形态
- 东风：初筛信息
- 红中：综合评分与风险提示

## 文件结构

```
hongzhong/
├── hongzhong.py           # 主程序
├── config.yaml            # 配置文件
├── notifier.py            # 通知模块
├── data/
│   ├── alert_history.json # 预警历史
│   └── top_picks.json     # 当前Top3
├── templates/
│   └── alert_template.md  # 预警模板
├── logs/                  # 日志目录
└── README.md              # 本文件
```

## 运行方式

```bash
# 手动执行一次筛选和推送
python hongzhong.py --run

# 进入定时推送模式（14:45-14:55）
python hongzhong.py --monitor

# 测试推送渠道
python hongzhong.py --test-notify

# 查看预警历史
python hongzhong.py --history
```

## Agent 协作流程

```
14:30 ━━ 红中启动
   ↓
获取东风 candidate_pool.json
   ↓
调用南风打分逻辑重算
   ↓
筛选 Top 1-3 (分数>8.0)
   ↓
14:45 ━━ 第一次推送
14:50 ━━ 第二次推送  
14:55 ━━ 第三次推送（截止）
   ↓
邮件 + 飞书 + Discord
```

## Emoji

🀄
