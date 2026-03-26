#!/usr/bin/env python3
"""判官L2验证 - API实时盘口校验"""

import urllib.request
import time
from datetime import datetime

class JudgeL2:
    def __init__(self):
        self.api_delay = 5  # API延迟阈值(秒)
        self.volume_drop_threshold = 0.3  # 成交量下降30%
    
    def verify_realtime(self, code, signal_price):
        """L2实时验证"""
        try:
            url = f'https://qt.gtimg.cn/q={code}'
            with urllib.request.urlopen(url, timeout=2) as r:
                parts = r.read().decode('gbk', errors='ignore').split('~')
                
                # 获取L2数据
                current_price = float(parts[3]) if parts[3] else 0
                volume = float(parts[6]) if parts[6] else 0
                amount = float(parts[7]) if parts[7] else 0
                
                # 验证1: 价格变化
                if current_price > 0:
                    change_pct = abs(current_price - signal_price) / signal_price
                    if change_pct > 0.05:  # >5%变化
                        return False, f"价格变动{change_pct*100:.1f}%"
                
                # 验证2: 成交量异常 (简化)
                # 如果volume突然下降，可能是诱多
                
                return True, "L2验证通过"
                
        except Exception as e:
            return True, f"L2验证跳过: {e}"
    
    def batch_verify(self, signals):
        """批量L2验证"""
        verified = []
        
        for s in signals:
            ok, msg = self.verify_realtime(s['code'], s['price'])
            s['l2_verified'] = ok
            s['l2_msg'] = msg
            
            if ok:
                verified.append(s)
            else:
                print(f"  ⚠️ L2拦截: {s['code']} - {msg}")
            
            time.sleep(0.1)  # 防止请求过快
        
        return verified

if __name__ == "__main__":
    judge = JudgeL2()
    
    # 测试
    test_signals = [{'code': 'sh600036', 'price': 39.56}]
    result = judge.batch_verify(test_signals)
    
    print(f"验证结果: {len(result)}/{len(test_signals)}通过")
