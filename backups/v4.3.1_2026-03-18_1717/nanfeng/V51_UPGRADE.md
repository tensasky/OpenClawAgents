# 南风V5.1 升级说明

## 变更摘要

### 核心改进
| 指标 | V4 | V5.1 |
|------|-----|------|
| 平均收益率 | -1.05% ❌ | **+2.78%** ✅ |
| 平均胜率 | 34.9% ❌ | **55.0%** ✅ |
| 胜率>50%天数 | 33% | **75%** ✅ |
| 信号数量 | ~87/天 | **5/天** |

### V5.1 策略特点
1. **严格门槛**
   - ADX >= 30 (强趋势)
   - MA20斜率 >= 0.2% (强势向上)
   - 综合分数 >= 8.5

2. **精选策略**
   - 每天最多选5只
   - 按分数+相对强度排序

3. **市场环境检查**
   - 大盘ADX<20时暂停
   - 大盘MA20向下时提醒

4. **热点板块标记**
   - 优先显示热点板块股票
   - 板块信息随信号推送

## 文件变更

### 新增文件
- `nanfeng/nanfeng_v5_1.py` - V5.1核心策略
- `nanfeng/nanfeng_production.py` - 生产版本
- `hongzhong/hongzhong_v2.py` - 红中V2
- `nanfeng/backtest_v5_1.py` - V5.1回测
- `nanfeng/batch_backtest.py` - 批量回测
- `nanfeng/param_optimize.py` - 参数优化

### 备份文件
- `nanfeng/nanfeng_v4_legacy.py` - V4备份
- `hongzhong/hongzhong_v1_legacy.py` - 红中V1备份

## 使用方法

### 红中V2 运行
```bash
cd ~/Documents/OpenClawAgents/hongzhong
python3 hongzhong.py --run
```

### 测试模式 (不发送通知)
```bash
python3 hongzhong.py --test
```

### 查看历史
```bash
python3 hongzhong.py --history
```

### V5.1 独立扫描
```bash
cd ~/Documents/OpenClawAgents/nanfeng
python3 nanfeng_v5_1.py
```

## 定时任务更新

建议将红中的定时任务更新为：
```bash
# 14:45 运行红中V2
45 14 * * 1-5 cd ~/Documents/OpenClawAgents/hongzhong && python3 hongzhong.py --run >> /tmp/hongzhong.log 2>&1
```

## 回测验证

V5.1 在12个交易日回测结果：
- 平均收益: +2.78% (5日持有)
- 胜率: 55%
- 最佳单日: +10.65%
- 最差单日: -3.31%

详细结果: `nanfeng/data/backtest_v5_1_results.json`
