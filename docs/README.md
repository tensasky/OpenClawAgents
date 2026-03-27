# OpenClaw 量化交易系统

**版本**: v4.4.1  
**更新时间**: 2026-03-27

## 系统架构

9-Agent协同工作的A股量化交易系统

| Agent | 职责 |
|-------|------|
| 北风 | 数据采集 |
| 东风 | 候选池筛选 |
| 南风 | 策略评分 |
| 红中 | 信号生成 |
| 发财 | 交易执行 |
| 白板 | 回测优化 |
| 判官 | 数据校验 |
| 财神爷 | 调度管理 |

## 快速开始

```bash
# 启动调度器
python3 manager/process_manager_v2.py
```

## 核心文件

- `manager/` - 调度系统
- `dongfeng/` - 候选池
- `hongzhong/` - 信号生成
- `facai/` - 交易执行
- `baiban/` - 回测优化
- `strategy/` - 策略库

## 文档

详细文档见 `docs/COMPLETE.md`
