#!/usr/bin/env python3
"""
南风 V5.2 - 策略调优版
目标: 月盈利5%+
改进: 动态止损止盈、策略差异化、风险精细管理
"""

from dataclasses import dataclass
from typing import Dict, List, Tuple
from strategy_config import StrategyConfig

@dataclass
class DynamicStopLoss:
    """动态止损配置"""
    initial_stop: float = -0.05  # 初始止损-5%
    trailing_start: float = 0.03  # 盈利3%启动移动止损
    trailing_step: float = 0.01   # 每涨1%，止损上移1%
    max_stop: float = -0.02       # 最大止损-2%（盈利后）

@dataclass
class DynamicTakeProfit:
    """动态止盈配置"""
    target_1: float = 0.05   # 第一目标5%
    target_2: float = 0.10   # 第二目标10%
    target_3: float = 0.15   # 第三目标15%
    
    # 分批止盈比例
    close_1: float = 0.30    # 第一目标卖出30%
    close_2: float = 0.40    # 第二目标卖出40%
    close_3: float = 1.0     # 第三目标卖出剩余
    
    # 时间止盈
    time_exit_days: int = 10  # 10天未达目标强制离场


# 调优后的5策略配置
STRATEGIES_V52 = {
    "趋势跟踪": {
        "config": StrategyConfig(
            name="趋势跟踪",
            description="识别强势趋势，顺势而为（目标月收益5-8%）",
            
            # 指标周期
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20, 60],
            
            # 权重配置 - 强化趋势
            trend_weight=0.55,      # 趋势权重最高
            momentum_weight=0.25,
            volume_weight=0.15,
            quality_weight=0.05,
            
            # 门槛值 - 严格筛选
            min_adx=35,             # ADX≥35（强趋势）
            min_ma20_slope=0.003,   # MA20斜率≥0.3%
            min_volume_ratio=1.5,   # 量比≥1.5
            score_threshold=8.0,    # 分数门槛8.0
            
            # RSI区间 - 允许强趋势
            rsi_low=45,
            rsi_high=75,
            
            # 交易建议
            holding_period="7-15天",
            entry_timing="收盘前30分钟",
            exit_strategy="移动止损+趋势反转",
            max_holding="30%",
            
            market_condition="趋势明确的市场",
            risk_level="中等",
            suitable_for="波段交易者"
        ),
        
        # 动态止损止盈
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.05,      # 初始-5%
            trailing_start=0.05,     # 盈利5%启动
            trailing_step=0.015,     # 每涨1.5%，止损上移1%
            max_stop=-0.03           # 最大回撤-3%
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.06,           # 第一目标6%
            target_2=0.12,           # 第二目标12%
            target_3=0.20,           # 第三目标20%
            close_1=0.30,            # 卖30%
            close_2=0.40,            # 卖40%
            close_3=1.0,             # 卖剩余
            time_exit_days=15        # 15天强制离场
        ),
        
        "monthly_target": 0.06      # 月目标6%
    },
    
    "均值回归": {
        "config": StrategyConfig(
            name="均值回归",
            description="捕捉超跌反弹（目标月收益5-10%，胜率关键）",
            
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            # 权重配置 - 强化动量
            trend_weight=0.15,
            momentum_weight=0.55,   # 动量权重最高
            volume_weight=0.20,
            quality_weight=0.10,
            
            # 门槛值 - 超卖区间
            min_adx=15,
            min_ma20_slope=-0.01,   # 允许下跌
            min_volume_ratio=1.2,
            score_threshold=7.5,
            
            # RSI区间 - 严格超卖
            rsi_low=20,             # RSI≤30为超卖
            rsi_high=40,
            
            holding_period="2-5天",
            entry_timing="RSI<30且企稳",
            exit_strategy="反弹即走，不恋战",
            max_holding="15%",
            
            market_condition="震荡市或回调后",
            risk_level="高",
            suitable_for="短线高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.03,      # 严格-3%止损
            trailing_start=0.02,     # 盈利2%启动
            trailing_step=0.01,
            max_stop=-0.01
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.04,           # 快速止盈
            target_2=0.08,
            target_3=0.12,
            close_1=0.50,            # 第一目标卖一半
            close_2=0.30,
            close_3=1.0,
            time_exit_days=5         # 5天必须走
        ),
        
        "monthly_target": 0.08
    },
    
    "突破策略": {
        "config": StrategyConfig(
            name="突破策略",
            description="捕捉突破行情（目标月收益8-12%，高盈亏比）",
            
            adx_period=7,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            # 权重配置 - 平衡型
            trend_weight=0.30,
            momentum_weight=0.30,
            volume_weight=0.35,     # 成交量关键
            quality_weight=0.05,
            
            # 门槛值 - 放量突破
            min_adx=25,
            min_ma20_slope=0.001,
            min_volume_ratio=2.5,   # 高放量要求
            score_threshold=8.0,
            
            rsi_low=45,
            rsi_high=65,
            
            holding_period="3-7天",
            entry_timing="突破确认后",
            exit_strategy="失败即走，成功持有",
            max_holding="20%",
            
            market_condition="热点活跃",
            risk_level="高",
            suitable_for="短线交易者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.04,      # 突破失败-4%止损
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.02
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.05,
            target_2=0.10,
            target_3=0.18,
            close_1=0.25,
            close_2=0.35,
            close_3=1.0,
            time_exit_days=7
        ),
        
        "monthly_target": 0.10
    },
    
    "稳健增长": {
        "config": StrategyConfig(
            name="稳健增长",
            description="追求稳定收益（目标月收益5%，低回撤）",
            
            adx_period=20,
            rsi_period=14,
            ma_periods=[10, 20, 60, 120],
            
            # 权重配置 - 质量优先
            trend_weight=0.40,
            momentum_weight=0.15,
            volume_weight=0.15,
            quality_weight=0.30,    # 质量权重最高
            
            # 门槛值 - 严格筛选
            min_adx=40,             # 强趋势要求
            min_ma20_slope=0.005,   # 稳定向上
            min_volume_ratio=1.0,
            score_threshold=9.0,    # 最高门槛
            
            rsi_low=45,
            rsi_high=55,            # RSI区间严格
            
            holding_period="15-30天",
            entry_timing="回调企稳",
            exit_strategy="基本面恶化或趋势反转",
            max_holding="35%",
            
            market_condition="牛市或震荡向上",
            risk_level="低",
            suitable_for="中长线投资者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.06,      # 较宽止损-6%
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.03
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.05,           # 稳健目标
            target_2=0.10,
            target_3=0.15,
            close_1=0.20,
            close_2=0.30,
            close_3=1.0,
            time_exit_days=30        # 最长持有30天
        ),
        
        "monthly_target": 0.05
    },
    
    "热点追击": {
        "config": StrategyConfig(
            name="热点追击",
            description="紧跟热点快进快出（目标月收益10%+，高风险高收益）",
            
            adx_period=5,           # 超短周期
            rsi_period=6,
            ma_periods=[5, 10],
            
            # 权重配置 - 动量+成交量
            trend_weight=0.25,
            momentum_weight=0.35,
            volume_weight=0.35,
            quality_weight=0.05,
            
            # 门槛值 - 热点特征
            min_adx=20,
            min_ma20_slope=0.002,
            min_volume_ratio=3.0,   # 极高放量
            score_threshold=7.5,
            
            rsi_low=55,             # 允许追高
            rsi_high=85,
            
            holding_period="1-3天",
            entry_timing="热点启动日",
            exit_strategy="热点退潮立即走",
            max_holding="15%",
            
            market_condition="热点轮动快",
            risk_level="很高",
            suitable_for="超短线高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.04,
            trailing_start=0.05,     # 快速启动移动止损
            trailing_step=0.02,      # 快速上移
            max_stop=-0.01
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.06,
            target_2=0.12,
            target_3=0.20,
            close_1=0.40,            # 快速减仓
            close_2=0.40,
            close_3=1.0,
            time_exit_days=3         # 3天必须走
        ),
        
        "monthly_target": 0.12
    }
}


