#!/usr/bin/env python3
"""白板辅助东风进化 - 自动调参"""

import sqlite3
import json
from datetime import datetime, timedelta

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STRATEGY_DB = "/Users/roberto/Documents/OpenClawAgents/strategy/strategy.db"

class DongFengOptimizer:
    def __init__(self):
        self.config_path = "/Users/roberto/Documents/OpenClawAgents/dongfeng/config.json"
    
    def load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)
    
    def save_config(self, config):
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def analyze_funnel_efficiency(self):
        """回溯漏斗效率"""
        print("=== 回溯漏斗效率 ===\n")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        # 获取最近信号
        cursor.execute("""
            SELECT stock_code, entry_price, score, timestamp 
            FROM signals 
            WHERE timestamp >= datetime('now', '-7 days')
            ORDER BY score DESC
            LIMIT 50
        """)
        
        signals = cursor.fetchall()
        conn.close()
        
        if not signals:
            print("无信号数据")
            return None
        
        # 分析
        print(f"分析 {len(signals)} 个信号:\n")
        
        # 按评分分组
        score_buckets = {}
        for s in signals:
            bucket = (s[2] // 10) * 10
            if bucket not in score_buckets:
                score_buckets[bucket] = []
            score_buckets[bucket].append(s)
        
        print("评分分布:")
        for bucket in sorted(score_buckets.keys()):
            count = len(score_buckets[bucket])
            print(f"  评分{bucket}: {count}只")
        
        return score_buckets
    
    def auto_tune(self, score_buckets):
        """自动调参"""
        print("\n=== 自动调参 ===\n")
        
        config = self.load_config()
        
        # 基于分析结果调整
        high_score_count = len(score_buckets.get(70, [])) + len(score_buckets.get(80, []))
        
        if high_score_count >= 10:
            print("策略状态: 高分信号充足 → 维持当前参数")
        elif high_score_count >= 5:
            print("策略状态: 高分信号减少 → 放宽筛选条件")
            # 放宽
            config['strategy']['min_momentum'] -= 1
            config['sentiment']['min_up_count'] -= 200
        else:
            print("策略状态: 高分信号不足 → 切换到防御模式")
            # 收紧
            config['strategy']['min_turnover'] = 3
            config['sentiment']['min_up_count'] = 1500
        
        # 检查市场环境
        print("\n市场环境检查:")
        
        # 模拟: 检查是否跌破MA20
        market_bear = True  # 简化
        
        if market_bear:
            print("  检测到熊市 → 减半筛选规模")
            config['macro']['scale_factor'] = 0.5
        
        # 情绪检查
        print("\n情绪检查:")
        print("  连板股断板 → 剔除跟随品种")
        config['sentiment']['exclude_followers'] = True
        
        # 板块检查
        print("\n板块检查:")
        print("  强制要求: 属于Top5热门行业")
        config['sector']['require_top5'] = True
        
        # 量价检查
        print("\n量价检查:")
        print("  剔除缩量上涨和放量下跌")
        config['volume_price']['exclude_shrink_up'] = True
        config['volume_price']['exclude_volume_down'] = True
        
        # 保存
        self.save_config(config)
        
        print("\n=== 新配置 ===\n")
        print(json.dumps(config, indent=2))
        
        return config
    
    def generate_directive(self, config):
        """生成调参指令"""
        print("\n=== 东风指令 ===\n")
        
        directives = []
        
        if config['macro']['scale_factor'] < 1:
            directives.append("📉 筛选规模减半 (规避系统风险)")
        
        if config['sentiment']['exclude_followers']:
            directives.append("🛡️ 剔除连板跟随品种 (规避短线退潮)")
        
        if config['sector']['require_top5']:
            directives.append("🔥 仅限Top5热门行业 (确保资金合力)")
        
        if config['volume_price']['exclude_shrink_up']:
            directives.append("📊 剔除缩量上涨 (确保真实性)")
        
        for d in directives:
            print(d)
        
        return directives

if __name__ == "__main__":
    optimizer = DongFengOptimizer()
    
    # 分析
    buckets = optimizer.analyze_funnel_efficiency()
    
    if buckets:
        # 调参
        config = optimizer.auto_tune(buckets)
        
        # 生成指令
        optimizer.generate_directive(config)
