#!/usr/bin/env python3
"""
白板 V2.0 - 持续优化系统
基于回测结果自动优化策略参数，目标平均收益>3%
"""

import json
import numpy as np
from datetime import datetime
from pathlib import Path
from typing import Dict, List

REPORT_DIR = Path(__file__).parent / "reports"
OPTIMIZE_DIR = Path(__file__).parent / "optimize"
OPTIMIZE_DIR.mkdir(exist_ok=True)


class StrategyOptimizer:
    """策略优化器"""
    
    def __init__(self, backtest_results: Dict):
        self.results = backtest_results
        self.strategy_name = backtest_results['strategy']
        self.current_config = self.load_current_config()
        
    def load_current_config(self) -> Dict:
        """加载当前配置"""
        # 从V5.2配置中读取
        import sys
        sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))
        from strategy_config_v52 import get_strategy_v52
        
        strategy = get_strategy_v52(self.strategy_name)
        return {
            'score_threshold': strategy['config'].score_threshold,
            'rsi_low': strategy['config'].rsi_low,
            'rsi_high': strategy['config'].rsi_high,
            'min_volume_ratio': strategy['config'].min_volume_ratio,
            'min_adx': strategy['config'].min_adx,
            'initial_stop': strategy['stop_loss'].initial_stop,
            'trailing_start': strategy['stop_loss'].trailing_start,
        }
    
    def analyze_problems(self) -> List[str]:
        """分析问题"""
        problems = []
        
        # 胜率分析
        if self.results['win_rate'] < 40:
            problems.append(f"胜率过低({self.results['win_rate']:.1f}%)，需要提高信号质量")
        
        # 收益分析
        if self.results['avg_return'] < 3.0:
            problems.append(f"平均收益不足({self.results['avg_return']:.2f}%)，低于3%目标")
        
        # 盈亏比分析
        if self.results['profit_factor'] < 1.5:
            problems.append(f"盈亏比偏低({self.results['profit_factor']:.2f})，盈利覆盖不了亏损")
        
        # 退出原因分析
        stop_loss_count = self.results['exit_reasons'].get('止损(initial)', 0)
        stop_loss_pct = stop_loss_count / self.results['total_trades'] * 100
        if stop_loss_pct > 25:
            problems.append(f"止损过多({stop_loss_pct:.1f}%)，止损条件可能过宽")
        
        time_exit_count = self.results['exit_reasons'].get('时间止损', 0)
        time_exit_pct = time_exit_count / self.results['total_trades'] * 100
        if time_exit_pct > 30:
            problems.append(f"时间止损过多({time_exit_pct:.1f}%)，持有期可能过短")
        
        return problems
    
    def generate_optimizations(self) -> List[Dict]:
        """生成优化建议"""
        optimizations = []
        
        # 根据策略类型生成特定优化
        if self.strategy_name == "趋势跟踪":
            optimizations.extend([
                {
                    'param': 'score_threshold',
                    'current': self.current_config['score_threshold'],
                    'suggested': 8.5,
                    'reason': '提高门槛，筛选更强趋势',
                    'expected_impact': '胜率↑，交易数↓'
                },
                {
                    'param': 'min_adx',
                    'current': self.current_config['min_adx'],
                    'suggested': 40,
                    'reason': '要求更强趋势确认',
                    'expected_impact': '胜率↑，假突破↓'
                },
                {
                    'param': 'initial_stop',
                    'current': self.current_config['initial_stop'],
                    'suggested': -0.03,
                    'reason': '收紧止损，保护本金',
                    'expected_impact': '单笔亏损↓，胜率可能↓'
                },
                {
                    'param': 'trailing_start',
                    'current': self.current_config['trailing_start'],
                    'suggested': 0.03,
                    'reason': '更早启动移动止损',
                    'expected_impact': '锁定利润↑'
                }
            ])
            
        elif self.strategy_name == "均值回归":
            optimizations.extend([
                {
                    'param': 'score_threshold',
                    'current': self.current_config['score_threshold'],
                    'suggested': 8.0,
                    'reason': '提高门槛，避免弱势反弹',
                    'expected_impact': '胜率↑'
                },
                {
                    'param': 'rsi_low',
                    'current': self.current_config['rsi_low'],
                    'suggested': 15,
                    'reason': '更严格的超卖条件',
                    'expected_impact': '信号质量↑，数量↓'
                },
                {
                    'param': 'initial_stop',
                    'current': self.current_config['initial_stop'],
                    'suggested': -0.02,
                    'reason': '严格止损，防止深跌',
                    'expected_impact': '单笔亏损↓'
                },
                {
                    'param': 'min_volume_ratio',
                    'current': self.current_config['min_volume_ratio'],
                    'suggested': 1.5,
                    'reason': '要求放量确认',
                    'expected_impact': '反弹可靠性↑'
                }
            ])
            
        elif self.strategy_name == "突破策略":
            optimizations.extend([
                {
                    'param': 'score_threshold',
                    'current': self.current_config['score_threshold'],
                    'suggested': 8.5,
                    'reason': '只选最强突破',
                    'expected_impact': '胜率↑，数量↓'
                },
                {
                    'param': 'min_volume_ratio',
                    'current': self.current_config['min_volume_ratio'],
                    'suggested': 3.0,
                    'reason': '要求更高放量',
                    'expected_impact': '假突破↓'
                },
                {
                    'param': 'initial_stop',
                    'current': self.current_config['initial_stop'],
                    'suggested': -0.02,
                    'reason': '突破失败立即止损',
                    'expected_impact': '亏损控制↑'
                },
                {
                    'param': 'rsi_high',
                    'current': self.current_config['rsi_high'],
                    'suggested': 70,
                    'reason': '允许更强动量',
                    'expected_impact': '不错过强势突破'
                }
            ])
            
        elif self.strategy_name == "稳健增长":
            optimizations.extend([
                {
                    'param': 'score_threshold',
                    'current': self.current_config['score_threshold'],
                    'suggested': 9.0,
                    'reason': '只选最高质量',
                    'expected_impact': '胜率↑↑'
                },
                {
                    'param': 'min_adx',
                    'current': self.current_config['min_adx'],
                    'suggested': 45,
                    'reason': '最强趋势要求',
                    'expected_impact': '回撤↓'
                },
                {
                    'param': 'initial_stop',
                    'current': self.current_config['initial_stop'],
                    'suggested': -0.04,
                    'reason': '允许正常波动',
                    'expected_impact': '减少过早止损'
                }
            ])
            
        elif self.strategy_name == "热点追击":
            optimizations.extend([
                {
                    'param': 'score_threshold',
                    'current': self.current_config['score_threshold'],
                    'suggested': 8.0,
                    'reason': '只追最强热点',
                    'expected_impact': '胜率↑'
                },
                {
                    'param': 'min_volume_ratio',
                    'current': self.current_config['min_volume_ratio'],
                    'suggested': 4.0,
                    'reason': '极高放量要求',
                    'expected_impact': '热点强度↑'
                },
                {
                    'param': 'rsi_low',
                    'current': self.current_config['rsi_low'],
                    'suggested': 60,
                    'reason': '只追强势',
                    'expected_impact': '弱势过滤'
                },
                {
                    'param': 'initial_stop',
                    'current': self.current_config['initial_stop'],
                    'suggested': -0.02,
                    'reason': '极严格止损',
                    'expected_impact': '亏损控制↑'
                }
            ])
        
        # 通用优化：增加大盘过滤
        optimizations.append({
            'param': 'market_filter',
            'current': '无',
            'suggested': '大盘ADX>20',
            'reason': '弱势市场不交易',
            'expected_impact': '系统性风险↓'
        })
        
        return optimizations
    
    def generate_report(self) -> str:
        """生成优化报告"""
        problems = self.analyze_problems()
        optimizations = self.generate_optimizations()
        
        report = f"""## 🀆 {self.strategy_name} 优化报告

### 📊 当前表现
- **平均收益**: {self.results['avg_return']:.2f}% (目标: >3%)
- **胜率**: {self.results['win_rate']:.1f}%
- **盈亏比**: {self.results['profit_factor']:.2f}
- **交易次数**: {self.results['total_trades']}

### ❌ 发现问题
"""
        
        for i, problem in enumerate(problems, 1):
            report += f"{i}. {problem}\n"
        
        if not problems:
            report += "✅ 无明显问题，可微调参数进一步提升\n"
        
        report += "\n### 💡 优化建议\n\n"
        report += "| 参数 | 当前值 | 建议值 | 优化理由 | 预期效果 |\n"
        report += "|------|--------|--------|----------|----------|\n"
        
        for opt in optimizations:
            report += f"| {opt['param']} | {opt['current']} | {opt['suggested']} | {opt['reason']} | {opt['expected_impact']} |\n"
        
        report += "\n### 🎯 优先级排序\n\n"
        report += "1. **立即执行**: 提高score_threshold，过滤低质量信号\n"
        report += "2. **高优先级**: 收紧initial_stop，控制单笔亏损\n"
        report += "3. **中优先级**: 调整RSI区间，优化入场时机\n"
        report += "4. **长期优化**: 增加大盘环境过滤\n"
        
        return report


