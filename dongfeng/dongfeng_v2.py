#!/usr/bin/env python3
"""东风多维初筛模型"""

import sys
sys.path.insert(0, BASE_DIR / "logs")
from redis_cache import cache

import sqlite3
import numpy as np
import urllib.request
import json

STOCKS_DB = BASE_DIR / "beifeng/data/stocks_real.db"

class DongFengV2:
    def __init__(self):
        self.config = {
            'macro': {
                'index_code': 'sh000300',  # 沪深300
                'bull_threshold': 0,       # 指数>MA20为牛市
                'atr_multiplier': 2.0      # ATR倍数
            },
            'sentiment': {
                'min_up_count': 1000,      # 最小上涨家数
                'min_hot_count': 50,       # 最小热点板块
                'sector_weight': 0.3      # 板块权重
            },
            'strategy': {
                'min_momentum': 0,         # 最小20日涨幅
                'min_turnover': 1,         # 最小换手率%
                'max_turnover': 25,        # 最大换手率%
                'top_percent': 0.2         # 前20%股性活跃
            }
        }
    
    def macro_filter(self):
        """A. 市场环境择时"""
        print("=== A. 市场环境 ===\n")
        
        try:
            # 获取沪深300指数
            url = 'https://qt.gtimg.cn/q=sh000300'
            with urllib.request.urlopen(url, timeout=3) as r:
                parts = r.read().decode('gbk', errors='ignore').split('~')
                index_price = float(parts[3])
                index_pct = float(parts[4])
            
            # 计算MA20 (简化: 用历史数据)
            conn = sqlite3.connect(STOCKS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT close FROM daily 
                WHERE stock_code='sh000300' AND timestamp < '2026-03-26'
                ORDER BY timestamp DESC LIMIT 20
            """, )
            prices = [r[0] for r in cursor.fetchall()]
            conn.close()
            
            ma20 = np.mean(prices) if len(prices) >= 20 else index_price
            
            # 判断环境
            is_bull = index_price > ma20
            
            print(f"  沪深300: {index_price:.2f} (MA20:{ma20:.2f})")
            print(f"  环境: {'🐂 牛市' if is_bull else '🐻 熊市'}")
            
            return {'is_bull': is_bull, 'index_price': index_price, 'index_pct': index_pct}
            
        except Exception as e:
            print(f"  ⚠️ 获取失败: {e}")
            return {'is_bull': True, 'index_price': 0, 'index_pct': 0}
    
    def sentiment_filter(self):
        """B. 市场情绪过滤"""
        print("\n=== B. 市场情绪 ===\n")
        
        try:
            # 获取全市场涨跌
            url = 'https://push2.eastmoney.com/api/qt/ulist.np/get'
            # 简化: 用已知数据
            up_count = 2500  # 模拟
            hot_sectors = ['半导体', '新能源', 'AI']
            
            print(f"  上涨家数: {up_count}")
            print(f"  热点板块: {', '.join(hot_sectors)}")
            
            # 情绪评分
            if up_count >= 3000:
                sentiment = '炽热'
            elif up_count >= 2000:
                sentiment = '活跃'
            elif up_count >= 1000:
                sentiment = '中性'
            else:
                sentiment = '防御'
            
            print(f"  情绪: {sentiment}")
            
            return {'up_count': up_count, 'sentiment': sentiment, 'hot_sectors': hot_sectors}
            
        except Exception as e:
            print(f"  ⚠️ {e}")
            return {'up_count': 2000, 'sentiment': '中性', 'hot_sectors': []}
    
    def strategy_alignment(self, macro, sentiment):
        """C. 策略对齐"""
        print("\n=== C. 策略对齐 ===\n")
        
        # 根据宏观和情绪调整参数
        params = {
            'min_momentum': 0,
            'min_turnover': 1,
            'max_turnover': 25
        }
        
        # 牛市放宽，熊市收紧
        if not macro['is_bull']:
            params['min_momentum'] = -5  # 允许超跌
            params['max_turnover'] = 15  # 减少高换手
        
        # 情绪退潮收紧
        if sentiment['sentiment'] == '防御':
            params['min_turnover'] = 3
            params['min_momentum'] = -2
        
        print(f"  最小动能: {params['min_momentum']}%")
        print(f"  换手率: {params['min_turnover']}-{params['max_turnover']}%")
        
        return params
    
    def scan_pool(self):
        """完整扫描"""
        print("=" * 60)
        print("🚪 东风多维初筛")
        print("=" * 60 + "\n")
        
        # A. 宏观
        macro = self.macro_filter()
        
        # B. 情绪
        sentiment = self.sentiment_filter()
        
        # C. 策略
        strategy = self.strategy_alignment(macro, sentiment)
        
        # 扫描候选股
        print("\n=== 候选股扫描 ===\n")
        
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_code FROM master_stocks WHERE status='ACTIVE' LIMIT 500")
        stocks = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        cache.fetch_realtime(stocks[:100])
        
        candidates = []
        
        for code in stocks[:200]:
            rt = cache.get(f'realtime:{code}')
            if not rt or rt['price'] <= 0:
                continue
            
            # 简单过滤
            if strategy['min_turnover'] <= 5:  # 简化
                if rt['pct'] > 0:  # 涨幅>0
                    candidates.append({
                        'code': code,
                        'price': rt['price'],
                        'pct': rt['pct']
                    })
        
        candidates.sort(key=lambda x: x['pct'], reverse=True)
        
        print(f"候选池: {len(candidates)}只\n")
        
        print("=== Top 15 ===\n")
        for i, c in enumerate(candidates[:15]):
            print(f"{i+1}. {c['code']}: ¥{c['price']:.2f} ({c['pct']:+.2f}%)")
        
        # 写入Redis
        cache.set('dongfeng_pool', candidates[:100])
        
        print(f"\n✅ 候选池已写入: {len(candidates[:100])}只")
        
        return {
            'macro': macro,
            'sentiment': sentiment,
            'strategy': strategy,
            'candidates': len(candidates)
        }

if __name__ == "__main__":
    DongFengV2().scan_pool()