def get_strategy_v52(name: str) -> Dict:
    """获取V5.2策略配置"""
    if name not in STRATEGIES_V52:
        raise ValueError(f"未知策略: {name}")
    return STRATEGIES_V52[name]


def calculate_position_size(strategy_name: str, confidence: float, 
                           account_value: float) -> float:
    """
    计算仓位大小
    
    Args:
        strategy_name: 策略名称
        confidence: 信号置信度(0-1)
        account_value: 账户总值
    
    Returns:
        建议仓位金额
    """
    strategy = get_strategy_v52(strategy_name)
    config = strategy["config"]
    
    # 基础仓位
    base_position = float(config.max_holding.strip('%')) / 100
    
    # 根据置信度调整
    position = base_position * confidence
    
    # 限制单票最大仓位
    max_single = 0.30  # 单票最大30%
    position = min(position, max_single)
    
    return account_value * position


def calculate_stop_loss_price(entry_price: float, strategy_name: str,
                              current_price: float = None) -> Tuple[float, str]:
    """
    计算动态止损价格
    
    Args:
        entry_price: 入场价格
        strategy_name: 策略名称
        current_price: 当前价格（用于移动止损）
    
    Returns:
        (止损价格, 止损类型)
    """
    strategy = get_strategy_v52(strategy_name)
    sl_config = strategy["stop_loss"]
    
    if current_price is None or current_price <= entry_price:
        # 初始止损
        stop_price = entry_price * (1 + sl_config.initial_stop)
        return stop_price, "initial"
    
    # 计算盈利比例
    profit_pct = (current_price - entry_price) / entry_price
    
    if profit_pct < sl_config.trailing_start:
        # 未启动移动止损
        stop_price = entry_price * (1 + sl_config.initial_stop)
        return stop_price, "initial"
    
    # 移动止损
    trailing_levels = int((profit_pct - sl_config.trailing_start) / sl_config.trailing_step)
    stop_pct = sl_config.initial_stop + (trailing_levels * sl_config.trailing_step)
    stop_pct = max(stop_pct, sl_config.max_stop)  # 不低于最大止损
    
    stop_price = entry_price * (1 + stop_pct)
    return stop_price, f"trailing_L{trailing_levels}"


