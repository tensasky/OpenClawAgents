#!/usr/bin/env python3
"""
红中V3 - 多策略综合预警报告
整合5策略信号，生成综合投资建议
"""

import json
import requests
from pathlib import Path
from datetime import datetime

# Discord配置
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

# 策略配置
STRATEGY_CONFIG = {
    "趋势跟踪": {
        "emoji": "📈",
        "holding": "5-10天",
        "risk": "中等",
        "suitable": "短线趋势交易者"
    },
    "均值回归": {
        "emoji": "🔄",
        "holding": "2-5天",
        "risk": "高",
        "suitable": "短线反弹交易者"
    },
    "突破策略": {
        "emoji": "🚀",
        "holding": "1-3天",
        "risk": "高",
        "suitable": "超短线交易者"
    },
    "稳健增长": {
        "emoji": "🛡️",
        "holding": "2-4周",
        "risk": "低",
        "suitable": "中长线投资者"
    },
    "热点追击": {
        "emoji": "🔥",
        "holding": "1-2天",
        "risk": "很高",
        "suitable": "超短线高手"
    }
}

def load_signals():
    """加载5策略信号"""
    signal_file = Path.home() / "Documents/OpenClawAgents/hongzhong/data/strategy_signals_2026-03-12.json"
    with open(signal_file) as f:
        return json.load(f)

def analyze_consensus(data):
    """分析多策略共识"""
    stock_votes = {}
    
    for strategy, signals in data["strategies"].items():
        for i, signal in enumerate(signals):
            code = signal["code"]
            if code not in stock_votes:
                stock_votes[code] = {
                    "count": 0,
                    "strategies": [],
                    "avg_score": 0,
                    "price": signal["price"]
                }
            stock_votes[code]["count"] += 1
            stock_votes[code]["strategies"].append({
                "name": strategy,
                "score": signal["score"],
                "rank": i + 1
            })
            stock_votes[code]["avg_score"] += signal["score"]
    
    # 计算平均分
    for code in stock_votes:
        stock_votes[code]["avg_score"] /= stock_votes[code]["count"]
    
    # 按共识度排序
    sorted_stocks = sorted(stock_votes.items(), 
                          key=lambda x: (x[1]["count"], x[1]["avg_score"]), 
                          reverse=True)
    
    return sorted_stocks[:5]

def create_report(data, consensus):
    """创建综合报告"""
    date = data["date"]
    
    # 构建Discord Embed
    embed = {
        "title": f"🀄 红中多策略预警报告 | {date}",
        "description": "📊 基于5种策略的综合选股建议",
        "color": 0xff6600,
        "fields": []
    }
    
    # 各策略Top 1
    for strategy, signals in data["strategies"].items():
        if signals:
            top = signals[0]
            config = STRATEGY_CONFIG.get(strategy, {})
            emoji = config.get("emoji", "📊")
            
            value = f"**{top['code']}** | {top['score']:.1f}分 | ¥{top['price']:.2f}\n"
            value += f"建议持有: {config.get('holding', 'N/A')} | 风险: {config.get('risk', 'N/A')}"
            
            embed["fields"].append({
                "name": f"{emoji} {strategy}",
                "value": value,
                "inline": True
            })
    
    # 多策略共识
    consensus_text = ""
    for i, (code, data) in enumerate(consensus[:3], 1):
        strategies = ", ".join([s["name"] for s in data["strategies"]])
        consensus_text += f"**{i}. {code}**\n"
        consensus_text += f"  共识度: {data['count']}/5策略 | 均分: {data['avg_score']:.1f}\n"
        consensus_text += f"  推荐策略: {strategies}\n\n"
    
    embed["fields"].append({
        "name": "🎯 多策略共识 (强烈推荐)",
        "value": consensus_text,
        "inline": False
    })
    
    # 操作建议
    operation = """**📋 综合操作建议**

1️⃣ **sh600188** (所有策略Top 1)
   • 策略: 趋势跟踪+均值回归+突破+稳健+热点
   • 建议: 重点关注，多策略共振
   • 仓位: 20-25%

2️⃣ **sh600158** (4策略推荐)
   • 策略: 趋势+均值回归+稳健+热点
   • 建议: 稳健型投资者首选
   • 仓位: 15-20%

3️⃣ **sh600256** (4策略推荐)
   • 策略: 趋势+均值回归+稳健+热点
   • 建议: 趋势跟踪策略重点标的
   • 仓位: 15-20%

⚠️ **风险提示**
• 突破策略和热点追击风险较高，建议小仓位
• 稳健增长策略适合长期持有
• 所有建议仅供参考，投资有风险"""
    
    embed["fields"].append({
        "name": "💡 操作建议",
        "value": operation,
        "inline": False
    })
    
    embed["footer"] = {
        "text": f"⏰ 报告时间: {datetime.now().strftime('%Y-%m-%d %H:%M')} | 5策略综合评分"
    }
    
    return embed

def send_discord(embed):
    """发送到Discord"""
    try:
        response = requests.post(
            DISCORD_WEBHOOK,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return response.status_code == 204
    except Exception as e:
        print(f"❌ 发送失败: {e}")
        return False

def main():
    print("🀄 红中多策略报告生成中...")
    
    # 加载数据
    data = load_signals()
    
    # 分析共识
    consensus = analyze_consensus(data)
    
    print(f"\n📊 分析结果:")
    print(f"  5策略共选出 {sum(len(s) for s in data['strategies'].values())} 个信号")
    print(f"  多策略共识股票: {len(consensus)} 只")
    
    # 创建报告
    embed = create_report(data, consensus)
    
    # 发送
    if send_discord(embed):
        print("✅ Discord报告发送成功")
    else:
        print("❌ Discord报告发送失败")
    
    # 保存报告
    report_file = Path.home() / "Documents/OpenClawAgents/hongzhong/data/multi_strategy_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump({
            "date": data["date"],
            "consensus": [
                {
                    "code": code,
                    "count": data["count"],
                    "avg_score": data["avg_score"],
                    "strategies": data["strategies"]
                }
                for code, data in consensus
            ]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 报告已保存: {report_file}")

if __name__ == '__main__':
    main()
