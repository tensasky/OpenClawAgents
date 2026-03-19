#!/usr/bin/env python3
"""
实时价格获取 - 智能切换
盘中(9:30-15:00): 腾讯/新浪
盘后: Baostock
"""

import baostock as bs
import requests
from typing import Dict
from datetime import datetime, time


def is_trading_hours() -> bool:
    """是否在交易时间"""
    now = datetime.now()
    t = now.time()
    # 周一到周五，交易时间
    if now.weekday() >= 5:
        return False
    # 9:30-11:30, 13:00-15:00
    return (time(9, 30) <= t <= time(11, 30)) or (time(13, 0) <= t <= time(15, 0))


def get_price_tencent(code: str) -> Dict:
    """腾讯API获取"""
    try:
        resp = requests.get(f"https://qt.gtimg.cn/q={code}", timeout=5)
        if '~' in resp.text:
            parts = resp.text.split('~')
            price = float(parts[3]) if parts[3] else 0
            change_pct = float(parts[5]) if parts[5] else 0
            return {'price': price, 'change_pct': change_pct, 'source': 'tencent'}
    except:
        pass
    return None


def get_price_sina(code: str) -> Dict:
    """新浪API获取"""
    try:
        headers = {'Referer': 'https://finance.sina.com.cn'}
        resp = requests.get(f"https://hq.sinajs.cn/list={code}", headers=headers, timeout=5)
        if '=' in resp.text:
            data = resp.text.split('=')[1].strip('";\n')
            fields = data.split(',')
            if len(fields) > 4:
                price = float(fields[2]) if fields[2] else 0
                change_pct = float(fields[4]) if fields[4] else 0
                return {'price': price, 'change_pct': change_pct, 'source': 'sina'}
    except:
        pass
    return None


def get_price_baostock(code: str) -> Dict:
    """Baostock获取"""
    try:
        lg = bs.login()
        
        # 转换代码
        if code.startswith('sh'):
            bs_code = 'sh.' + code[2:]
        elif code.startswith('sz'):
            bs_code = 'sz.' + code[2:]
        else:
            bs_code = code
            
        rs = bs.query_history_k_data_plus(bs_code, 
            "date,close,pctChg",
            start_date=datetime.now().strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d'))
        
        if rs.error_code == '0' and rs.next():
            data = rs.get_row_data()
            price = float(data[1])
            change_pct = float(data[2]) if data[2] else 0
            bs.logout()
            return {'price': price, 'change_pct': change_pct, 'source': 'baostock'}
            
    except:
        pass
    finally:
        try:
            bs.logout()
        except:
            pass
    return None


def get_realtime_price(code: str) -> Dict:
    """
    智能获取实时价格
    盘中用腾讯/新浪，盘后用Baostock
    """
    # 盘后(非交易时间)用Baostock
    if not is_trading_hours():
        result = get_price_baostock(code)
        if result:
            return {**result, 'mode': 'after-hours'}
    
    # 盘中用腾讯
    result = get_price_tencent(code)
    if result:
        return {**result, 'mode': 'realtime'}
    
    # 腾讯失败用新浪
    result = get_price_sina(code)
    if result:
        return {**result, 'mode': 'realtime'}
    
    # 都失败用Baostock
    result = get_price_baostock(code)
    if result:
        return {**result, 'mode': 'fallback'}
    
    return {'error': 'no data'}


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "sh600289"
    
    result = get_realtime_price(code)
    print(f"股票: {code}")
    print(f"价格: ¥{result.get('price', 'N/A')}")
    print(f"涨跌幅: {result.get('change_pct', 'N/A')}%")
    print(f"数据源: {result.get('source', 'N/A')}")
    print(f"模式: {result.get('mode', 'N/A')}")
