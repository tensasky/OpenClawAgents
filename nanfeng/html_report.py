#!/usr/bin/env python3
"""
HTML报告生成器 - 多策略综合报告
"""

from datetime import datetime
from typing import List, Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("南风")



def generate_html_report(strategies_data: List[Dict], market_msg: str = "") -> str:
    """
    生成HTML格式的多策略综合报告
    
    strategies_data: [
        {
            'strategy_name': '趋势跟踪',
            'strategy_config': {...},
            'signals': [{code, name, score, ...}, ...]
        },
        ...
    ]
    """
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header .subtitle {{
            margin-top: 10px;
            opacity: 0.9;
        }}
        .market-info {{
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 15px 20px;
            margin-bottom: 30px;
            border-radius: 5px;
        }}
        .strategy-section {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin-bottom: 25px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .strategy-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 2px solid #f0f0f0;
        }}
        .strategy-title {{
            font-size: 22px;
            font-weight: bold;
            color: #333;
        }}
        .risk-badge {{
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .risk-low {{ background: #4caf50; color: white; }}
        .risk-medium {{ background: #ff9800; color: white; }}
        .risk-high {{ background: #f44336; color: white; }}
        .risk-very-high {{ background: #9c27b0; color: white; }}
        
        .strategy-desc {{
            color: #666;
            margin-bottom: 15px;
        }}
        
        .stock-card {{
            background: #fafafa;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .stock-code {{
            font-size: 20px;
            font-weight: bold;
            color: #333;
        }}
        .stock-name {{
            color: #666;
            margin-left: 10px;
        }}
        .score-box {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 10px 20px;
            border-radius: 8px;
            text-align: center;
        }}
        .score-value {{
            font-size: 24px;
            font-weight: bold;
        }}
        .score-label {{
            font-size: 12px;
            opacity: 0.9;
        }}
        
        .metrics-grid {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }}
        .metric-item {{
            background: white;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .metric-label {{
            font-size: 11px;
            color: #999;
            margin-bottom: 5px;
        }}
        .metric-value {{
            font-size: 16px;
            font-weight: bold;
            color: #333;
        }}
        
        .score-breakdown {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 15px;
        }}
        .score-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #f0f0f0;
        }}
        .score-row:last-child {{
            border-bottom: none;
            font-weight: bold;
            color: #667eea;
        }}
        
        .trading-advice {{
            background: #fff3e0;
            border-left: 4px solid #ff9800;
            padding: 15px;
            border-radius: 5px;
            margin-top: 15px;
        }}
        .advice-title {{
            font-weight: bold;
            color: #e65100;
            margin-bottom: 10px;
        }}
        .advice-item {{
            padding: 5px 0;
            color: #666;
        }}
        
        .footer {{
            text-align: center;
            color: #999;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 多策略量化选股报告</h1>
        <div class="subtitle">{datetime.now().strftime('%Y年%m月%d日 %H:%M')}</div>
    </div>
"""
    
    # 市场环境
    if market_msg:
        html += f"""
    <div class="market-info">
        <strong>📊 市场环境:</strong> {market_msg}
    </div>
"""
    
    # 每个策略一个章节
    for strategy_data in strategies_data:
        config = strategy_data['strategy_config']
        signals = strategy_data['signals']
        name = strategy_data['strategy_name']
        
        # 风险等级样式
        risk_class = "risk-medium"
        if config['risk_level'] == '低':
            risk_class = "risk-low"
        elif config['risk_level'] == '高':
            risk_class = "risk-high"
        elif config['risk_level'] == '很高':
            risk_class = "risk-very-high"
        
        html += f"""
    <div class="strategy-section">
        <div class="strategy-header">
            <div>
                <div class="strategy-title">{name}</div>
                <div class="strategy-desc">{config.get('description', '')}</div>
            </div>
            <span class="risk-badge {risk_class}">{config['risk_level']}风险</span>
        </div>
"""
        
        # 策略配置摘要
        html += f"""
        <div style="background: #f5f5f5; padding: 15px; border-radius: 5px; margin-bottom: 20px;">
            <strong>策略配置:</strong> 
            持有周期 {config['holding_period']} | 
            ADX≥{config.get('min_adx', 30)} | 
            RSI {config.get('rsi_low', 45):.0f}-{config.get('rsi_high', 65):.0f} | 
            量比≥{config.get('min_volume_ratio', 1.2)}
        </div>
"""
        
        # 每只股票
        for i, stock in enumerate(signals, 1):
            score = stock.get('score', 0)
            trend = stock.get('trend_score', 0)
            momentum = stock.get('momentum_score', 0)
            volume = stock.get('volume_score', 0)
            quality = stock.get('quality_score', 0)
            
            html += f"""
        <div class="stock-card">
            <div class="stock-header">
                <div>
                    <span class="stock-code">#{i} {stock['code']}</span>
                    <span class="stock-name">{stock.get('name', '')}</span>
                </div>
                <div class="score-box">
                    <div class="score-value">{score:.1f}</div>
                    <div class="score-label">/ 10分</div>
                </div>
            </div>
            
            <div class="metrics-grid">
                <div class="metric-item">
                    <div class="metric-label">当前价格</div>
                    <div class="metric-value">¥{stock.get('price', 0):.2f}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">止损价格</div>
                    <div class="metric-value">¥{stock.get('stop_loss', 0):.2f}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">ADX</div>
                    <div class="metric-value">{stock.get('adx', 0):.1f}</div>
                </div>
                <div class="metric-item">
                    <div class="metric-label">RSI</div>
                    <div class="metric-value">{stock.get('rsi', 0):.0f}</div>
                </div>
            </div>
            
            <div class="score-breakdown">
                <div class="score-row">
                    <span>📈 趋势得分 (权重{config.get('trend_weight', 0.4):.0%})</span>
                    <span>{trend * config.get('trend_weight', 0.4):.1f}分</span>
                </div>
                <div class="score-row">
                    <span>⚡ 动量得分 (权重{config.get('momentum_weight', 0.3):.0%})</span>
                    <span>{momentum * config.get('momentum_weight', 0.3):.1f}分</span>
                </div>
                <div class="score-row">
                    <span>📊 成交量得分 (权重{config.get('volume_weight', 0.2):.0%})</span>
                    <span>{volume * config.get('volume_weight', 0.2):.1f}分</span>
                </div>
                <div class="score-row">
                    <span>✨ 质量得分 (权重{config.get('quality_weight', 0.1):.0%})</span>
                    <span>{quality * config.get('quality_weight', 0.1):.1f}分</span>
                </div>
                <div class="score-row">
                    <span>🎯 综合得分</span>
                    <span>{score:.1f}分 / 10分</span>
                </div>
            </div>
            
            <div style="margin-top: 10px; color: #666; font-size: 14px;">
                <strong>买入信号:</strong> {' | '.join(stock.get('signals', [])[:3])}
            </div>
            
            <div class="trading-advice">
                <div class="advice-title">💡 交易建议</div>
                <div class="advice-item">📅 <strong>持有周期:</strong> {config['holding_period']}</div>
                <div class="advice-item">⏰ <strong>入场时机:</strong> {config['entry_timing']}</div>
                <div class="advice-item">🚪 <strong>出场策略:</strong> {config['exit_strategy']}</div>
                <div class="advice-item">💼 <strong>最大仓位:</strong> {config['max_holding']}</div>
                <div class="advice-item">👤 <strong>适合人群:</strong> {config['suitable_for']}</div>
            </div>
        </div>
"""
        
        html += "    </div>\n"
    
    # 页脚
    html += """
    <div class="footer">
        <p>🤖 报告由财神爷量化系统生成 | 南风V5.1多策略</p>
        <p style="font-size: 12px; color: #999;">⚠️ 风险提示: 以上分析仅供参考，不构成投资建议。投资有风险，入市需谨慎。</p>
    </div>
</body>
</html>
"""
    
    return html


if __name__ == '__main__':
    # 测试
    test_data = [
        {
            'strategy_name': '趋势跟踪',
            'strategy_config': {
                'description': '识别强势趋势，顺势而为',
                'risk_level': '中等',
                'holding_period': '5-10天',
                'entry_timing': '收盘前30分钟',
                'exit_strategy': '移动止损',
                'max_holding': '25%',
                'suitable_for': '短线趋势交易者',
                'trend_weight': 0.5,
                'momentum_weight': 0.25,
                'volume_weight': 0.15,
                'quality_weight': 0.1,
                'min_adx': 30,
                'rsi_low': 50,
                'rsi_high': 70,
                'min_volume_ratio': 1.2
            },
            'signals': [
                {
                    'code': 'sh600268',
                    'name': '国电南自',
                    'score': 8.5,
                    'trend_score': 35,
                    'momentum_score': 12,
                    'volume_score': 20,
                    'quality_score': 5,
                    'price': 16.12,
                    'stop_loss': 14.13,
                    'adx': 41.9,
                    'rsi': 79,
                    'signals': ['多头排列', 'MA20强势向上', '强趋势ADX=41.9']
                }
            ]
        }
    ]
    
    html = generate_html_report(test_data, "大盘环境良好ADX=26.0，今日+1.45%")
    print(html[:2000])
    log.info("\n... (HTML内容已截断)")
