#!/usr/bin/env python3
"""
西风 Skill - 舆情与热点分析
核心功能：RSS抓取 + LLM提取 + 热度计算
"""

import os
import sys
import json
import sqlite3
import re
import time
import random
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# 导入真实新闻抓取器
from real_news_fetcher import fetch_real_news
from stock_sector_map import get_leading_stocks

# 配置路径
SKILL_DIR = Path(__file__).parent
DATA_DIR = SKILL_DIR / "data"
LOG_DIR = SKILL_DIR / "logs"
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 加载配置
CONFIG_PATH = SKILL_DIR / "config" / "config.json"
if not CONFIG_PATH.exists():
    CONFIG_PATH = SKILL_DIR / "config.json"
with open(CONFIG_PATH) as f:
    CONFIG = json.load(f)


class LLMAnalyzer:
    """LLM语义分析器"""
    
    def __init__(self):
        llm_config = CONFIG.get('llm', {})
        self.model = llm_config.get('model', 'moonshot/kimi-k2.5')
        self.temperature = llm_config.get('temperature', 0.3)
    
    def analyze_news(self, title: str, content: str = "") -> Dict:
        """
        使用LLM分析新闻，提取板块和关键词
        
        返回: {
            "sector": "板块名称",
            "keywords": ["关键词1", "关键词2"],
            "sentiment": 0.5,  # -1到1
            "summary": "摘要"
        }
        """
        # 构建prompt
        prompt = f"""分析以下财经新闻，提取信息：

标题：{title}
内容：{content[:200] if content else title}

请用JSON格式返回：
{{
    "sector": "涉及的板块/概念（如：人工智能、新能源、房地产等）",
    "keywords": ["关键词1", "关键词2", "关键词3"],
    "sentiment": 0.5,  // 情感得分：-1(利空)到+1(利好)
    "summary": "一句话摘要"
}}

只返回JSON，不要其他内容。"""

        try:
            # 调用OpenClaw的LLM（通过环境变量或本地API）
            result = self._call_llm(prompt)
            
            # 解析JSON
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                analysis = json.loads(json_match.group())
                return {
                    "sector": analysis.get("sector", "其他"),
                    "keywords": analysis.get("keywords", []),
                    "sentiment": float(analysis.get("sentiment", 0)),
                    "summary": analysis.get("summary", "")
                }
            
        except Exception as e:
            print(f"LLM分析失败: {e}")
        
        # 失败时返回默认值
        return {
            "sector": "其他",
            "keywords": [],
            "sentiment": 0.0,
            "summary": ""
        }
    
    def _call_llm(self, prompt: str) -> str:
        """调用LLM API"""
        # 这里使用OpenClaw的本地接口
        # 实际部署时可以通过openclaw的agent调用
        
        # 简化版本：使用关键词匹配（演示）
        return self._fallback_analysis(prompt)
    
    def _fallback_analysis(self, prompt: str) -> str:
        """备用分析（关键词匹配）"""
        text = prompt.lower()
        
        # 板块关键词
        sectors = {
            "人工智能": ["ai", "人工智能", "大模型", "chatgpt", "算力", "芯片"],
            "新能源": ["新能源", "光伏", "风电", "储能", "锂电池"],
            "机器人": ["机器人", "人形机器人", "减速器"],
            "半导体": ["半导体", "芯片", "光刻机", "国产替代"],
            "医药": ["医药", "创新药", "cxo", "医疗器械"],
            "房地产": ["房地产", "楼市", "房价", "地产"],
            "金融": ["银行", "保险", "券商", "央行", "降息"],
            "汽车": ["汽车", "新能源", "比亚迪", "特斯拉"],
        }
        
        # 匹配板块
        matched_sector = "其他"
        max_score = 0
        for sector, keywords in sectors.items():
            score = sum(1 for k in keywords if k in text)
            if score > max_score:
                max_score = score
                matched_sector = sector
        
        # 情感分析
        positive = ['上涨', '利好', '突破', '增长', '涨停', '创新高']
        negative = ['下跌', '利空', '跌破', '亏损', '跌停', '风险']
        
        sentiment = 0.0
        for p in positive:
            if p in text:
                sentiment += 0.3
        for n in negative:
            if n in text:
                sentiment -= 0.3
        
        sentiment = max(-1.0, min(1.0, sentiment))
        
        return json.dumps({
            "sector": matched_sector,
            "keywords": [matched_sector] if matched_sector != "其他" else [],
            "sentiment": sentiment,
            "summary": ""
        }, ensure_ascii=False)


