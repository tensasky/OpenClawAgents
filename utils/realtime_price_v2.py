#!/usr/bin/env python3
"""
实时价格获取 - Baostock优先
"""

import baostock as bs
from typing import Dict
from datetime import datetime


def get_realtime_price(code: str) -> Dict:
    """
    获取实时价格 - 优先Baostock
    """
    try:
        lg = bs.login()
        
        # 转换代码格式
        if code.startswith('sh'):
            bs_code = 'sh.' + code[2:]
        elif code.startswith('sz'):
            bs_code = 'sz.' + code[2:]
        else:
            bs_code = code
            
        # 获取今日数据
        rs = bs.query_history_k_data_plus(bs_code, 
            "date,code,open,high,low,close,volume,pctChg",
            start_date=datetime.now().strftime('%Y-%m-%d'),
            end_date=datetime.now().strftime('%Y-%m-%d'))
        
        if rs.error_code == '0' and rs.next():
            data = rs.get_row_data()
            price = float(data[5])
            change_pct = float(data[7]) if data[7] else 0
            
            bs.logout()
            
            return {
                'price': price,
                'change_pct': round(change_pct, 2),
                'source': 'baostock',
                'verified': True
            }
            
    except Exception as e:
        print(f"Baostock错误: {e}")
    
    bs.logout()
    return {'error': 'no data'}


if __name__ == "__main__":
    import sys
    code = sys.argv[1] if len(sys.argv) > 1 else "sh600289"
    result = get_realtime_price(code)
    print(f"价格: ¥{result.get('price', 'N/A')}")
    print(f"涨跌幅: {result.get('change_pct', 'N/A')}%")
    print(f"数据源: {result.get('source', 'N/A')}")
