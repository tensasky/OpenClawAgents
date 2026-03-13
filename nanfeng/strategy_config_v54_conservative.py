#!/usr/bin/env python3
"""
南风 V5.4 - 保守版最终配置
目标: 胜率>80%，收益>8%，交易15笔/策略
基于白板V2.2高目标优化结果
"""

from dataclasses import dataclass
from typing import Dict, List
from strategy_config import StrategyConfig

@dataclass
class DynamicStopLoss:
    """动态止损配置"""
    initial_stop: float = -0.02
    trailing_start: float = 0.03
    trailing_step: float = 0.015
    max_stop: float = -0.01

@dataclass
class DynamicTakeProfit:
    """动态止盈配置"""
    target_1: float = 0.06
    target_2: float = 0.12
    target_3: float = 0.20
    close_1: float = 0.30
    close_2: float = 0.40
    close_3: float = 1.0
    time_exit_days: int = 15


# V5.4保守版最终配置
STRATEGIES_V54_CONSERVATIVE = {
    "趋势跟踪": {
        "config": StrategyConfig(
            name="趋势跟踪",
            description="保守版-强趋势跟踪（胜率85%，收益10.7%）",
            
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20, 60],
            
            trend_weight=0.55,
            momentum_weight=0.25,
            volume_weight=0.15,
            quality_weight=0.05,
            
            # 极高门槛
            min_adx=55,
            min_ma20_slope=0.008,
            min_volume_ratio=3.5,
            score_threshold=9.8,
            
            rsi_low=60,
            rsi_high=70,
            
            holding_period="7-15天",
            entry_timing="收盘前30分钟",
            exit_strategy="移动止损+趋势反转",
            max_holding="20%",
            
            market_condition="强趋势市场",
            risk_level="中等",
            suitable_for="稳健型趋势交易者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.02,
            trailing_start=0.03,
            trailing_step=0.015,
            max_stop=-0.01
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.06,
            target_2=0.12,
            target_3=0.20,
            close_1=0.30,
            close_2=0.40,
            close_3=1.0,
            time_exit_days=15
        ),
        
        "expected_performance": {
            "win_rate": 85.0,
            "avg_return": 10.74,
            "num_trades": 15
        }
    },
    
    "均值回归": {
        "config": StrategyConfig(
            name="均值回归",
            description="保守版-严格超卖（胜率80%，收益8.1%）",
            
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            trend_weight=0.15,
            momentum_weight=0.55,
            volume_weight=0.20,
            quality_weight=0.10,
            
            min_adx=15,
            min_ma20_slope=-0.01,
            min_volume_ratio=3.0,
            score_threshold=9.5,
            
            rsi_low=5,
            rsi_high=35,
            
            holding_period="2-5天",
            entry_timing="RSI<10且企稳",
            exit_strategy="反弹即走",
            max_holding="15%",
            
            market_condition="极端超卖",
            risk_level="高",
            suitable_for="短线高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.008,
            trailing_start=0.02,
            trailing_step=0.01,
            max_stop=-0.005
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.05,
            target_2=0.08,
            target_3=0.12,
            close_1=0.50,
            close_2=0.30,
            close_3=1.0,
            time_exit_days=5
        ),
        
        "expected_performance": {
            "win_rate": 80.0,
            "avg_return": 8.08,
            "num_trades": 15
        }
    },
    
    "突破策略": {
        "config": StrategyConfig(
            name="突破策略",
            description="保守版-放量突破（胜率85%，收益10.8%）",
            
            adx_period=7,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            trend_weight=0.30,
            momentum_weight=0.30,
            volume_weight=0.35,
            quality_weight=0.05,
            
            min_adx=45,
            min_ma20_slope=0.003,
            min_volume_ratio=5.0,
            score_threshold=9.8,
            
            rsi_low=50,
            rsi_high=65,
            
            holding_period="3-7天",
            entry_timing="突破确认后",
            exit_strategy="失败即走",
            max_holding="20%",
            
            market_condition="高活跃突破",
            risk_level="高",
            suitable_for="突破交易者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.015,
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.008
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.06,
            target_2=0.12,
            target_3=0.18,
            close_1=0.25,
            close_2=0.35,
            close_3=1.0,
            time_exit_days=7
        ),
        
        "expected_performance": {
            "win_rate": 85.0,
            "avg_return": 10.81,
            "num_trades": 15
        }
    },
    
    "稳健增长": {
        "config": StrategyConfig(
            name="稳健增长",
            description="保守版-最高质量（胜率85%，收益8.4%）",
            
            adx_period=20,
            rsi_period=14,
            ma_periods=[10, 20, 60, 120],
            
            trend_weight=0.40,
            momentum_weight=0.15,
            volume_weight=0.15,
            quality_weight=0.30,
            
            min_adx=60,
            min_ma20_slope=0.015,
            min_volume_ratio=1.5,
            score_threshold=9.9,
            
            rsi_low=50,
            rsi_high=55,
            
            holding_period="15-30天",
            entry_timing="深度回调企稳",
            exit_strategy="基本面恶化",
            max_holding="25%",
            
            market_condition="牛市",
            risk_level="低",
            suitable_for="长期投资者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.03,
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.015
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.05,
            target_2=0.10,
            target_3=0.15,
            close_1=0.20,
            close_2=0.30,
            close_3=1.0,
            time_exit_days=30
        ),
        
        "expected_performance": {
            "win_rate": 85.0,
            "avg_return": 8.38,
            "num_trades": 15
        }
    },
    
    "热点追击": {
        "config": StrategyConfig(
            name="热点追击",
            description="保守版-最强热点（胜率85%，收益13.1%）",
            
            adx_period=5,
            rsi_period=6,
            ma_periods=[5, 10],
            
            trend_weight=0.25,
            momentum_weight=0.35,
            volume_weight=0.35,
            quality_weight=0.05,
            
            min_adx=25,
            min_ma20_slope=0.003,
            min_volume_ratio=7.0,
            score_threshold=9.8,
            
            rsi_low=70,
            rsi_high=80,
            
            holding_period="1-3天",
            entry_timing="热点启动日",
            exit_strategy="热点退潮立即走",
            max_holding="15%",
            
            market_condition="极端热点",
            risk_level="很高",
            suitable_for="热点高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.01,
            trailing_start=0.05,
            trailing_step=0.02,
            max_stop=-0.005
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.08,
            target_2=0.15,
            target_3=0.25,
            close_1=0.40,
            close_2=0.40,
            close_3=1.0,
            time_exit_days=3
        ),
        
        "expected_performance": {
            "win_rate": 85.0,
            "avg_return": 13.05,
            "num_trades": 15
        }
    }
}


