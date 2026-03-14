#!/usr/bin/env python3
"""
西风 - 优化版新闻生成器
基于真实市场规律生成模拟数据
"""

import json
import random
from datetime import datetime
from typing import List, Dict
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("西风")


# 板块配置（带权重和关联性）
SECTORS_CONFIG = {
    "人工智能": {
        "weight": 10,
        "keywords": ["AI", "大模型", "ChatGPT", "算力", "芯片", "GPU"],
        "sentiment_bias": 0.3,  # 偏向利好
        "volatility": "high"
    },
    "低空经济": {
        "weight": 8,
        "keywords": ["低空经济", "飞行汽车", "eVTOL", "无人机"],
        "sentiment_bias": 0.4,
        "volatility": "high"
    },
    "机器人": {
        "weight": 9,
        "keywords": ["机器人", "人形机器人", "减速器", "伺服电机"],
        "sentiment_bias": 0.2,
        "volatility": "high"
    },
    "半导体": {
        "weight": 7,
        "keywords": ["半导体", "芯片", "光刻机", "国产替代"],
        "sentiment_bias": 0.1,
        "volatility": "medium"
    },
    "新能源": {
        "weight": 8,
        "keywords": ["新能源", "光伏", "储能", "锂电池", "宁德时代"],
        "sentiment_bias": 0.0,
        "volatility": "medium"
    },
    "医药": {
        "weight": 6,
        "keywords": ["医药", "创新药", "CXO", "医疗器械", "减肥药"],
        "sentiment_bias": 0.0,
        "volatility": "low"
    },
    "汽车": {
        "weight": 7,
        "keywords": ["汽车", "新能源汽车", "比亚迪", "特斯拉", "小米汽车"],
        "sentiment_bias": 0.1,
        "volatility": "medium"
    },
    "金融": {
        "weight": 5,
        "keywords": ["银行", "保险", "券商", "央行", "降息"],
        "sentiment_bias": 0.0,
        "volatility": "low"
    },
    "房地产": {
        "weight": 4,
        "keywords": ["房地产", "楼市", "房价", "地产", "LPR"],
        "sentiment_bias": -0.1,
        "volatility": "low"
    },
    "消费": {
        "weight": 5,
        "keywords": ["消费", "白酒", "茅台", "免税", "旅游"],
        "sentiment_bias": 0.1,
        "volatility": "low"
    },
}

# 新闻模板
NEWS_TEMPLATES = {
    "high_positive": [
        "{sector}板块今日大涨，{keyword}概念股集体涨停",
        "政策利好{sector}，{keyword}产业迎来爆发期",
        "{sector}龙头{keyword}发布超预期财报，净利润增长200%",
        "机构密集调研{sector}，{keyword}成为新风口",
        "{sector}板块资金净流入超百亿，{keyword}领涨",
    ],
    "medium_positive": [
        "{sector}板块震荡上行，{keyword}表现活跃",
        "{sector}行业景气度回升，{keyword}订单增长",
        "政策扶持{sector}发展，{keyword}技术取得突破",
        "{sector}板块获北向资金增持，{keyword}受青睐",
    ],
    "neutral": [
        "{sector}板块震荡整理，{keyword}等待方向选择",
        "{sector}行业数据发布，{keyword}表现平稳",
        "{sector}板块分化明显，{keyword}个股涨跌互现",
    ],
    "medium_negative": [
        "{sector}板块回调，{keyword}获利盘出逃",
        "{sector}行业竞争加剧，{keyword}毛利率下滑",
        "{sector}板块资金净流出，{keyword}承压",
    ],
    "high_negative": [
        "{sector}板块大跌，{keyword}概念股跌停",
        "{sector}行业监管趋严，{keyword}面临整顿",
        "{sector}龙头{keyword}业绩暴雷，股价闪崩",
        "{sector}板块遭遇黑天鹅，{keyword}全线下跌",
    ]
}


class RealisticNewsGenerator:
    """真实感新闻生成器"""
    
    def __init__(self):
        self.sectors = list(SECTORS_CONFIG.keys())
        self.weights = [SECTORS_CONFIG[s]["weight"] for s in self.sectors]
    
    def generate_news(self, count: int = 100) -> List[Dict]:
        """生成新闻"""
        news_list = []
        
        for i in range(count):
            # 按权重选择板块
            sector = random.choices(self.sectors, weights=self.weights)[0]
            config = SECTORS_CONFIG[sector]
            
            # 选择关键词
            keyword = random.choice(config["keywords"])
            
            # 根据情感偏向选择模板
            sentiment_bias = config["sentiment_bias"]
            rand = random.random() + sentiment_bias
            
            if rand > 0.8:
                template_category = "high_positive"
                sentiment = random.uniform(0.5, 1.0)
            elif rand > 0.6:
                template_category = "medium_positive"
                sentiment = random.uniform(0.1, 0.5)
            elif rand > 0.4:
                template_category = "neutral"
                sentiment = random.uniform(-0.1, 0.1)
            elif rand > 0.2:
                template_category = "medium_negative"
                sentiment = random.uniform(-0.5, -0.1)
            else:
                template_category = "high_negative"
                sentiment = random.uniform(-1.0, -0.5)
            
            template = random.choice(NEWS_TEMPLATES[template_category])
            title = template.format(sector=sector, keyword=keyword)
            
            # 生成时间（今天随机时间）
            hour = random.randint(9, 15)
            minute = random.randint(0, 59)
            time_str = f"2026-03-09 {hour:02d}:{minute:02d}:00"
            
            news_list.append({
                'title': title,
                'content': title + '。市场分析人士认为，该板块后续走势值得关注。',
                'source': random.choice(['财联社', '东方财富', '新浪财经', '同花顺']),
                'url': f'https://news.example.com/{i}',
                'time': time_str,
                'sector': sector,
                'sentiment': round(sentiment, 2),
                'keywords': [keyword, sector]
            })
        
        return news_list


def fetch_realistic_news(count: int = 100) -> List[Dict]:
    """获取真实感新闻"""
    generator = RealisticNewsGenerator()
    return generator.generate_news(count)


if __name__ == '__main__':
    log.info("🌪️ 西风 - 真实感新闻生成")
    log.info("=" * 60)
    
    news_list = fetch_realistic_news(100)
    
    log.info(f"生成 {len(news_list)} 条新闻\n")
    
    # 统计
    sectors = {}
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    
    for news in news_list:
        s = news['sector']
        sectors[s] = sectors.get(s, 0) + 1
        
        if news['sentiment'] > 0.2:
            sentiments["positive"] += 1
        elif news['sentiment'] < -0.2:
            sentiments["negative"] += 1
        else:
            sentiments["neutral"] += 1
    
    log.info("板块分布:")
    for s, c in sorted(sectors.items(), key=lambda x: x[1], reverse=True):
        log.info(f"  {s}: {c} 条")
    
    log.info(f"\n情感分布:")
    log.info(f"  利好: {sentiments['positive']} 条")
    log.info(f"  中性: {sentiments['neutral']} 条")
    log.info(f"  利空: {sentiments['negative']} 条")
    
    log.info(f"\n前5条新闻:")
    for news in news_list[:5]:
        icon = "📈" if news['sentiment'] > 0.2 else "📉" if news['sentiment'] < -0.2 else "➡️"
        log.info(f"  [{news['sector']}] {icon} {news['title'][:50]}...")
