#!/usr/bin/env python3
"""
实时价格获取 - 多源重试机制
"""

import requests
import time
from typing import Optional

MAX_RETRIES = 3

def get_price_tencent(code: str, retries=MAX_RETRIES) -> Optional[dict]:
    """腾讯API获取，带重试"""
    for i in range(retries):
        try:
            resp = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
            if '~' in resp.text:
                parts = resp.text.split('~')
                return {
                    'price': float(parts[3]) if parts[3] else 0,
                    'change_pct': float(parts[5]) if parts[5] else 0,
                    'source': 'tencent'
                }
        except Exception as e:
            if i < retries - 1:
                time.sleep(1)
                continue
    return None

def get_price_sina(code: str, retries=MAX_RETRIES) -> Optional[dict]:
    """新浪API获取，带重试"""
    for i in range(retries):
        try:
            headers = {"Referer": "https://finance.sina.com.cn"}
            resp = requests.get(f"https://hq.sinajs.cn/list={code}", headers=headers, timeout=5)
            if '=' in resp.text:
                data = resp.text.split('=')[1].strip('";\n')
                fields = data.split(',')
                return {
                    'price': float(fields[2]) if fields[2] else 0,
                    'change_pct': float(fields[4]) if fields[4] else 0,
                    'source': 'sina'
                }
        except Exception as e:
            if i < retries - 1:
                time.sleep(1)
                continue
    return None

def get_realtime_price(code: str) -> dict:
    """获取实时价格，自动切换数据源"""
    # 腾讯
    result = get_price_tencent(code)
    if result and result['price'] > 0:
        return result
    
    # 新浪备用
    result = get_price_sina(code)
    if result and result['price'] > 0:
        return result
    
    return {"error": "no data"}

if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "sh000001"
    result = get_realtime_price(code)
    print(f"价格: {result.get('price')}, 来源: {result.get('source', 'N/A')}")