def calculate_take_profit_levels(entry_price: float, strategy_name: str) -> Dict:
    """
    计算止盈目标
    
    Args:
        entry_price: 入场价格
        strategy_name: 策略名称
    
    Returns:
        止盈配置字典
    """
    strategy = get_strategy_v52(strategy_name)
    tp_config = strategy["take_profit"]
    
    return {
        "target_1": {
            "price": entry_price * (1 + tp_config.target_1),
            "profit_pct": tp_config.target_1 * 100,
            "close_pct": tp_config.close_1 * 100
        },
        "target_2": {
            "price": entry_price * (1 + tp_config.target_2),
            "profit_pct": tp_config.target_2 * 100,
            "close_pct": tp_config.close_2 * 100
        },
        "target_3": {
            "price": entry_price * (1 + tp_config.target_3),
            "profit_pct": tp_config.target_3 * 100,
            "close_pct": tp_config.close_3 * 100
        },
        "time_exit_days": tp_config.time_exit_days
    }


if __name__ == '__main__':
    print("="*70)
    print("南风V5.2 - 策略调优配置")
    print("="*70)
    
    for name, strategy in STRATEGIES_V52.items():
        config = strategy["config"]
        monthly_target = strategy["monthly_target"]
        
        print(f"\n📊 {name}")
        print(f"  月目标: {monthly_target:.1%}")
        print(f"  止损: {strategy['stop_loss'].initial_stop:.1%} → {strategy['stop_loss'].max_stop:.1%}")
        print(f"  止盈: {strategy['take_profit'].target_1:.1%}/{strategy['take_profit'].target_2:.1%}/{strategy['take_profit'].target_3:.1%}")
        print(f"  持有: {config.holding_period}")
    
    print("\n" + "="*70)
    
    # 测试计算
    print("\n💡 示例计算（趋势跟踪策略，入场价100元）:")
    entry = 100.0
    
    # 止损计算
    stop_price, stop_type = calculate_stop_loss_price(entry, "趋势跟踪")
    print(f"  初始止损: {stop_price:.2f} ({stop_type})")
    
    # 移动止损（盈利10%后）
    stop_price, stop_type = calculate_stop_loss_price(entry, "趋势跟踪", current_price=110.0)
    print(f"  移动止损(盈利10%): {stop_price:.2f} ({stop_type})")
    
    # 止盈目标
    tp_levels = calculate_take_profit_levels(entry, "趋势跟踪")
    print(f"  止盈目标:")
    for level, data in tp_levels.items():
        if level.startswith("target"):
            print(f"    {level}: {data['price']:.2f} (+{data['profit_pct']:.1f}%) 卖出{data['close_pct']:.0f}%")
    
    print("="*70)
