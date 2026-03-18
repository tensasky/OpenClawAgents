#!/usr/bin/env python3
"""
南风策略配置中心 - 多策略量化选股
支持多种预设策略，每种策略包含指标配置和交易建议
"""

from typing import Dict, List
from dataclasses import dataclass
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("南风")


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    description: str
    
    # 指标周期
    adx_period: int = 14
    rsi_period: int = 6
    ma_periods: List[int] = None
    volume_period: int = 5
    
    # 权重配置
    trend_weight: float = 0.40
    momentum_weight: float = 0.30
    volume_weight: float = 0.20
    quality_weight: float = 0.10
    
    # 门槛值 (100分制)
    min_adx: float = 30
    min_ma20_slope: float = 0.002
    min_volume_ratio: float = 1.2
    score_threshold: float = 40  # 合格线40分
    
    # RSI区间
    rsi_low: float = 30
    rsi_high: float = 80
    
    # 交易建议
    holding_period: str = "5-10天"  # 建议持有周期
    entry_timing: str = "收盘前30分钟"  # 入场时机
    exit_strategy: str = "分批止盈"  # 出场策略
    max_holding: str = "20%"  # 最大仓位
    
    # 适用场景
    market_condition: str = "趋势市"  # 适用市场
    risk_level: str = "中等"  # 风险等级
    suitable_for: str = "短线交易者"  # 适合人群


# 预设策略库
STRATEGIES = {
    "趋势跟踪": StrategyConfig(
        name="趋势跟踪",
        description="识别强势趋势，顺势而为",
        adx_period=14,
        rsi_period=6,
        ma_periods=[5, 10, 20, 60],
        
        trend_weight=0.45,
        momentum_weight=0.35,
        volume_weight=0.10,
        quality_weight=0.10,
        
        min_adx=20,
        min_ma20_slope=0.001,
        rsi_low=30,
        rsi_high=80,
        
        holding_period="5-10天",
        entry_timing="收盘前30分钟或开盘30分钟",
        exit_strategy="移动止损，趋势反转离场",
        max_holding="25%",
        
        market_condition="趋势明确的市场",
        risk_level="中等",
        suitable_for="短线趋势交易者"
    ),
    
    "均值回归": StrategyConfig(
        name="均值回归",
        description="捕捉超跌反弹机会",
        adx_period=14,
        rsi_period=6,
        ma_periods=[5, 10, 20, 60],
        
        trend_weight=0.20,
        momentum_weight=0.50,
        volume_weight=0.20,
        quality_weight=0.10,
        
        min_adx=15,  # 趋势不强时反而有机会
        min_ma20_slope=-0.005,  # 允许短期下跌
        rsi_low=25,  # 超卖区间
        rsi_high=45,
        
        holding_period="2-5天",
        entry_timing="RSI低于30且出现企稳信号",
        exit_strategy="反弹至压力位或RSI回到50以上",
        max_holding="15%",
        
        market_condition="震荡市或回调后的市场",
        risk_level="高",
        suitable_for="短线反弹交易者，需严格止损"
    ),
    
    "突破策略": StrategyConfig(
        name="突破策略",
        description="捕捉突破关键位置的爆发行情",
        adx_period=7,  # 短周期更敏感
        rsi_period=6,
        ma_periods=[5, 10, 20],
        volume_period=5,
        
        trend_weight=0.35,
        momentum_weight=0.25,
        volume_weight=0.35,  # 成交量权重提高
        quality_weight=0.05,
        
        min_adx=25,
        min_ma20_slope=0.001,
        min_volume_ratio=2.0,  # 要求放量
        rsi_low=40,
        rsi_high=60,
        
        holding_period="1-3天",
        entry_timing="突破当日收盘前或次日开盘",
        exit_strategy="3%止损，8%止盈，不留恋",
        max_holding="20%",
        
        market_condition="热点活跃，成交量放大",
        risk_level="高",
        suitable_for="超短线交易者，盯盘时间充足"
    ),
    
    "稳健增长": StrategyConfig(
        name="稳健增长",
        description="追求稳定收益，低风险偏好",
        adx_period=20,  # 长周期更稳定
        rsi_period=14,
        ma_periods=[10, 20, 60, 120],
        
        trend_weight=0.45,
        momentum_weight=0.20,
        volume_weight=0.15,
        quality_weight=0.20,  # 质量权重提高
        
        min_adx=35,  # 要求更强的趋势
        min_ma20_slope=0.003,
        min_volume_ratio=1.0,
        rsi_low=45,
        rsi_high=55,  # RSI区间更严格
        score_threshold=25,  # 100分制，门槛更高
        
        holding_period="2-4周",
        entry_timing="回调至支撑位，企稳后买入",
        exit_strategy="基本面恶化或趋势反转",
        max_holding="30%",
        
        market_condition="牛市或震荡向上",
        risk_level="低",
        suitable_for="中长线投资者，上班族"
    ),
    
    "热点追击": StrategyConfig(
        name="热点追击",
        description="紧跟市场热点，快进快出",
        adx_period=7,
        rsi_period=6,
        ma_periods=[5, 10, 20],
        
        trend_weight=0.30,
        momentum_weight=0.30,
        volume_weight=0.30,
        quality_weight=0.10,
        
        min_adx=20,
        min_ma20_slope=0.001,
        min_volume_ratio=2.5,  # 高放量要求
        rsi_low=50,
        rsi_high=80,  # 允许追高
        
        holding_period="1-2天",
        entry_timing="热点启动首日或次日早盘",
        exit_strategy="热点退潮立即离场，不恋战",
        max_holding="15%",
        
        market_condition="热点轮动快，题材活跃",
        risk_level="很高",
        suitable_for="超短线高手，风险承受能力强"
    )
}


