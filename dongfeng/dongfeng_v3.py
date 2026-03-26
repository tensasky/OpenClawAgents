#!/usr/bin/env python3
"""东风多维初筛 V3 - 增加连板高度监控"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')
from redis_cache import cache
import sqlite3
import numpy as np
import urllib.request
import json

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class DongFengV3:
    def __init__(self):
        self.config = {
            'macro': {'index_code': 'sh000300', 'bull_threshold': 0},
            'sentiment': {'min_up_count': 1000, 'min_limit_up': 30},
            'strategy': {'min_turnover': 1, 'max_turnover': 25},
            'limit_up': {'max_height': 7, 'alert_height': 5}  # 连板高度配置
        }
    
    def check_limit_up_height(self):
        """A. 连板高度监控"""
        print("=== A. 连板高度监控 ===\n")
        
        try:
            # 获取昨日涨停数据 (简化模拟)
            # 实际应从东方财富API获取
            url = 'https://push2ex.eastmoney.com/getTopicZTPool'
            
            # 模拟数据
            limit_up_data = {
                'height': 4,  # 假设昨日最高连板4板
                'count': 45,   # 涨停家数
                'direction': 'stable'  # stable/up/down
            }
            
            height = limit_up_data['height']
            direction = limit_up_data['direction']
            
            print(f"  昨日最高连板: {height}板")
            print(f"  涨停家数: {limit_up_data['count']}")
            print(f"  方向: {direction}")
            
            # 判断情绪
            if direction == 'down':
                print("  ⚠️ 短线情绪退潮，减少激进操作")
                return {'safe': False, 'height': height, 'action': 'reduce'}
            elif height >= self.config['limit_up']['alert_height']:
                print("  ⚠️ 连板过高，注意风险")
                return {'safe': False, 'height': height, 'action': 'caution'}
            else:
                print("  ✅ 连板高度正常")
                return {'safe': True, 'height': height, 'action': 'normal'}
                
        except Exception as e:
            print(f"  ⚠️ 获取失败: {e}")
            return {'safe': True, 'height': 0, 'action': 'normal'}
    
    def sentiment_filter(self, limit_up_status):
        """B. 市场情绪过滤 (考虑连板高度)"""
        print("\n=== B. 市场情绪过滤 ===\n")
        
        try:
            url = 'https://push2.eastmoney.com/api/qt/ulist.np/get'
            # 简化
            up_count = 2500
            hot_sectors = ['半导体', '新能源', 'AI']
            
            print(f"  上涨家数: {up_count}")
            print(f"  热点板块: {', '.join(hot_sectors)}")
            
            # 根据连板高度调整情绪判断
            if not limit_up_status['safe']:
                sentiment = '防御'
                print(f"  情绪(调整后): {sentiment} (因连板高度{limit_up_status['height']})")
            else:
                sentiment = '炽热' if up_count >= 3000 else '活跃' if up_count >= 2000 else '中性'
                print(f"  情绪: {sentiment}")
            
            return {'up_count': up_count, 'sentiment': sentiment, 'hot_sectors': hot_sectors}
            
        except Exception as e:
            print(f"  ⚠️ {e}")
            return {'up_count': 2000, 'sentiment': '中性', 'hot_sectors': []}
    
    def scan_pool(self):
        """完整扫描"""
        print("=" * 60)
        print("🚪 东风多维初筛 V3")
        print("=" * 60 + "\n")
        
        # A. 连板高度
        limit_up_status = self.check_limit_up_height()
        
        # B. 情绪 (考虑连板)
        sentiment = self.sentiment_filter(limit_up_status)
        
        # C. 策略参数调整
        print("\n=== C. 策略参数 ===\n")
        
        if limit_up_status['action'] == 'reduce':
            # 减少激进操作
            params = {
                'min_turnover': 5,  # 提高换手率要求
                'max_pct': 3,       # 限制涨幅
                'exclude_high': True  # 排除高位股
            }
            print("  模式: 防御 (降低风险)")
        else:
            params = {
                'min_turnover': 1,
                'max_pct': 10,
                'exclude_high': False
            }
            print("  模式: 正常")
        
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
            
            # 应用参数
            if params['exclude_high'] and rt['pct'] > params['max_pct']:
                continue
            
            if rt['pct'] > 0:
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
        
        cache.set('dongfeng_pool', candidates[:100])
        
        print(f"\n✅ 候选池已写入: {len(candidates[:100])}只")
        
        return {
            'limit_up': limit_up_status,
            'sentiment': sentiment,
            'candidates': len(candidates)
        }

if __name__ == "__main__":
    DongFengV3().scan_pool()
