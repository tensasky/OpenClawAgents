#!/usr/bin/env python3
"""Redis风格缓存 - 直接API调用版"""

import sqlite3
import threading
import time
import urllib.request
from datetime import datetime
from collections import deque
import json

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class RedisCache:
    """Redis风格缓存 - 直接API调用"""
    
    def __init__(self):
        self.data = {}           # 实时数据: {code: {price, pct, time}}
        self.minute_buffer = deque()  # 分钟数据缓冲
        self.lock = threading.Lock()
        
        print("✅ Redis缓存已启动 (直接API模式)")
    
    def set(self, key: str, value):
        """设置缓存"""
        with self.lock:
            self.data[key] = {
                'value': value,
                'time': datetime.now().timestamp()
            }
    
    def get(self, key: str, default=None):
        """获取缓存"""
        with self.lock:
            item = self.data.get(key)
            return item['value'] if item else default
    
    def get_all_realtime(self):
        """获取所有实时数据"""
        with self.lock:
            result = {}
            for k, v in self.data.items():
                if k.startswith('realtime:'):
                    result[k.replace('realtime:', '')] = v['value']
            return result
    
    def append_minute(self, code: str, timestamp: str, price: float):
        """追加分钟数据"""
        self.minute_buffer.append({
            'code': code,
            'timestamp': timestamp,
            'price': price
        })
        
        if len(self.minute_buffer) > 500:
            self._flush_minute()
    
    def _flush_minute(self):
        """刷写分钟数据到数据库"""
        if not self.minute_buffer:
            return
        
        items = list(self.minute_buffer)
        self.minute_buffer.clear()
        
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        for item in items:
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO minute (stock_code, timestamp, close)
                    VALUES (?, ?, ?)
                """, (item['code'], item['timestamp'], item['price']))
            except:
                pass
        
        conn.commit()
        conn.close()
        
        print(f"  💾 持久化 {len(items)} 条分钟数据")
    
    def fetch_realtime(self, codes: list):
        """批量获取实时数据 - 直接调用API"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        for code in codes:
            try:
                url = f'https://qt.gtimg.cn/q={code}'
                with urllib.request.urlopen(url, timeout=2) as r:
                    parts = r.read().decode('gbk', errors='ignore').split('~')
                    price = float(parts[3]) if parts[3] else 0
                    pct = float(parts[4]) / 100 if parts[4] else 0
                    
                    if price > 0:
                        self.set(f"realtime:{code}", {'price': price, 'pct': pct})
                        
                        # 追加分钟数据
                        self.append_minute(code, now, price)
                        
            except:
                pass
        
        # 定期持久化
        self._flush_minute()

# 全局实例
cache = RedisCache()
