#!/usr/bin/env python3
"""
西风 - 真实财经新闻抓取模块
使用 akshare 获取实时数据
"""

import akshare as ak
import json
import time
from datetime import datetime
from typing import List, Dict

# 板块关键词映射（扩展版）
SECTOR_KEYWORDS = {
    "人工智能": ["AI", "人工智能", "大模型", "ChatGPT", "算力", "芯片", "GPU", "OpenAI", "百度文心", "通义千问", "讯飞星火", "智谱"],
    "低空经济": ["低空经济", "飞行汽车", "eVTOL", "无人机", "通航", "航空", "飞行器", "亿航", "小鹏汇天"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电池", "宁德时代", "比亚迪", "锂电", "氢能", "充电桩", "光伏组件"],
    "机器人": ["机器人", "人形机器人", "工业机器人", "减速器", "伺服电机", "特斯拉机器人", "Optimus", "波士顿动力", "谐波减速器"],
    "半导体": ["半导体", "芯片", "光刻机", "晶圆", "EDA", "国产替代", "集成电路", "中芯国际", "华为芯片", "先进制程"],
    "医药": ["医药", "创新药", "CXO", "医疗器械", "生物制药", "疫苗", "医保", "集采", "减肥药", "GLP-1", "CRO"],
    "房地产": ["房地产", "楼市", "房价", "地产", "住建部", "房企", "商品房", "房贷", "LPR", "限购", "松绑"],
    "金融": ["银行", "保险", "券商", "金融", "央行", "降息", "降准", "证监会", "汇金", "金融监管", "信贷"],
    "消费": ["消费", "零售", "白酒", "食品饮料", "免税", "茅台", "五粮液", "餐饮", "旅游", "酒店", "预制菜"],
    "汽车": ["汽车", "新能源汽车", "比亚迪", "特斯拉", "自动驾驶", "电动车", "小米汽车", "华为汽车", "理想", "蔚来"],
    "中字头": ["中字头", "央企", "国企", "国资委", "中国", "中铁", "中建", "中石油", "中石化", "中国移动", "中国联通"],
    "游戏": ["游戏", "网游", "手游", "版号", "腾讯游戏", "网易游戏", "原神", "王者荣耀", "黑神话"],
    "传媒": ["传媒", "影视", "电影", "票房", "短视频", "抖音", "快手", "B站", "爱奇艺"],
    "有色": ["有色", "铜", "铝", "锌", "镍", "锂", "稀土", "黄金", "白银", "贵金属", "大宗商品"],
    "化工": ["化工", "化纤", "塑料", "橡胶", "PVC", "MDI", "钛白粉", "农药", "化肥"],
}


class RealNewsFetcher:
    """真实新闻抓取器"""
    
    def __init__(self):
        self.last_request = 0
    
    def _rate_limit(self, delay: float = 0.5):
        """请求限流"""
        import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("西风")

        elapsed = time.time() - self.last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()
    
    def fetch_akshare_news(self, source: str = "em") -> List[Dict]:
        """使用 akshare 抓取新闻"""
        news_list = []
        
        try:
            self._rate_limit()
            
            if source == "em":
                # 东方财富新闻
                df = ak.stock_news_em()
                for _, row in df.iterrows():
                    news_list.append({
                        'title': str(row.get('新闻标题', '')),
                        'content': str(row.get('新闻内容', '')),
                        'source': '东方财富',
                        'url': str(row.get('新闻链接', '')),
                        'time': str(row.get('发布时间', '')),
                        'keywords': str(row.get('关键词', ''))
                    })
            
            log.info(f"  东方财富: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"东方财富新闻失败: {e}")
        
        try:
            self._rate_limit()
            
            # 财联社新闻
            df = ak.stock_news_main_cx()
            for _, row in df.iterrows():
                news_list.append({
                    'title': str(row.get('标题', '')),
                    'content': str(row.get('内容', row.get('summary', ''))),
                    'source': '财联社',
                    'url': str(row.get('链接', '')),
                    'time': str(row.get('时间', datetime.now().isoformat()))
                })
            
            log.info(f"  财联社: {len(news_list)} 条")
            
        except Exception as e:
            log.info(f"财联社新闻失败: {e}")
        
        return news_list
    
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
                   '支持', '大涨', '强势', '超预期', '净利润增长', '订单增长', '中标', '增持']
        negative = ['下跌', '利空', '跌破', '亏损', '暴雷', '跌停', '监管', '处罚', 
                   '风险', '大跌', '弱势', '不及预期', '净利润下滑', '裁员', '减持', '退市']
        
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
        """抓取所有新闻"""
        log.info("🌪️ 抓取真实财经新闻...")
        
        news_list = self.fetch_akshare_news()
        
        # 处理
        for news in news_list:
            text = news['title'] + ' ' + news.get('content', '')
            news['sector'] = self.identify_sector(text)
            news['sentiment'] = self.analyze_sentiment(text)
        
        return news_list


def fetch_real_news(count: int = 100) -> List[Dict]:
    """获取真实新闻"""
    fetcher = RealNewsFetcher()
    return fetcher.fetch_all()


if __name__ == '__main__':
    log.info("=" * 60)
    log.info("🌪️ 西风 - 真实财经新闻测试")
    log.info("=" * 60)
    
    news_list = fetch_real_news()
    
    log.info(f"\n📊 总计: {len(news_list)} 条")
    
    # 统计
    sectors = {}
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    
    for news in news_list:
        s = news.get('sector', '其他')
        sectors[s] = sectors.get(s, 0) + 1
        
        if news.get('sentiment', 0) > 0.2:
            sentiments["positive"] += 1
        elif news.get('sentiment', 0) < -0.2:
            sentiments["negative"] += 1
        else:
            sentiments["neutral"] += 1
    
    log.info("\n板块分布:")
    for s, c in sorted(sectors.items(), key=lambda x: x[1], reverse=True)[:10]:
        log.info(f"  {s}: {c} 条")
    
    log.info(f"\n情感分布:")
    log.info(f"  利好: {sentiments['positive']} 条")
    log.info(f"  中性: {sentiments['neutral']} 条")
    log.info(f"  利空: {sentiments['negative']} 条")
    
    log.info(f"\n前5条新闻:")
    for news in news_list[:5]:
        icon = "📈" if news.get('sentiment', 0) > 0.2 else "📉" if news.get('sentiment', 0) < -0.2 else "➡️"
        log.info(f"  [{news.get('sector', '其他')}] {icon} {news['title'][:60]}...")