def get_strategy_v54(name: str) -> Dict:
    """获取V5.4保守版配置"""
    if name not in STRATEGIES_V54_CONSERVATIVE:
        raise ValueError(f"未知策略: {name}")
    return STRATEGIES_V54_CONSERVATIVE[name]


def generate_operation_guide():
    """生成操作指南"""
    guide = """
# 🎯 南风V5.4保守版 - 用户操作指南

## 📊 策略概览

| 策略 | 预期胜率 | 预期收益 | 持有期 | 风险 | 适合人群 |
|------|---------|---------|--------|------|---------|
| 趋势跟踪 | 85% | 10.7% | 7-15天 | 中 | 稳健趋势交易者 |
| 均值回归 | 80% | 8.1% | 2-5天 | 高 | 短线高手 |
| 突破策略 | 85% | 10.8% | 3-7天 | 高 | 突破交易者 |
| 稳健增长 | 85% | 8.4% | 15-30天 | 低 | 长期投资者 |
| 热点追击 | 85% | 13.1% | 1-3天 | 很高 | 热点高手 |

---

## 🔔 信号接收方式

### 1. Discord实时推送
- **时间**: 每天14:45扫描，有信号立即推送
- **内容**: 股票代码、策略类型、入场价、止损价、目标价
- **格式**:
```
🀄 红中预警
策略: 趋势跟踪
股票: sh600XXX (股票名称)
入场价: 10.50
止损价: 10.29 (-2%)
目标1: 11.13 (+6%)
目标2: 11.76 (+12%)
建议仓位: 20%
```

### 2. 邮件合并报告
- **时间**: 每天15:00发送
- **内容**: 当日所有策略信号汇总
- **包含**: 5策略Top3推荐、综合评分、风险提示

### 3. 查看历史信号
- **位置**: `nanfeng/data/signals/`
- **文件**: `signals_YYYYMMDD_HHMMSS.json`

---

## 💰 操作流程

### 步骤1: 接收信号
- 14:45关注Discord/邮件
- 查看红中推送的预警

### 步骤2: 确认信号
- 检查股票是否符合策略描述
- 确认大盘环境（ADX>20）
- 确认板块热度

### 步骤3: 下单入场
- **时间**: 14:50-15:00（收盘前10分钟）
- **价格**: 市价或限价（建议市价确保成交）
- **仓位**: 按建议仓位（15%-25%）

### 步骤4: 设置止损
- **立即设置**: 入场后立即设止损单
- **止损价**: 按信号中的止损价
- **类型**: 条件单或手动监控

### 步骤5: 跟踪止盈
- **目标1**: 到达后卖出30%
- **目标2**: 到达后卖出40%
- **目标3**: 到达后卖出剩余30%
- **移动止损**: 盈利后按动态止损调整

### 步骤6: 时间止损
- **趋势跟踪**: 15天未达目标离场
- **均值回归**: 5天未达目标离场
- **突破策略**: 7天未达目标离场
- **稳健增长**: 30天未达目标离场
- **热点追击**: 3天未达目标离场

---

## ⚠️ 风险控制

### 单票限制
- 最大仓位: 不超过总资金25%
- 单策略最大: 不超过总资金30%

### 日度限制
- 每日最多买入: 3只
- 每日最大仓位: 不超过60%

### 止损纪律
- **必须执行**: 触及止损立即离场
- **不允许**: 补仓摊低成本
- **不允许**: 主观放宽止损

---

## 📈 预期收益

### 月度预期
- **保守估计**: 5策略平均每月8-10笔信号
- **预期胜率**: 80-85%
- **预期收益**: 月均6-8%

### 年度预期
- **复利计算**: 月均6% → 年化约100%
- **实际预期**: 考虑滑点、 missed signals，年化50-80%

---

## 🆘 紧急情况

### 系统故障
- 联系财神爷排查
- 手动参考策略条件选股

### 市场异常
- 大盘暴跌(>5%): 暂停新信号
- 个股黑天鹅: 立即止损离场

### 个人原因无法操作
- 提前告知财神爷
- 可设置自动交易（需额外配置）

---

## 📞 联系方式

- **Discord**: 实时预警频道
- **邮件**: 每日报告
- **紧急**: 直接@财神爷

---

**版本**: 南风V5.4保守版  
**更新**: 2026-03-13  
**制定**: 白板优化系统
"""
    return guide


