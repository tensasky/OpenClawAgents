#!/usr/bin/env python3
"""红中信号生成 - 增加炸板风险预警"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')
from redis_cache import cache
import sqlite3
import numpy as np

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
STRATEGY_DB = "/Users/roberto/Documents/OpenClawAgents/strategy/strategy.db"

class HongZhongWithRisk:
    def __init__(self):
        self.biasis_threshold = 0.05  # 5%乖离率阈值
    
    def load_strategy(self):
        import json
        conn = sqlite3.connect(STRATEGY_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT params_json FROM strategies WHERE status='ACTIVE'")
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else {}
    
    def calculate_biasis(self, code):
        """计算乖离率 (当前价格 vs 分时均线)"""
        try:
            # 获取实时价格
            rt = cache.get(f'realtime:{code}')
            if not rt:
                return 0, 0
            
            current = rt['price']
            
            # 获取分时数据 (简化: 用今日开盘价作为均线替代)
            conn = sqlite3.connect(STOCKS_DB)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT open FROM daily 
                WHERE stock_code=? AND timestamp='2026-03-26'
            """, (code,))
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                ma = row[0]  # 用开盘价代替分时均线
                bias = (current - ma) / ma
                return bias, current
            
            return 0, current
        except:
            return 0, 0
    
    def check_break_risk(self, code):
        """B. 炸板风险检测"""
        bias, current = self.calculate_biasis(code)
        
        if abs(bias) > self.biasis_threshold:
            if bias > 0:
                # 涨太快，可能炸板
                return True, f"乖离率{bias*100:.1f}%，不追高"
            else:
                return True, f"乖离率{bias*100:.1f}%，超跌"
        
        return False, "正常"
    
    def generate_signals(self):
        """生成信号 (带风险标签)"""
        strategy = self.load_strategy()
        
        if not strategy:
            print("⚠️ 无活跃策略")
            return []
        
        filters = strategy.get('filters', {})
        weights = strategy.get('weights', {})
        
        conn = sqlite3.connect(STOCKS_DB)
        
        # 获取候选池
        pool = cache.get('dongfeng_pool') or []
        
        signals = []
        
        for item in pool[:50]:
            code = item['code']
            
            # 炸板风险检测
            break_risk, risk_msg = self.check_break_risk(code)
            
            # 获取历史计算因子
            cursor = conn.cursor()
            cursor.execute("""
                SELECT close FROM daily WHERE stock_code=? AND timestamp < '2026-03-26'
                ORDER BY timestamp DESC LIMIT 30
            """, (code,))
            prices = [r[0] for r in cursor.fetchall()]
            
            if len(prices) < 20:
                continue
            
            prices = prices[::-1]
            
            # 计算因子
            ma_arr = np.convolve(prices, np.ones(20)/20, mode='valid')
            slope = (ma_arr[-1] - ma_arr[-5]) / ma_arr[-5] if len(ma_arr) >= 5 else 0
            
            deltas = np.diff(prices)
            rs = np.mean(np.where(deltas > 0, deltas, 0)[-14:]) / (np.mean(np.where(deltas < 0, -deltas, 0)[-14:]) + 0.001)
            rsi = 100 - (100 / (1 + rs))
            
            # 过滤
            if slope < filters.get('min_ma20_slope', 0):
                continue
            if not (filters.get('min_rsi', 0) <= rsi <= filters.get('max_rsi', 100)):
                continue
            
            # 评分
            score = 0
            if slope > 0.002:
                score += weights.get('ma20_slope', 20)
            if 40 < rsi < 75:
                score += weights.get('rsi', 15)
            
            if score < 30:
                continue
            
            # 信号
            signals.append({
                'code': code,
                'price': item['price'],
                'pct': item['pct'],
                'score': score,
                'break_risk': break_risk,
                'risk_msg': risk_msg
            })
        
        conn.close()
        
        # 排序并标记风险
        signals.sort(key=lambda x: x['score'], reverse=True)
        
        return signals[:10]

if __name__ == "__main__":
    hc = HongZhongWithRisk()
    signals = hc.generate_signals()
    
    print("=== 红中信号 (带炸板风险) ===\n")
    
    for i, s in enumerate(signals):
        risk_tag = "⚠️" if s['break_risk'] else "✅"
        print(f"{i+1}. {s['code']}: ¥{s['price']:.2f} ({s['pct']:+.2f}%) 评分:{s['score']} {risk_tag} {s['risk_msg']}")
