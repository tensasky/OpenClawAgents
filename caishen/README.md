# 财神爷 (Orchestrator) —— 编排智能体

💰 **职责**：任务编排、Agent调度、执行路径优化

## 核心定位

财神爷不再处理具体数据或逻辑，而是负责：
- 根据市场状态和时间节点，自动拼装执行路径
- 调度其他7个Agent协同工作
- 不断优化7个Agent的技能和协作效率

## 核心功能

### 1. 任务编排 (Workflow Orchestration)

根据时间和市场状态，自动触发相应Agent：

| 时间 | 触发Agent | 任务 |
|------|-----------|------|
| 09:15 | 北风 | 开盘数据采集启动 |
| 09:30-11:30 | 北风+东风 | 实时数据+盘中监控 |
| 13:00-14:15 | 北风+东风 | 下午交易时段监控 |
| 14:30 | 西风 | 更新热点分析 |
| 14:45 | 红中 | 获取Top3并预警推送 |
| 14:50-15:00 | 发财 | 执行买入+风控检查 |
| 15:30 | 白板 | 收盘后归因分析 |
| 周日20:00 | 白板 | 全量回测+进化指令 |

### 2. Agent状态监控

- 监控7个Agent的健康状态
- 检测Agent是否正常运行
- 失败时自动重试或告警

### 3. 执行路径优化

- 根据白板进化指令，调整Agent执行顺序
- 优化Agent间数据流转
- 动态调整时间窗口

### 4. 技能管理

- 管理7个Agent的版本和配置
- 根据回测结果，建议Agent技能升级
- 协调Agent间的依赖关系

## 编排状态机

```
[Idle] → [PreMarket] → [MorningSession] → [NoonBreak] 
                                            ↓
[PostMarket] ← [AfternoonSession] ← [AfternoonStart]
      ↓
[DailyReview] → [WeeklyReview] → [Evolution]
```

## 文件结构

```
caishen/
├── caishen.py           # 主编排程序
├── scheduler.py         # 调度器
├── monitor.py           # Agent监控
├── optimizer.py         # 路径优化
├── skills/              # 7个Agent技能配置
│   ├── beifeng_skill.json
│   ├── xifeng_skill.json
│   ├── nanfeng_skill.json
│   ├── dongfeng_skill.json
│   ├── hongzhong_skill.json
│   ├── facai_skill.json
│   └── baiban_skill.json
├── data/
│   ├── workflow_state.json   # 当前工作流状态
│   ├── agent_status.json     # Agent状态
│   └── execution_log.json    # 执行日志
├── logs/                # 日志目录
└── README.md            # 本文件
```

## 运行方式

```bash
# 启动编排器（持续运行）
python caishen.py --daemon

# 手动触发特定时段工作流
python caishen.py --trigger morning    # 上午盘
python caishen.py --trigger afternoon  # 下午盘
python caishen.py --trigger preclose   # 收盘前
python caishen.py --trigger postclose  # 收盘后

# 检查所有Agent状态
python caishen.py --status

# 执行路径优化
python caishen.py --optimize

# 查看执行日志
python caishen.py --logs
```

## Agent依赖关系

```
北风 (数据基础)
  ├── 西风 (依赖北风数据)
  ├── 东风 (依赖北风数据)
  └── 南风 (依赖北风数据)

东风 (候选池)
  └── 红中 (依赖东风候选池)

红中 (Top3)
  └── 发财 (依赖红中Top3)

发财 (交易记录)
  └── 白板 (依赖发财记录)

白板 (进化指令)
  └── 财神爷 (接收指令，调度其他Agent)
```

## Emoji

💰
