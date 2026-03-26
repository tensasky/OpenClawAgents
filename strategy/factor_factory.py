#!/usr/bin/env python3
"""因子工厂 - 动态计算因子"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')

from redis_cache import cache
import sqlite3
import numpy as np
import json

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
STRATEGY_DB = "/Users/roberto/Documents/OpenClawAgents/strategy/strategy.db"

class FactorFactory:
    def __init__(self):
        self.factors = {
            'close': self.f_close,
            'ma5': self.f_ma5,
            'ma10': self.f_ma10,
            'ma20': self.f_ma20,
            'ma20_slope': self.f_ma20_slope,
            'rsi': self.f_rsi,
            'pct': self.f_pct,
            'volume': self.f_volume,
            'bullish_ma': self.f_bullish_ma,
        }
    
    def load_strategy(self):
        """从数据库加载策略"""
        conn = sqlite3.connect(STRATEGY_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT params_json FROM strategies WHERE status='ACTIVE'")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.loads(row[0])
        return {}
    
    def get_price_data(self, code):
        """获取价格数据"""
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT close FROM daily 
            WHERE stock_code=? AND timestamp < '2026-03-26'
            ORDER BY timestamp DESC LIMIT 30
        """, (code,))
        
        prices = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        return prices[::-1] if prices else []
    
    # === 因子函数 ===
    def f_close(self, code):
        rt = cache.get(f'realtime:{code}')
        if rt:
            return rt['price']
        
        prices = self.get_price_data(code)
        return prices[-1] if prices else 0
    
    def f_ma5(self, code):
        prices = self.get_price_data(code)
        if len(prices) >= 5:
            return np.mean(prices[-5:])
        return 0
    
    def f_ma10(self, code):
        prices = self.get_price_data(code)
        if len(prices) >= 10:
            return np.mean(prices[-10:])
        return 0
    
    def f_ma20(self, code):
        prices = self.get_price_data(code)
        if len(prices) >= 20:
            return np.mean(prices[-20:])
        return 0
    
    def f_ma20_slope(self, code):
        prices = self.get_price_data(code)
        if len(prices) >= 25:
            ma = np.convolve(prices, np.ones(20)/20, mode='valid')
            if len(ma) >= 5:
                return (ma[-1] - ma[-5]) / ma[-5]
        return 0
    
    def f_rsi(self, code):
        prices = self.get_price_data(code)
        if len(prices) < 15:
            return 50
        
        deltas = np.diff(prices)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        avg_gain = np.mean(gains[-14:])
        avg_loss = np.mean(losses[-14:])
        rs = avg_gain / avg_loss if avg_loss > 0 else 100
        return 100 - (100 / (1 + rs))
    
    def f_pct(self, code):
        rt = cache.get(f'realtime:{code}')
        if rt:
            return rt.get('pct', 0)
        return 0
    
    def f_volume(self, code):
        return 1.0  # 简化
    
    def f_bullish_ma(self, code):
        return self.f_ma5(code) > self.f_ma10(code) > self.f_ma20(code)
    
    def compute_factor(self, code, factor_name):
        """计算单个因子"""
        if factor_name in self.factors:
            return self.factors[factor_name](code)
        return 0
    
    def evaluate(self, code):
        """评估股票 - 使用策略中的因子"""
        strategy = self.load_strategy()
        
        if not strategy:
            return None
        
        filters = strategy.get('filters', {})
        
        # 计算因子
        values = {}
        for name in self.factors.keys():
            values[name] = self.compute_factor(code)
        
        # 应用过滤器
        if filters.get('min_ma20_slope', 0) > 0:
            if values['ma20_slope'] < filters['min_ma20_slope']:
                return None
        
        rsi = values['rsi']
        min_rsi = filters.get('min_rsi', 0)
        max_rsi = filters.get('max_rsi', 100)
        if not (min_rsi <= rsi <= max_rsi):
            return None
        
        pct = values['pct']
        min_pct = filters.get('min_pct', -100)
        max_pct = filters.get('max_pct', 100)
        if not (min_pct <= pct <= max_pct):
            return None
        
        # 评分
        weights = strategy.get('weights', {})
        thresholds = strategy.get('thresholds', {})
        
        score = 0
        if values['bullish_ma']:
            score += weights.get('bullish', 20)
        if values['ma20_slope'] > 0.002:
            score += weights.get('ma20_slope', 20)
        if 40 < rsi < 75:
            score += weights.get('rsi', 15)
        
        if score < thresholds.get('min_score', 30):
            return None
        
        return {
            'code': code,
            'price': values['close'],
            'pct': values['pct'],
            'score': score,
            'factors': values
        }

if __name__ == "__main__":
    factory = FactorFactory()
    
    # 预热缓存
    cache.fetch_realtime(['sh600519', 'sh601318', 'sh600036'])
    
    print("=== 因子工厂测试 ===\n")
    
    # 测试单因子
    for factor in ['close', 'ma20', 'rsi', 'pct', 'bullish_ma']:
        value = factory.compute_factor('sh600519', factor)
        print(f"{factor}: {value}")
    
    # 评估股票
    print("\n=== 评估 ===")
    result = factory.evaluate('sh600036')
    if result:
        print(f"{result['code']}: ¥{result['price']:.2f} 评分:{result['score']}")