class RSSFetcher:
    """RSS/快讯抓取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_request = 0
    
    def _rate_limit(self, delay: float = 1.0):
        """请求限流"""
        elapsed = time.time() - self.last_request
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request = time.time()
    
    def fetch_cls_telegraph(self) -> List[Dict]:
        """抓取财联社电报"""
        url = "https://www.cls.cn/api/telegraph"
        
        try:
            self._rate_limit()
            
            headers = {
                'Referer': 'https://www.cls.cn/telegraph',
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            }
            
            resp = self.session.get(url, headers=headers, timeout=10)
            data = resp.json()
            
            news_list = []
            if 'data' in data and 'roll_data' in data['data']:
                for item in data['data']['roll_data'][:30]:
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
    
    def fetch_mock_news(self, count: int = 50) -> List[Dict]:
        """生成模拟新闻（演示用）"""
        sectors = ["人工智能", "新能源", "机器人", "半导体", "医药", "房地产", "金融", "汽车"]
        templates = [
            "{sector}板块今日大涨，相关政策出台",
            "{sector}龙头企业发布利好公告",
            "机构看好{sector}板块投资机会",
            "{sector}概念股异动，资金流入明显",
            "政策利好{sector}，行业迎来新机遇"
        ]
        
        news_list = []
        for i in range(count):
            sector = random.choice(sectors)
            template = random.choice(templates)
            title = template.format(sector=sector)
            
            news_list.append({
                'title': title,
                'content': title + '。相关个股表现活跃。',
                'source': '财联社',
                'url': f'https://example.com/{i}',
                'time': datetime.now().isoformat()
            })
        
        return news_list
    
    def fetch_all(self) -> List[Dict]:
        """抓取所有源"""
        # 使用真实新闻抓取器
        all_news = fetch_real_news()
        print(f"  真实财经新闻: {len(all_news)} 条")
        return all_news


class HeatCalculator:
    """热度计算器"""
    
    def __init__(self):
        self.db_path = DATA_DIR / "xifeng.db"
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY,
                title TEXT,
                sector TEXT,
                keywords TEXT,
                sentiment REAL,
                time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sector_daily (
                sector TEXT,
                date TEXT,
                count INTEGER DEFAULT 0,
                avg_sentiment REAL DEFAULT 0,
                PRIMARY KEY (sector, date)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_news(self, news: Dict, analysis: Dict):
        """保存新闻"""
        conn = sqlite3.connect(self.db_path)
        
        conn.execute(
            """INSERT INTO news (title, sector, keywords, sentiment, time)
               VALUES (?, ?, ?, ?, ?)""",
            (news['title'], analysis['sector'], 
             json.dumps(analysis['keywords'], ensure_ascii=False),
             analysis['sentiment'], news.get('time', datetime.now().isoformat()))
        )
        
        conn.commit()
        conn.close()
    
    def get_historical_count(self, sector: str, days: int = 15) -> float:
        """获取历史平均提及次数"""
        conn = sqlite3.connect(self.db_path)
        
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        cursor = conn.execute(
            """SELECT AVG(count) FROM sector_daily 
               WHERE sector=? AND date >= ?""",
            (sector, start_date)
        )
        
        result = cursor.fetchone()[0]
        conn.close()
        
        return result or 1.0
    
    def update_daily_stats(self, sector: str, count: int, sentiment: float):
        """更新每日统计"""
        conn = sqlite3.connect(self.db_path)
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        conn.execute(
            """INSERT OR REPLACE INTO sector_daily (sector, date, count, avg_sentiment)
               VALUES (?, ?, ?, ?)""",
            (sector, today, count, sentiment)
        )
        
        conn.commit()
        conn.close()
    
    def calculate_heat(self, sector: str, today_count: int, sentiment: float) -> Dict:
        """
        计算热度评分
        Heat = 0.3 * frequency + 0.5 * momentum + 0.2 * sentiment
        """
        # 获取15天历史平均
        avg_count = self.get_historical_count(sector, days=15)
        
        # 计算动量（爆发系数）
        momentum = today_count / avg_count if avg_count > 0 else 1.0
        
        # 标准化分数 (0-100)
        freq_score = min(today_count * 2, 100)  # 频率分
        momentum_score = min(momentum * 20, 100)  # 动量分（爆发系数×20）
        sentiment_score = (sentiment + 1) * 50  # 情感分映射到0-100
        
        # 综合评分
        heat_score = (
            0.3 * freq_score +
            0.5 * momentum_score +
            0.2 * sentiment_score
        )
        
        heat_score = max(0, min(100, heat_score))
        
        # 分级
        heat_config = CONFIG.get('heat_threshold', {'high': 80, 'medium': 40})
        high_threshold = heat_config.get('high', 80)
        medium_threshold = heat_config.get('medium', 40)
        
        if heat_score >= high_threshold:
            level = "High"
        elif heat_score >= medium_threshold:
            level = "Medium"
        else:
            level = "Low"
        
        return {
            "sector": sector,
            "heat_score": round(heat_score, 1),
            "level": level,
            "today_count": today_count,
            "avg_count": round(avg_count, 1),
            "momentum": round(momentum, 2),
            "sentiment": round(sentiment, 2),
            "breakout_coefficient": round(momentum, 2)  # 爆发系数
        }


class XiFengSkill:
    """西风 Skill 主类"""
    
    def __init__(self):
        self.fetcher = RSSFetcher()
        self.analyzer = LLMAnalyzer()
        self.calculator = HeatCalculator()
    
    def analyze(self):
        """执行完整分析流程"""
        print("=" * 60)
        print("🌪️ 西风 Skill - 舆情热点分析")
        print("=" * 60)
        print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        # 1. 抓取新闻
        print("📰 Step 1: 抓取财联社快讯...")
        news_list = self.fetcher.fetch_all()
        print(f"   获取 {len(news_list)} 条新闻\n")
        
        # 2. LLM分析
        print("🧠 Step 2: LLM语义分析...")
        analyzed_news = []
        for i, news in enumerate(news_list, 1):
            analysis = self.analyzer.analyze_news(news['title'], news.get('content', ''))
            analyzed_news.append({
                'news': news,
                'analysis': analysis
            })
            
            # 保存到数据库
            self.calculator.save_news(news, analysis)
            
            if i <= 5:  # 只显示前5条
                print(f"   [{analysis['sector']}] {news['title'][:40]}...")
        
        if len(news_list) > 5:
            print(f"   ... 还有 {len(news_list)-5} 条")
        print()
        
        # 3. 统计板块
        print("📊 Step 3: 统计板块词频...")
        sector_stats = {}
        for item in analyzed_news:
            sector = item['analysis']['sector']
            sentiment = item['analysis']['sentiment']
            
            if sector not in sector_stats:
                sector_stats[sector] = {'count': 0, 'sentiment_sum': 0}
            
            sector_stats[sector]['count'] += 1
            sector_stats[sector]['sentiment_sum'] += sentiment
        
        print(f"   识别 {len(sector_stats)} 个板块\n")
        
        # 4. 计算热度
        print("🔥 Step 4: 计算热度评分...")
        hot_spots = []
        
        for sector, stats in sector_stats.items():
            count = stats['count']
            avg_sentiment = stats['sentiment_sum'] / count if count > 0 else 0
            
            # 更新每日统计
            self.calculator.update_daily_stats(sector, count, avg_sentiment)
            
            # 计算热度
            heat = self.calculator.calculate_heat(sector, count, avg_sentiment)
            hot_spots.append(heat)
        
        # 按热度排序
        hot_spots.sort(key=lambda x: x['heat_score'], reverse=True)
        
        # 显示结果
        for spot in hot_spots[:10]:
            icon = "🔥" if spot['level'] == "High" else "📈" if spot['level'] == "Medium" else "📉"
            print(f"   {icon} {spot['sector']}: {spot['heat_score']} ({spot['level']})")
            print(f"      今日{spot['today_count']}次 | 爆发系数{spot['momentum']}x | 情感{spot['sentiment']:+.1f}")
        print()
        
        # 5. 生成核心汇总
        print("📋 Step 5: 生成核心汇总...")
        
        # 获取热门新闻（按板块分组）
        sector_news = {}
        for item in analyzed_news:
            sector = item['analysis']['sector']
            if sector not in sector_news:
                sector_news[sector] = []
            sector_news[sector].append(item['news'])
        
        # 为每个热点板块生成汇总
        summary = []
        for spot in hot_spots[:5]:  # 前5个板块
            sector = spot['sector']
            news_list_sector = sector_news.get(sector, [])
            
            # 获取该板块热门新闻（前3条）
            top_news = news_list_sector[:3] if news_list_sector else []
            
            # 获取龙头股
            leading_stocks = get_leading_stocks(sector, 3)
            
            summary_item = {
                "sector": sector,
                "heat_score": spot['heat_score'],
                "level": spot['level'],
                "today_count": spot['today_count'],
                "sentiment": spot['sentiment'],
                "top_news": [
                    {
                        "title": n['title'][:80],
                        "source": n.get('source', '未知'),
                        "sentiment": "📈" if n.get('sentiment', 0) > 0.2 else "📉" if n.get('sentiment', 0) < -0.2 else "➡️"
                    } for n in top_news
                ],
                "leading_stocks": [
                    {
                        "code": s['code'],
                        "name": s['name'],
                        "weight": s['weight']
                    } for s in leading_stocks
                ]
            }
            summary.append(summary_item)
        
        # 6. 导出结果
        print("💾 Step 6: 导出结果...")
        output = {
            "generated_at": datetime.now().isoformat(),
            "total_sectors": len(hot_spots),
            "summary": summary,
            "hot_spots": hot_spots
        }
        
        output_file = DATA_DIR / "hot_spots.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        print(f"   已保存: {output_file}")
        print(f"   板块数: {len(hot_spots)}")
        print()
        
        # 显示核心汇总
        print("=" * 60)
        print("📊 核心汇总")
        print("=" * 60)
        for item in summary:
            icon = "🔥" if item['level'] == "High" else "📈" if item['level'] == "Medium" else "📉"
            print(f"\n{icon} {item['sector']} (热度: {item['heat_score']})")
            print(f"   提及: {item['today_count']}次 | 情感: {item['sentiment']:+.2f}")
            
            print(f"   热门新闻:")
            for news in item['top_news']:
                print(f"     {news['sentiment']} {news['title']}... ({news['source']})")
            
            print(f"   影响股票:")
            for stock in item['leading_stocks']:
                print(f"     • {stock['code']} {stock['name']} (权重{stock['weight']})")
        
        print("\n" + "=" * 60)
        
        # 总结
        high_count = sum(1 for s in hot_spots if s['level'] == "High")
        medium_count = sum(1 for s in hot_spots if s['level'] == "Medium")
        
        print("📋 统计")
        print("=" * 60)
        print(f"   新闻总数: {len(news_list)}")
        print(f"   热点板块: {high_count} 个 🔥")
        print(f"   中热板块: {medium_count} 个 📈")
        print(f"   总板块数: {len(hot_spots)}")
        print("=" * 60)
        
        return True


def main():
    """命令行入口"""
    skill = XiFengSkill()
    skill.analyze()


if __name__ == '__main__':
    main()
