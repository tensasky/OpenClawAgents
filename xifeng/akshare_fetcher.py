#!/usr/bin/env python3
"""
西风 - 使用 akshare 获取真实财经新闻
"""

import akshare as ak
import json
import time
from datetime import datetime
from typing import List, Dict

# 板块关键词映射
SECTOR_KEYWORDS = {
    "人工智能": ["AI", "人工智能", "大模型", "ChatGPT", "算力", "芯片", "GPU", "OpenAI", "百度文心", "通义千问"],
    "低空经济": ["低空经济", "飞行汽车", "eVTOL", "无人机", "通航", "航空", "飞行器"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电池", "宁德时代", "比亚迪", "锂电", "氢能"],
    "机器人": ["机器人", "人形机器人", "工业机器人", "减速器", "伺服电机", "特斯拉机器人"],
    "半导体": ["半导体", "芯片", "光刻机", "晶圆", "EDA", "国产替代", "集成电路", "中芯国际"],
    "医药": ["医药", "创新药", "CXO", "医疗器械", "生物制药", "疫苗", "医保", "集采", "减肥药"],
    "房地产": ["房地产", "楼市", "房价", "地产", "住建部", "房企", "商品房", "房贷", "LPR"],
    "金融": ["银行", "保险", "券商", "金融", "央行", "降息", "降准", "证监会", "汇金"],
    "消费": ["消费", "零售", "白酒", "食品饮料", "免税", "茅台", "五粮液", "餐饮", "旅游"],
    "汽车": ["汽车", "新能源汽车", "比亚迪", "特斯拉", "自动驾驶", "电动车", "小米汽车"],
}


def fetch_akshare_news() -> List[Dict]:
    """使用 akshare 获取财经新闻"""
    news_list = []
    
    try:
        # 东方财富财经新闻
        df = ak.stock_zh_a_new()
        
        for _, row in df.head(30).iterrows():
            news_list.append({
                'title': str(row.get('title', '')),
                'content': str(row.get('content', '')),
                'source': '东方财富',
                'url': str(row.get('url', '')),
                'time': str(row.get('datetime', '')),
            })
        
        print(f"  东方财富: {len(news_list)} 条")
        
    except Exception as e:
        print(f"东方财富新闻失败: {e}")
    
    try:
        # 新浪财经新闻
        df = ak.stock_news_em()
        
        for _, row in df.head(30).iterrows():
            news_list.append({
                'title': str(row.get('title', '')),
                'content': str(row.get('content', '')),
                'source': '新浪财经',
                'url': str(row.get('url', '')),
                'time': str(row.get('datetime', '')),
            })
        
        print(f"  新浪财经: {len(news_list)} 条")
        
    except Exception as e:
        print(f"新浪财经失败: {e}")
    
    return news_list


def identify_sector(text: str) -> str:
    """识别板块"""
    if not text:
        return "其他"
    
    text = text.lower()
    scores = {}
    
    for sector, keywords in SECTOR_KEYWORDS.items():
        score = sum(1 for k in keywords if k.lower() in text)
        if score > 0:
            scores[sector] = score
    
    if scores:
        return max(scores, key=scores.get)
    
    return "其他"


def analyze_sentiment(text: str) -> float:
    """情感分析"""
    if not text:
        return 0.0
    
    positive = ['上涨', '利好', '突破', '增长', '盈利', '创新高', '涨停', '政策扶持', 
               '支持', '大涨', '强势', '超预期', '净利润增长']
    negative = ['下跌', '利空', '跌破', '亏损', '暴雷', '跌停', '监管', '处罚', 
               '风险', '大跌', '弱势', '不及预期', '净利润下滑']
    
    score = 0.0
    text_lower = text.lower()
    
    for p in positive:
        if p in text_lower:
            score += 0.25
    
    for n in negative:
        if n in text_lower:
            score -= 0.25
    
    return max(-1.0, min(1.0, score))


def fetch_all() -> List[Dict]:
    """抓取所有新闻"""
    print("🌪️ 抓取真实财经新闻...")
    
    news_list = fetch_akshare_news()
    
    # 处理
    for news in news_list:
        text = news['title'] + ' ' + news.get('content', '')
        news['sector'] = identify_sector(text)
        news['sentiment'] = analyze_sentiment(text)
    
    return news_list


if __name__ == '__main__':
    print("=" * 60)
    print("🌪️ 西风 - 真实财经新闻测试")
    print("=" * 60)
    
    news_list = fetch_all()
    
    print(f"\n📊 总计: {len(news_list)} 条")
    
    # 统计
    sectors = {}
    for news in news_list:
        s = news.get('sector', '其他')
        sectors[s] = sectors.get(s, 0) + 1
    
    print(f"\n板块分布:")
    for s, c in sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"  {s}: {c}")
    
    print(f"\n前5条:")
    for news in news_list[:5]:
        icon = "📈" if news.get('sentiment', 0) > 0 else "📉" if news.get('sentiment', 0) < 0 else "➡️"
        print(f"  [{news.get('sector', '其他')}] {icon} {news['title'][:50]}...")
