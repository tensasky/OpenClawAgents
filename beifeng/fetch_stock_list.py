#!/usr/bin/env python3
"""
获取全 A 股股票列表
"""
import requests
import time
import json
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")


def fetch_all_stocks():
    """从东方财富获取全量 A 股"""
    all_stocks = []
    
    for page in range(1, 30):  # 最多30页
        url = "http://push2.eastmoney.com/api/qt/clist/get"
        params = {
            "pn": page,
            "pz": 500,
            "po": 1,
            "np": 1,
            "fltt": 2,
            "invt": 2,
            "fid": "f12",
            "fs": "m:0+t:6,m:0+t:13,m:1+t:2,m:1+t:23",
            "fields": "f12,f13,f14",
            "_": int(time.time() * 1000)
        }
        
        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()
            
            items = data.get("data", {}).get("diff", [])
            if not items:
                break
            
            for item in items:
                code = item.get("f12")
                market = item.get("f13")
                name = item.get("f14")
                
                if code and market:
                    prefix = "sh" if str(market) == "1" else "sz"
                    all_stocks.append({
                        "code": f"{prefix}{code}",
                        "name": name,
                        "market": prefix.upper()
                    })
            
            log.info(f"✅ 第{page}页: {len(items)} 只，累计 {len(all_stocks)}")
            time.sleep(0.3)
            
        except Exception as e:
            log.info(f"❌ 第{page}页失败: {e}")
            break
    
    # 保存到文件
    output = Path.home() / "Documents/OpenClawAgents/beifeng/data/all_stocks.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump(all_stocks, f, ensure_ascii=False, indent=2)
    
    log.info(f"\n🎉 总共获取 {len(all_stocks)} 只股票")
    log.info(f"💾 已保存到: {output}")
    return all_stocks

if __name__ == '__main__':
    fetch_all_stocks()