def get_strategy(name: str) -> StrategyConfig:
    """获取策略配置"""
    if name not in STRATEGIES:
        raise ValueError(f"未知策略: {name}。可用策略: {list(STRATEGIES.keys())}")
    return STRATEGIES[name]


def list_strategies() -> Dict[str, str]:
    """列出所有策略"""
    return {name: config.description for name, config in STRATEGIES.items()}


def format_strategy_info(strategy: StrategyConfig) -> str:
    """格式化策略信息"""
    return f"""
{'='*60}
📊 {strategy.name} - {strategy.description}
{'='*60}

【指标配置】
  ADX周期: {strategy.adx_period}日 | RSI周期: {strategy.rsi_period}日
  均线: {', '.join(map(str, strategy.ma_periods or [5,10,20]))}

【权重分配】
  趋势: {strategy.trend_weight:.0%} | 动量: {strategy.momentum_weight:.0%}
  成交量: {strategy.volume_weight:.0%} | 质量: {strategy.quality_weight:.0%}

【门槛条件】
  ADX ≥ {strategy.min_adx} | MA20斜率 ≥ {strategy.min_ma20_slope*100:.2f}%
  RSI区间: {strategy.rsi_low:.0f}-{strategy.rsi_high:.0f}
  量比 ≥ {strategy.min_volume_ratio} | 分数 ≥ {strategy.score_threshold}

【交易建议】💡
  持有周期: {strategy.holding_period}
  入场时机: {strategy.entry_timing}
  出场策略: {strategy.exit_strategy}
  最大仓位: {strategy.max_holding}

【适用场景】
  市场条件: {strategy.market_condition}
  风险等级: {strategy.risk_level}
  适合人群: {strategy.suitable_for}
{'='*60}
"""


if __name__ == '__main__':
    # 测试
    log.info("可用策略:")
    for name, desc in list_strategies().items():
        log.info(f"  - {name}: {desc}")
    
    log.info("\n" + format_strategy_info(STRATEGIES["趋势跟踪"]))
