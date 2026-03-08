#!/usr/bin/env python3
"""
西风 - 真实 RSS 抓取模块
支持：财联社、东方财富、新浪财经
"""

import requests
import feedparser
import json
import re
import time
import random
from datetime import datetime
from typing import List, Dict
from pathlib import Path

# RSS 源配置
RSS_FEEDS = {
    "新浪财经": {
        "url": "https://finance.sina.com.cn/stock/",
        "rss": "https://rss.sina.com.cn/roll/finance/hot_roll.xml",
        "type": "rss"
    },
    "东方财富": {
        "url": "https://finance.eastmoney.com/a/cywjh.html",
        "api": "https://np-anotice-stock.eastmoney.com/api/security/ann",
        "type": "api"
    },
    "财联社": {
        "url": "https://www.cls.cn/telegraph",
        "api": "https://www.cls.cn/api/telegraph",
        "headers": {
            'Referer': 'https://www.cls.cn/telegraph',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        },
        "type": "api"
    }
}

# 板块关键词（扩展版）
SECTOR_KEYWORDS = {
    "人工智能": ["AI", "人工智能", "大模型", "ChatGPT", "算力", "芯片", "GPU", "OpenAI", "百度文心", "通义千问", "讯飞星火"],
    "低空经济": ["低空经济", "飞行汽车", "eVTOL", "无人机", "通航", "航空", "飞行器", "亿航", "小鹏汇天"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电池", "宁德时代", "比亚迪", "锂电", "氢能", "充电桩"],
    "机器人": ["机器人", "人形机器人", "工业机器人", "减速器", "伺服电机", "特斯拉机器人", "Optimus", "波士顿动力"],
    "半导体": ["半导体", "芯片", "光刻机", "晶圆", "EDA", "国产替代", "集成电路", "中芯国际", "华为芯片"],
    "医药": ["医药", "创新药", "CXO", "医疗器械", "生物制药", "疫苗", "医保", "集采", "减肥药", "GLP-1"],
    "房地产": ["房地产", "楼市", "房价", "地产", "住建部", "房企", "商品房", "房贷", "限购", "LPR"],
    "金融": ["银行", "保险", "券商", "金融", "央行", "降息", "降准", "证监会", "银保监会", "汇金"],
    "消费": ["消费", "零售", "白酒", "食品饮料", "免税", "茅台", "五粮液", "餐饮", "旅游", "酒店"],
    "汽车": ["汽车", "新能源汽车", "比亚迪", "特斯拉", "自动驾驶", "电动车", "锂电池", "充电桩", "小米汽车", "华为汽车"],
    "中字头": ["中字头", "央企", "国企", "国资委", "中国", "中铁", "中建", "中石油", "中石化", "中国移动"],
    "游戏": ["游戏", "网游", "手游", "版号", "腾讯游戏", "网易游戏", "原神", "王者荣耀"],
    "传媒": ["传媒", "影视", "电影", "票房", "短视频", "抖音", "快手", "B站"],
}


class RealRSSFetcher:
    """真实 RSS 抓取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.last_request = 0
    
    def _rate_limit(self, delay: float = 1.0):
        """请求限流"""
        elapsed = time.time() - self.last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()
    
    def fetch_sina_rss(self) -> List[Dict]:
        """抓取新浪财经 RSS"""
        config = RSS_FEEDS["新浪财经"]
        
        try:
            self._rate_limit(1.0)
            
            feed = feedparser.parse(config["rss"])
            
            news_list = []
            for entry in feed.entries[:50]:
                news_list.append({
                    'title': entry.get('title', ''),
                    'content': entry.get('summary', ''),
                    'source': '新浪财经',
                    'url': entry.get('link', ''),
                    'time': entry.get('published', ''),
                })
            
            return news_list
            
        except Exception as e:
            print(f"新浪财经 RSS 失败: {e}")
            return []
    
    def fetch_cls(self) -> List[Dict]:
        """抓取财联社电报"""
        config = RSS_FEEDS["财联社"]
        
        try:
            self._rate_limit(1.5)
            
            resp = self.session.get(
                config["api"], 
                headers=config["headers"], 
                timeout=15
            )
            
            if resp.status_code != 200:
                print(f"财联社 HTTP {resp.status_code}")
                return []
            
            data = resp.json()
            
            news_list = []
            if 'data' in data and 'roll_data' in data['data']:
                for item in data['data']['roll_data'][:50]:
                    news_list.append({
                        'title': item.get('title', ''),
                        'content': item.get('content', ''),
                        'source': '财联社',
                        'url': f"https://www.cls.cn/detail/{item.get('id', '')}",
                        'time': item.get('ctime', ''),
                    })
            
            return news_list
            
        except Exception as e:
            print(f"财联社抓取失败: {e}")
            return []
    
    def fetch_eastmoney(self) -> List[Dict]:
        """抓取东方财富公告"""
        config = RSS_FEEDS["东方财富"]
        
        try:
            self._rate_limit(1.5)
            
            params = {
                'page_size': 50,
                'page_index': 1
            }
            
            resp = self.session.get(
                config["api"],
                params=params,
                headers=config["headers"],
                timeout=15
            )
            
            if resp.status_code != 200:
                print(f"东方财富 HTTP {resp.status_code}")
                return []
            
            data = resp.json()
            
            news_list = []
            if 'data' in data and 'list' in data['data']:
                for item in data['data']['list']:
                    title = item.get('art_title', '') or item.get('notice_title', '')
                    if title:
                        news_list.append({
                            'title': title,
                            'content': item.get('art_content', '') or item.get('notice_content', ''),
                            'source': '东方财富',
                            'url': item.get('art_url', '') or item.get('url', ''),
                            'time': item.get('art_time', '') or item.get('notice_time', ''),
                        })
            
            return news_list
            
        except Exception as e:
            print(f"东方财富抓取失败: {e}")
            return []
    
    def identify_sector(self, text: str) -> str:
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
    
    def analyze_sentiment(self, text: str) -> float:
        """情感分析"""
        if not text:
            return 0.0
        
        positive = ['上涨', '利好', '突破', '增长', '盈利', '创新高', '涨停', '政策扶持', 
                   '支持', '大涨', '强势', '超预期', '净利润增长', '订单增长', '中标']
        negative = ['下跌', '利空', '跌破', '亏损', '暴雷', '跌停', '监管', '处罚', 
                   '风险', '大跌', '弱势', '不及预期', '净利润下滑', '裁员', '退市']
        
        score = 0.0
        text_lower = text.lower()
        
        for p in positive:
            if p in text_lower:
                score += 0.25
        
        for n in negative:
            if n in text_lower:
                score -= 0.25
        
        return max(-1.0, min(1.0, score))
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有源"""
        all_news = []
        
        # 新浪财经 RSS (最稳定)
        sina_news = self.fetch_sina_rss()
        print(f"  新浪财经: {len(sina_news)} 条")
        all_news.extend(sina_news)
        
        # 财联社
        cls_news = self.fetch_cls()
        if cls_news:
            print(f"  财联社: {len(cls_news)} 条")
            all_news.extend(cls_news)
        
        # 东方财富
        em_news = self.fetch_eastmoney()
        if em_news:
            print(f"  东方财富: {len(em_news)} 条")
            all_news.extend(em_news)
        
        # 处理
        for news in all_news:
            text = news['title'] + ' ' + news.get('content', '')
            news['sector'] = self.identify_sector(text)
            news['sentiment'] = self.analyze_sentiment(text)
        
        return all_news


if __name__ == '__main__':
    print("🌪️ 西风 RSS 抓取测试")
    print("=" * 60)
    
    fetcher = RealRSSFetcher()
    news_list = fetcher.fetch_all()
    
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
