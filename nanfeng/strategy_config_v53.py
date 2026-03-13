#!/usr/bin/env python3
"""
南风 V5.3 - 白板优化版
基于白板V2优化建议，目标平均收益>3%
核心改进：提高门槛、收紧止损、增加过滤
"""

from dataclasses import dataclass
from typing import Dict, List
from strategy_config import StrategyConfig

@dataclass
class DynamicStopLoss:
    """动态止损配置"""
    initial_stop: float = -0.03      # 收紧至-3%
    trailing_start: float = 0.03
    trailing_step: float = 0.01
    max_stop: float = -0.01          # 最大止损-1%

@dataclass
class DynamicTakeProfit:
    """动态止盈配置"""
    target_1: float = 0.05
    target_2: float = 0.10
    target_3: float = 0.15
    close_1: float = 0.30
    close_2: float = 0.40
    close_3: float = 1.0
    time_exit_days: int = 10


# V5.3优化后的5策略配置
STRATEGIES_V53 = {
    "趋势跟踪": {
        "config": StrategyConfig(
            name="趋势跟踪",
            description="识别强势趋势（白板优化版，目标>3%）",
            
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20, 60],
            
            # 权重配置
            trend_weight=0.55,
            momentum_weight=0.25,
            volume_weight=0.15,
            quality_weight=0.05,
            
            # 门槛值 - 大幅提高
            min_adx=40,                 # 从35提高到40
            min_ma20_slope=0.005,       # 从0.003提高到0.005
            min_volume_ratio=2.0,       # 从1.5提高到2.0
            score_threshold=8.5,        # 保持8.5
            
            # RSI区间
            rsi_low=50,                 # 从45提高到50
            rsi_high=70,                # 从75降低到70
            
            holding_period="7-15天",
            entry_timing="收盘前30分钟",
            exit_strategy="移动止损+趋势反转",
            max_holding="25%",
            
            market_condition="强趋势市场",
            risk_level="中等",
            suitable_for="波段交易者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.03,         # 收紧
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
        
        "filters": {
            'market_adx_min': 20,       # 大盘ADX>20
            'hot_sector_required': True, # 要求热点板块
            'min_stocks_in_sector': 3    # 板块内至少3只上涨
        },
        
        "monthly_target": 0.05
    },
    
    "均值回归": {
        "config": StrategyConfig(
            name="均值回归",
            description="捕捉超跌反弹（白板优化版）",
            
            adx_period=14,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            trend_weight=0.15,
            momentum_weight=0.55,
            volume_weight=0.20,
            quality_weight=0.10,
            
            # 门槛值 - 更严格
            min_adx=15,
            min_ma20_slope=-0.01,
            min_volume_ratio=1.5,       # 从1.2提高到1.5
            score_threshold=8.0,        # 从7.5提高到8.0
            
            rsi_low=15,                 # 从20降低到15（更超卖）
            rsi_high=35,                # 从40降低到35
            
            holding_period="2-5天",
            entry_timing="RSI<20且企稳",
            exit_strategy="反弹即走",
            max_holding="15%",
            
            market_condition="震荡市",
            risk_level="高",
            suitable_for="短线高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.02,         # 严格-2%
            trailing_start=0.02,
            trailing_step=0.01,
            max_stop=-0.01
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.04,
            target_2=0.08,
            target_3=0.12,
            close_1=0.50,
            close_2=0.30,
            close_3=1.0,
            time_exit_days=5
        ),
        
        "filters": {
            'market_adx_max': 25,       # 大盘ADX<25（震荡市）
            'require_reversal_candle': True  # 要求反转K线
        },
        
        "monthly_target": 0.06
    },
    
    "突破策略": {
        "config": StrategyConfig(
            name="突破策略",
            description="捕捉突破行情（白板优化版）",
            
            adx_period=7,
            rsi_period=6,
            ma_periods=[5, 10, 20],
            
            trend_weight=0.30,
            momentum_weight=0.30,
            volume_weight=0.35,
            quality_weight=0.05,
            
            # 门槛值 - 大幅提高
            min_adx=30,                 # 从25提高到30
            min_ma20_slope=0.003,       # 从0.001提高到0.003
            min_volume_ratio=3.0,       # 从2.5提高到3.0
            score_threshold=8.5,        # 从8.0提高到8.5
            
            rsi_low=45,
            rsi_high=65,
            
            holding_period="3-7天",
            entry_timing="突破确认后",
            exit_strategy="失败即走",
            max_holding="20%",
            
            market_condition="热点活跃",
            risk_level="高",
            suitable_for="短线交易者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.02,         # 严格-2%
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.01
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
        
        "filters": {
            'market_adx_min': 20,
            'hot_sector_required': True,
            'breakout_volume_min': 3.5   # 突破时量比>3.5
        },
        
        "monthly_target": 0.08
    },
    
    "稳健增长": {
        "config": StrategyConfig(
            name="稳健增长",
            description="追求稳定收益（白板优化版）",
            
            adx_period=20,
            rsi_period=14,
            ma_periods=[10, 20, 60, 120],
            
            trend_weight=0.40,
            momentum_weight=0.15,
            volume_weight=0.15,
            quality_weight=0.30,
            
            # 门槛值 - 最严格
            min_adx=45,                 # 从40提高到45
            min_ma20_slope=0.008,       # 从0.005提高到0.008
            min_volume_ratio=1.2,       # 从1.0提高到1.2
            score_threshold=9.0,        # 保持9.0
            
            rsi_low=48,                 # 从45提高到48
            rsi_high=55,                # 保持55
            
            holding_period="15-30天",
            entry_timing="回调企稳",
            exit_strategy="基本面恶化",
            max_holding="30%",
            
            market_condition="牛市",
            risk_level="低",
            suitable_for="中长线投资者"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.05,         # 较宽-5%
            trailing_start=0.03,
            trailing_step=0.01,
            max_stop=-0.02
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
        
        "filters": {
            'market_adx_min': 25,       # 大盘ADX>25（牛市）
            'ma_alignment_required': True  # 要求均线多头排列
        },
        
        "monthly_target": 0.04
    },
    
    "热点追击": {
        "config": StrategyConfig(
            name="热点追击",
            description="紧跟热点（白板优化版）",
            
            adx_period=5,
            rsi_period=6,
            ma_periods=[5, 10],
            
            trend_weight=0.25,
            momentum_weight=0.35,
            volume_weight=0.35,
            quality_weight=0.05,
            
            # 门槛值 - 极高
            min_adx=25,                 # 从20提高到25
            min_ma20_slope=0.003,       # 从0.002提高到0.003
            min_volume_ratio=4.0,       # 从3.0提高到4.0
            score_threshold=8.5,        # 从7.5提高到8.5
            
            rsi_low=60,                 # 从55提高到60
            rsi_high=80,
            
            holding_period="1-3天",
            entry_timing="热点启动日",
            exit_strategy="热点退潮立即走",
            max_holding="15%",
            
            market_condition="热点轮动",
            risk_level="很高",
            suitable_for="超短线高手"
        ),
        
        "stop_loss": DynamicStopLoss(
            initial_stop=-0.02,         # 极严格-2%
            trailing_start=0.05,
            trailing_step=0.02,
            max_stop=-0.01
        ),
        
        "take_profit": DynamicTakeProfit(
            target_1=0.06,
            target_2=0.12,
            target_3=0.20,
            close_1=0.40,
            close_2=0.40,
            close_3=1.0,
            time_exit_days=3
        ),
        
        "filters": {
            'hot_sector_required': True,
            'sector_momentum_min': 0.05,  # 板块涨幅>5%
            'leader_only': True           # 只追龙头
        },
        
        "monthly_target": 0.10
    }
}


def get_strategy_v53(name: str) -> Dict:
    """获取V5.3策略配置"""
    if name not in STRATEGIES_V53:
        raise ValueError(f"未知策略: {name}")
    return STRATEGIES_V53[name]


def check_market_filter(strategy_name: str, market_adx: float) -> bool:
    """检查大盘过滤条件"""
    strategy = get_strategy_v53(strategy_name)
    filters = strategy.get('filters', {})
    
    # 检查ADX下限
    if 'market_adx_min' in filters:
        if market_adx < filters['market_adx_min']:
            return False
    
    # 检查ADX上限
    if 'market_adx_max' in filters:
        if market_adx > filters['market_adx_max']:
            return False
    
    return True


def check_sector_filter(strategy_name: str, is_hot_sector: bool, 
                       sector_momentum: float = 0) -> bool:
    """检查板块过滤条件"""
    strategy = get_strategy_v53(strategy_name)
    filters = strategy.get('filters', {})
    
    # 是否要求热点板块
    if filters.get('hot_sector_required', False):
        if not is_hot_sector:
            return False
    
    # 板块动量要求
    if 'sector_momentum_min' in filters:
        if sector_momentum < filters['sector_momentum_min']:
            return False
    
    return True


if __name__ == '__main__':
    print("="*70)
    print("南风V5.3 - 白板优化版")
    print("="*70)
    
    for name, strategy in STRATEGIES_V53.items():
        config = strategy["config"]
        monthly_target = strategy["monthly_target"]
        filters = strategy.get('filters', {})
        
        print(f"\n📊 {name}")
        print(f"  月目标: {monthly_target:.1%}")
        print(f"  止损: {strategy['stop_loss'].initial_stop:.1%}")
        print(f"  门槛: ADX≥{config.min_adx}, 分数≥{config.score_threshold}")
        print(f"  过滤: {filters}")
    
    print("\n" + "="*70)
    print("✅ V5.3优化要点:")
    print("  1. 统一收紧止损至-2%~-3%")
    print("  2. 提高score_threshold至8.0+")
    print("  3. 增加大盘ADX过滤")
    print("  4. 增加板块热点过滤")
    print("  5. 提高成交量要求")
    print("="*70)
