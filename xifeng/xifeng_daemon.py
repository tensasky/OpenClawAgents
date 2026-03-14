#!/usr/bin/env python3
"""
xifeng_daemon.py - 西风守护进程
每30分钟自动抓取一次板块热点数据
"""

import os
import sys
import time
import json
import logging
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from multi_source_fetcher import MultiSourceFetcher
from stock_sector_map import SECTOR_LEADING_STOCKS, SECTOR_KEYWORDS
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("西风")


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path(__file__).parent / "logs" / f"xifeng_daemon_{datetime.now():%Y%m%d}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("西风.daemon")

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)


def analyze_sectors(news_list: list) -> dict:
    """分析新闻板块热度"""
    # 板块计数
    sector_counts = {}
    sector_news = {}
    
    for news in news_list:
        title = news.get('title', '')
        content = news.get('content', '')
        text = title + ' ' + content
        
        # 匹配板块关键词
        for sector, keywords in SECTOR_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    if sector not in sector_counts:
                        sector_counts[sector] = 0
                        sector_news[sector] = []
                    
                    sector_counts[sector] += 1
                    if len(sector_news[sector]) < 5:
                        sector_news[sector].append(news)
                    break  # 匹配到一个关键词就跳出
    
    # 计算热度
    hot_spots = []
    for sector, count in sorted(sector_counts.items(), key=lambda x: x[1], reverse=True):
        if count >= 2:  # 至少2条新闻
            # 计算热度分数
            heat_score = min(100, count * 10 + len(SECTOR_LEADING_STOCKS.get(sector, [])) * 2)
            
            hot_spots.append({
                'sector': sector,
                'heat_score': heat_score,
                'level': 'High' if heat_score >= 70 else 'Medium' if heat_score >= 40 else 'Low',
                'news_count': count,
                'today_count': count,
                'top_news': sector_news[sector][:3],
                'leading_stocks': SECTOR_LEADING_STOCKS.get(sector, [])[:5]
            })
    
    return {
        'generated_at': datetime.now().isoformat(),
        'total_news': len(news_list),
        'total_sectors': len(sector_counts),
        'summary': hot_spots[:5],
        'hot_spots': hot_spots[:10]
    }


def run_once():
    """执行一次抓取"""
    logger.info("🌪️ 西风开始抓取...")
    
    try:
        fetcher = MultiSourceFetcher()
        
        # 抓取新闻
        news = fetcher.fetch_all()
        
        if not news:
            logger.warning("未获取到新闻")
            return
        
        logger.info(f"获取 {len(news)} 条新闻")
        
        # 分析板块
        result = analyze_sectors(news)
        
        # 保存结果
        output_file = DATA_DIR / "hot_spots.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✅ 热点分析完成: {len(result['hot_spots'])} 个板块")
        
        # 打印热点
        for spot in result['hot_spots'][:5]:
            logger.info(f"  🔥 {spot['sector']}: {spot['heat_score']}分 ({spot['news_count']}条)")
        
    except Exception as e:
        logger.error(f"抓取失败: {e}")


def main():
    """主循环"""
    logger.info("🌪️ 西风守护进程启动")
    logger.info("每30分钟抓取一次")
    
    # 立即执行一次
    run_once()
    
    # 定时执行
    while True:
        logger.info("等待30分钟...")
        time.sleep(1800)  # 30分钟
        run_once()


if __name__ == '__main__':
    main()
