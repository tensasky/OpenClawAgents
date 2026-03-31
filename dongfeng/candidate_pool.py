#!/usr/bin/env python3
"""东风候选池扫描"""

import sys
sys.path.insert(0, BASE_DIR / "logs")
from redis_cache import cache

import sqlite3
import numpy as np
import time

STOCKS_DB = BASE_DIR / "beifeng/data/stocks_real.db"

class DongFeng:
    def __init__(self):
        self.config = {
            'min_volume': 500000,  # 成交额50万
            'min_price': 1,        # 最低价1元
            'max_price': 500,      # 最高价500元
            'exclude_st': True,     # 剔除ST
            'exclude_new': True,     # 剔除新股(上市不满1年)
            'bullish_ma': True,    # 多头排列
            'pct_range': (2, 5)    # 涨幅2-5%
        }
    
    def check_basic_filter(self, code):
        """基础过滤"""
        # 获取股票信息
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        # 检查是否ST、退市
        # 简化: 检查名称
        cursor.execute("""
            SELECT name FROM stocks 
            WHERE code=?
        """, (code,))
        row = cursor.fetchone()
        
        if row and ('ST' in row[0] or '*ST' in row[0]):
            conn.close()
            return False, "ST股"
        
        conn.close()
        return True, None
    
    def check_liquidity(self, code):
        """流动性过滤"""
        rt = cache.get(f'realtime:{code}')
        
        if not rt:
            return False, "无实时数据"
        
        # 简化: 用涨跌幅和价格估算流动性
        if rt['price'] < self.config['min_price']:
            return False, "价格过低"
        
        if rt['price'] > self.config['max_price']:
            return False, "价格过高"
        
        return True, None
    
    def check_pattern(self, code):
        """形态过滤"""
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT close FROM daily 
            WHERE stock_code=? AND timestamp < '2026-03-26'
            ORDER BY timestamp DESC LIMIT 20
        """, (code,))
        
        prices = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        if len(prices) < 10:
            return False, "数据不足"
        
        prices = prices[::-1]
        
        # 多头排列
        ma5 = np.mean(prices[-5:])
        ma10 = np.mean(prices[-10:])
        ma20 = np.mean(prices[-20:])
        
        if self.config['bullish_ma']:
            if not (ma5 > ma10 > ma20):
                return False, "非多头"
        
        # 涨幅
        rt = cache.get(f'realtime:{code}')
        if rt:
            pct_min, pct_max = self.config['pct_range']
            if not (pct_min <= rt['pct'] <= pct_max):
                return False, "涨幅不符"
        
        return True, None
    
    def scan_pool(self, limit=300):
        """扫描候选池"""
        print("=== 东风候选池扫描 ===\n")
        
        # 获取全部股票
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT stock_code FROM master_stocks WHERE status='ACTIVE' LIMIT ?", (limit,))
        stocks = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        print(f"扫描: {len(stocks)}只\n")
        
        # 预热缓存
        cache.fetch_realtime(stocks[:100])
        
        # 过滤
        candidates = []
        
        for code in stocks:
            # 基础过滤
            ok, reason = self.check_basic_filter(code)
            if not ok:
                continue
            
            # 流动性过滤
            ok, reason = self.check_liquidity(code)
            if not ok:
                continue
            
            # 形态过滤
            ok, reason = self.check_pattern(code)
            if not ok:
                continue
            
            # 获取实时数据
            rt = cache.get(f'realtime:{code}')
            if rt:
                candidates.append({
                    'code': code,
                    'price': rt['price'],
                    'pct': rt['pct']
                })
        
        print(f"候选池: {len(candidates)}只\n")
        
        # 排序
        candidates.sort(key=lambda x: x['pct'], reverse=True)
        
        # 写入Redis
        cache.set('candidate_pool', candidates)
        
        print("=== Top 20 ===\n")
        for i, c in enumerate(candidates[:20]):
            print(f"{i+1}. {c['code']}: ¥{c['price']:.2f} ({c['pct']:+.2f}%)")
        
        return candidates

if __name__ == "__main__":
    DongFeng().scan_pool(limit=500)
