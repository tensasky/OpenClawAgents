#!/usr/bin/env python3
"""东风反陷阱过滤器"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')
from redis_cache import cache

class AntiTrapFilter:
    def __init__(self):
        self.config = {
            'pulse_threshold': 2.0,      # 1分钟涨幅>2%为脉冲
            'volume_threshold': 0.5,      # 成交量<均量50%为缩量
            'limit_up_height': 5,        # 连板>5板为危险
        }
    
    def check_pulse_trap(self, code):
        """检测脉冲诱多"""
        rt = cache.get(f'realtime:{code}')
        if not rt:
            return False, "无数据"
        
        # 获取成交量数据 (简化)
        pct_1min = rt.get('pct', 0)
        vol_1min = rt.get('vol', 1000000)
        avg_vol = rt.get('avg_vol_5min', 2000000)
        
        # 脉冲检测：涨幅>2%但成交量<均量50%
        if pct_1min > self.config['pulse_threshold'] and vol_1min < avg_vol * self.config['volume_threshold']:
            return True, f"脉冲诱多: 涨幅{pct_1min}%, 成交量{vol_1min/avg_vol*100:.0f}%"
        
        return False, "正常"
    
    def check_limit_up_trap(self, code):
        """检测连板陷阱"""
        rt = cache.get(f'realtime:{code}')
        if not rt:
            return False, "正常"
        
        # 获取连板数据 (简化)
        limit_count = rt.get('limit_count', 0)
        
        if limit_count > self.config['limit_up_height']:
            return True, f"连板过高: {limit_count}板"
        
        return False, "正常"
    
    def filter(self, candidates):
        """过滤候选股"""
        filtered = []
        
        for c in candidates:
            code = c['code']
            
            # 脉冲检测
            is_trap, msg = self.check_pulse_trap(code)
            if is_trap:
                c['trap'] = True
                c['trap_msg'] = msg
                filtered.append(c)
                continue
            
            # 连板检测
            is_trap, msg = self.check_limit_up_trap(code)
            if is_trap:
                c['trap'] = True
                c['trap_msg'] = msg
                filtered.append(c)
                continue
            
            c['trap'] = False
            filtered.append(c)
        
        return filtered

if __name__ == "__main__":
    ft = AntiTrapFilter()
    
    # 测试
    codes = ['sh600036', 'sh600000']
    cache.fetch_realtime(codes)
    
    for code in codes:
        is_trap, msg = ft.check_pulse_trap(code)
        print(f"{code}: {'⚠️ ' + msg if is_trap else '✅ 正常'}")
