#!/usr/bin/env python3
"""
西风 - 多数据源新闻抓取
整合：akshare + 直接HTTP + RSS
"""

import akshare as ak
import requests
import feedparser
import json
import time
import random
import re
from datetime import datetime
from typing import List, Dict
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("西风")


# 请求头
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}


class MultiSourceFetcher:
    """多数据源抓取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.last_request = 0
        self.seen_titles = set()  # 用于去重
    
    def _rate_limit(self, delay: float = 1.0):
        """请求限流"""
        elapsed = time.time() - self.last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()
    
    def _add_news(self, title: str, content: str, source: str, url: str = "", time_str: str = "") -> bool:
        """添加新闻，去重，返回是否添加成功"""
        if not title:
            return False
        
        # 标准化标题用于去重
        normalized = re.sub(r'\s+', '', title.lower())
        
        # 检查是否已存在
        for seen in self.seen_titles:
            # 完全相同或是子串关系
            if normalized == seen or normalized in seen or seen in normalized:
                return False
        
        self.seen_titles.add(normalized)
        return True
    
    def fetch_akshare_em(self) -> List[Dict]:
        """东方财富新闻（akshare）"""
        news_list = []
        
        try:
            self._rate_limit(0.5)
            df = ak.stock_news_em()
            
            for _, row in df.head(20).iterrows():
                title = str(row.get('新闻标题', ''))
                if self._add_news(title, "", "东方财富"):
                    news_list.append({
                        'title': title,
                        'content': str(row.get('新闻内容', '')),
                        'source': '东方财富',
                        'url': str(row.get('新闻链接', '')),
                        'time': str(row.get('发布时间', ''))
                    })
            
            log.info(f"  东方财富: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  东方财富失败: {e}")
        
        return news_list
    
    def fetch_akshare_cx(self) -> List[Dict]:
        """财联社新闻（akshare）"""
        news_list = []
        
        try:
            self._rate_limit(0.5)
            df = ak.stock_news_main_cx()
            
            for _, row in df.head(30).iterrows():
                title = str(row.get('标题', ''))
                if title and self._add_news(title, "", "财联社"):
                    news_list.append({
                        'title': title,
                        'content': str(row.get('内容', row.get('summary', ''))),
                        'source': '财联社',
                        'url': str(row.get('链接', '')),
                        'time': str(row.get('时间', ''))
                    })
            
            log.info(f"  财联社: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  财联社失败: {e}")
        
        return news_list
    
    def fetch_sina_finance(self) -> List[Dict]:
        """新浪财经7x24"""
        news_list = []
        
        try:
            self._rate_limit(1.0)
            
            # 新浪财经7x24小时滚动新闻API
            url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&k=&num=30&r=0.5"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'result' in data and 'data' in data['result']:
                for item in data['result']['data']:
                    title = item.get('title', '')
                    if title and self._add_news(title, "", "新浪财经"):
                        news_list.append({
                            'title': title,
                            'content': item.get('summary', ''),
                            'source': '新浪财经',
                            'url': item.get('url', ''),
                            'time': item.get('ctime', '')
                        })
            
            log.info(f"  新浪财经: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  新浪财经失败: {e}")
        
        return news_list
    
    def fetch_xueqiu(self) -> List[Dict]:
        """雪球热帖"""
        news_list = []
        
        try:
            self._rate_limit(1.0)
            
            # 雪球热帖API
            url = "https://xueqiu.com/statuses/hot.json"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'statuses' in data:
                for item in data['statuses'][:20]:
                    title = item.get('title', '') or item.get('description', '')[:50]
                    if title and self._add_news(title, "", "雪球"):
                        news_list.append({
                            'title': title,
                            'content': item.get('description', ''),
                            'source': '雪球',
                            'url': f"https://xueqiu.com{item.get('target', '')}",
                            'time': item.get('created_at', '')
                        })
            
            log.info(f"  雪球: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  雪球失败: {e}")
        
        return news_list
    
    def fetch_tencent(self) -> List[Dict]:
        """腾讯财经"""
        news_list = []
        
        try:
            self._rate_limit(1.0)
            
            # 腾讯财经新闻
            url = "https://i.news.qq.com/trpc.qqnews_web.kv_srv.kv_srv_http_proxy/list"
            params = {
                'sub_srv_id': '24hours',
                'srv_id': 'pc',
                'limit': 30,
                'page': 1
            }
            
            response = self.session.get(url, params=params, timeout=10)
            data = response.json()
            
            if data and 'data' in data and isinstance(data['data'], dict) and 'list' in data['data']:
                for item in data['data']['list']:
                    title = item.get('title', '')
                    if title and self._add_news(title, "", "腾讯财经"):
                        news_list.append({
                            'title': title,
                            'content': item.get('abstract', ''),
                            'source': '腾讯财经',
                            'url': item.get('url', ''),
                            'time': item.get('publish_time', '')
                        })
            
            log.info(f"  腾讯财经: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  腾讯财经失败: {e}")
        
        return news_list
    
    def fetch_10jqka(self) -> List[Dict]:
        """同花顺财经"""
        news_list = []
        
        try:
            self._rate_limit(1.0)
            
            # 同花顺7x24快讯
            url = "http://news.10jqka.com.cn/tapp/news/push/stock/"
            
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            if 'data' in data and 'list' in data['data']:
                for item in data['data']['list']:
                    title = item.get('title', '')
                    if title and self._add_news(title, "", "同花顺"):
                        news_list.append({
                            'title': title,
                            'content': item.get('content', ''),
                            'source': '同花顺',
                            'url': item.get('url', ''),
                            'time': item.get('time', '')
                        })
            
            log.info(f"  同花顺: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"  同花顺失败: {e}")
        
        return news_list
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有数据源"""
        log.info("🌪️ 抓取多源财经新闻...")
        log.info("-" * 60)
        
        all_news = []
        
        # 数据源1: 东方财富
        all_news.extend(self.fetch_akshare_em())
        
        # 数据源2: 财联社
        all_news.extend(self.fetch_akshare_cx())
        
        # 数据源3: 新浪财经
        all_news.extend(self.fetch_sina_finance())
        
        # 数据源4: 雪球
        all_news.extend(self.fetch_xueqiu())
        
        # 数据源5: 腾讯财经
        all_news.extend(self.fetch_tencent())
        
        # 数据源6: 同花顺
        all_news.extend(self.fetch_10jqka())
        
        log.info("-" * 60)
        log.info(f"📊 总计: {len(all_news)} 条（已去重）")
        
        return all_news


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
    "中字头": ["中字头", "央企", "国企", "国资委", "中国", "中铁", "中建", "中石油", "中石化"],
    "有色": ["有色", "铜", "铝", "锌", "镍", "锂", "稀土", "黄金", "白银", "贵金属"],
}


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


