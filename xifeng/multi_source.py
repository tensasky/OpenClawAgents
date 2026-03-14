#!/usr/bin/env python3
"""
西风多数据源扩展
增加同花顺、雪球、财联社等数据源
"""

import json
import logging
import requests
from datetime import datetime
from pathlib import Path
import akshare as ak
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("西风")


# 配置
DATA_DIR = Path.home() / "Documents/OpenClawAgents/xifeng/data"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/xifeng/logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"multi_source_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("西风多数据源")


class MultiSourceFetcher:
    """多数据源获取器"""
    
    def __init__(self):
        self.hot_spots = {}
        self.all_news = []
    
    def fetch_from_akshare(self):
        """从akshare获取新闻"""
        logger.info("从akshare获取新闻...")
        
        try:
            # 获取财经新闻
            df = ak.stock_news_em()
            if df is not None and not df.empty:
                for _, row in df.head(50).iterrows():
                    self.all_news.append({
                        'title': row.get('标题', ''),
                        'content': row.get('内容', '')[:200],  # 摘要
                        'source': '东方财富',
                        'url': row.get('链接', ''),
                        'time': str(row.get('发布时间', '')),
                        'stock_code': row.get('代码', '')
                    })
                logger.info(f"  获取 {len(df)} 条东方财富新闻")
        except Exception as e:
            logger.error(f"获取东方财富新闻失败: {e}")
        
        try:
            # 获取龙虎榜数据（热点线索）
            df = ak.stock_lhb_detail_daily_sina()
            if df is not None and not df.empty:
                logger.info(f"  获取 {len(df)} 条龙虎榜数据")
        except Exception as e:
            logger.error(f"获取龙虎榜失败: {e}")
    
    def fetch_from_ths(self):
        """从同花顺获取热点"""
        logger.info("从同花顺获取热点...")
        
        try:
            # 获取同花顺热点板块
            df = ak.stock_board_concept_name_ths()
            if df is not None and not df.empty:
                for _, row in df.head(20).iterrows():
                    sector_name = row.get('概念名称', '')
                    if sector_name:
                        if sector_name not in self.hot_spots:
                            self.hot_spots[sector_name] = {
                                'source': '同花顺',
                                'heat_score': 50,
                                'stocks': []
                            }
                        
                        # 获取该板块的成分股
                        try:
                            stocks_df = ak.stock_board_concept_cons_ths(symbol=sector_name)
                            if stocks_df is not None:
                                stocks = []
                                for _, srow in stocks_df.head(10).iterrows():
                                    stocks.append({
                                        'code': srow.get('代码', ''),
                                        'name': srow.get('名称', '')
                                    })
                                self.hot_spots[sector_name]['stocks'] = stocks
                        except:
                            pass
                
                logger.info(f"  获取 {len(df)} 个同花顺板块")
        except Exception as e:
            logger.error(f"获取同花顺热点失败: {e}")
    
    def fetch_market_sentiment(self):
        """获取市场情绪数据"""
        logger.info("获取市场情绪数据...")
        
        try:
            # 获取涨停股（情绪指标）
            df = ak.stock_zt_pool_em(date=datetime.now().strftime('%Y%m%d'))
            if df is not None and not df.empty:
                zt_count = len(df)
                logger.info(f"  今日涨停: {zt_count} 只")
                
                # 添加到热点
                self.hot_spots['涨停概念'] = {
                    'source': '市场情绪',
                    'heat_score': min(100, 50 + zt_count),
                    'stocks': [{'code': row.get('代码', ''), 'name': row.get('名称', '')} 
                              for _, row in df.head(20).iterrows()]
                }
        except Exception as e:
            logger.error(f"获取涨停数据失败: {e}")
        
        try:
            # 获取跌停股
            df = ak.stock_zt_pool_dtgc_em(date=datetime.now().strftime('%Y%m%d'))
            if df is not None and not df.empty:
                dt_count = len(df)
                logger.info(f"  今日跌停: {dt_count} 只")
        except Exception as e:
            logger.error(f"获取跌停数据失败: {e}")
    
    def merge_and_save(self):
        """合并数据并保存"""
        logger.info("合并数据...")
        
        # 转换为hot_spots.json格式
        hot_spots_list = []
        for sector_name, data in self.hot_spots.items():
            hot_spots_list.append({
                'sector': sector_name,
                'heat_score': data.get('heat_score', 50),
                'level': 'High' if data.get('heat_score', 0) > 70 else 'Medium' if data.get('heat_score', 0) > 40 else 'Low',
                'news_count': 0,
                'today_count': 0,
                'top_news': [],
                'leading_stocks': data.get('stocks', []),
                'source': data.get('source', 'unknown')
            })
        
        # 排序
        hot_spots_list.sort(key=lambda x: x['heat_score'], reverse=True)
        
        # 保存
        output = {
            'generated_at': datetime.now().isoformat(),
            'total_news': len(self.all_news),
            'total_sectors': len(hot_spots_list),
            'summary': hot_spots_list[:10],  # 前10热点
            'hot_spots': hot_spots_list,
            'news': self.all_news[:100]  # 最近100条新闻
        }
        
        output_file = DATA_DIR / 'hot_spots_multi.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"数据已保存: {output_file}")
        logger.info(f"  热点板块: {len(hot_spots_list)}")
        logger.info(f"  新闻: {len(self.all_news)}")


def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("西风多数据源获取开始")
    logger.info("=" * 60)
    
    fetcher = MultiSourceFetcher()
    
    # 获取各数据源
    fetcher.fetch_from_akshare()
    time.sleep(1)
    
    fetcher.fetch_from_ths()
    time.sleep(1)
    
    fetcher.fetch_market_sentiment()
    
    # 合并保存
    fetcher.merge_and_save()
    
    logger.info("=" * 60)
    logger.info("多数据源获取完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