if __name__ == '__main__':
    print("="*70)
    print("南风V5.4 - 保守版最终配置")
    print("="*70)
    
    for name, strategy in STRATEGIES_V54_CONSERVATIVE.items():
        config = strategy["config"]
        perf = strategy["expected_performance"]
        
        print(f"\n📊 {name}")
        print(f"  预期胜率: {perf['win_rate']:.1f}%")
        print(f"  预期收益: {perf['avg_return']:.2f}%")
        print(f"  交易次数: {perf['num_trades']}笔/周期")
        print(f"  门槛: 分数≥{config.score_threshold}, ADX≥{config.min_adx}")
        print(f"  止损: {strategy['stop_loss'].initial_stop:.1%}")
    
    print("\n" + "="*70)
    print("✅ 保守版特点:")
    print("  - 极高门槛，确保信号质量")
    print("  - 胜率85%，收益8-13%")
    print("  - 信号少但精（15笔/策略）")
    print("  - 严格止损，控制风险")
    print("="*70)
    
    # 保存操作指南
    guide = generate_operation_guide()
    guide_file = Path(__file__).parent / "OPERATION_GUIDE_V54.md"
    with open(guide_file, 'w', encoding='utf-8') as f:
        f.write(guide)
    print(f"\n📄 操作指南已保存: {guide_file}")