def fetch_multi_source_news() -> List[Dict]:
    """获取多源新闻"""
    fetcher = MultiSourceFetcher()
    news_list = fetcher.fetch_all()
    
    # 处理
    for news in news_list:
        text = news['title'] + ' ' + news.get('content', '')
        news['sector'] = identify_sector(text)
        news['sentiment'] = analyze_sentiment(text)
    
    return news_list


if __name__ == '__main__':
    log.info("=" * 60)
    log.info("🌪️ 西风 - 多源财经新闻测试")
    log.info("=" * 60)
    
    news_list = fetch_multi_source_news()
    
    # 统计
    sectors = {}
    sources = {}
    
    for news in news_list:
        s = news.get('sector', '其他')
        sectors[s] = sectors.get(s, 0) + 1
        
        src = news.get('source', '未知')
        sources[src] = sources.get(src, 0) + 1
    
    log.info(f"\n来源分布:")
    for src, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        log.info(f"  {src}: {count} 条")
    
    log.info(f"\n板块分布:")
    for s, c in sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:10]:
        log.info(f"  {s}: {c} 条")
    
    log.info(f"\n前5条新闻:")
    for news in news_list[:5]:
        icon = "📈" if news.get('sentiment', 0) > 0.2 else "📉" if news.get('sentiment', 0) < -0.2 else "➡️"
        log.info(f"  [{news.get('source', '未知')}] [{news.get('sector', '其他')}] {icon}")
        log.info(f"    {news['title'][:60]}...")
        print()