def generate_master_optimization_plan(all_results: List[Dict]):
    """生成总体优化计划"""
    
    plan_file = OPTIMIZE_DIR / f"optimization_plan_{datetime.now().strftime('%Y%m%d_%H%M')}.md"
    
    with open(plan_file, 'w', encoding='utf-8') as f:
        f.write("# 🀆 白板V2 - 南风策略优化总计划\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("**优化目标**: 平均收益 > 3%，胜率 > 40%\n\n")
        f.write("---\n\n")
        
        # 总体分析
        avg_returns = [r['avg_return'] for r in all_results]
        avg_win_rates = [r['win_rate'] for r in all_results]
        
        f.write("## 📈 总体分析\n\n")
        f.write(f"- **策略平均收益**: {np.mean(avg_returns):.2f}%\n")
        f.write(f"- **平均胜率**: {np.mean(avg_win_rates):.1f}%\n")
        f.write(f"- **达标策略**: {sum(1 for r in all_results if r['avg_return'] > 3)}/5\n\n")
        
        # 各策略优化报告
        for results in all_results:
            optimizer = StrategyOptimizer(results)
            f.write(optimizer.generate_report())
            f.write("\n---\n\n")
        
        # 总体建议
        f.write("## 🎯 总体优化建议\n\n")
        f.write("### 立即执行（本周）\n\n")
        f.write("1. **统一提高门槛**: 所有策略score_threshold提升至8.0+\n")
        f.write("2. **收紧止损**: 初始止损统一调整为-3%\n")
        f.write("3. **增加大盘过滤**: 大盘ADX<20时暂停交易\n\n")
        
        f.write("### 短期优化（本月）\n\n")
        f.write("1. **策略差异化**: 根据回测结果调整各策略参数\n")
        f.write("2. **增加板块过滤**: 只交易热点板块内股票\n")
        f.write("3. **优化持仓期**: 根据策略特点调整时间止损\n\n")
        
        f.write("### 长期规划（下月）\n\n")
        f.write("1. **机器学习优化**: 用历史数据训练参数\n")
        f.write("2. **动态权重**: 根据市场环境调整策略权重\n")
        f.write("3. **组合优化**: 多策略组合降低整体波动\n\n")
        
        f.write("---\n\n")
        f.write("## 📋 执行检查清单\n\n")
        f.write("- [ ] 更新strategy_config_v52.py参数\n")
        f.write("- [ ] 增加大盘ADX过滤逻辑\n")
        f.write("- [ ] 增加板块热点过滤\n")
        f.write("- [ ] 重新回测验证\n")
        f.write("- [ ] 部署到生产环境\n\n")
    
    print(f"\n📄 优化计划已保存: {plan_file}")
    return plan_file


def main():
    """主程序"""
    print("="*70)
    print("🀆 白板V2.0 - 策略持续优化系统")
    print("="*70)
    
    # 模拟加载回测结果（实际应从文件读取）
    # 这里使用示例数据
    sample_results = [
        {
            'strategy': '趋势跟踪',
            'avg_return': 2.35,
            'win_rate': 25.0,
            'profit_factor': 3.47,
            'total_trades': 24,
            'exit_reasons': {'持有期末': 17, '止损(initial)': 3, '止盈目标2': 4}
        },
        {
            'strategy': '均值回归',
            'avg_return': -0.50,
            'win_rate': 33.3,
            'profit_factor': 0.68,
            'total_trades': 51,
            'exit_reasons': {'时间止损': 17, '止损(initial)': 16, '持有期末': 17, '止盈目标3': 1}
        },
        {
            'strategy': '突破策略',
            'avg_return': -1.29,
            'win_rate': 13.6,
            'profit_factor': 0.37,
            'total_trades': 22,
            'exit_reasons': {'止损(initial)': 7, '时间止损': 3, '持有期末': 12}
        },
        {
            'strategy': '稳健增长',
            'avg_return': 1.54,
            'win_rate': 51.3,
            'profit_factor': 1.86,
            'total_trades': 39,
            'exit_reasons': {'持有期末': 27, '止盈目标2': 2, '止损(initial)': 9, '止盈目标3': 1}
        },
        {
            'strategy': '热点追击',
            'avg_return': 0.18,
            'win_rate': 3.8,
            'profit_factor': float('inf'),
            'total_trades': 26,
            'exit_reasons': {'时间止损': 26}
        }
    ]
    
    plan_file = generate_master_optimization_plan(sample_results)
    
    print("\n" + "="*70)
    print("✅ 优化计划生成完成！")
    print("="*70)
    print("\n🎯 核心优化方向:")
    print("  1. 提高score_threshold至8.0+")
    print("  2. 收紧initial_stop至-3%")
    print("  3. 增加大盘ADX>20过滤")
    print("  4. 增加板块热点过滤")
    print("="*70)


if __name__ == '__main__':
    main()
