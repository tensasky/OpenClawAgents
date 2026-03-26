#!/usr/bin/env python3
"""
西风 - 板块热点分析
使用腾讯API获取实时板块数据
"""

import urllib.request
import json
import sys
from pathlib import Path
from datetime import datetime

WORKDIR = Path(__file__).parent.parent
sys.path.insert(0, str(WORKDIR / "utils"))
from agent_logger import get_logger

log = get_logger("西风")

def get_sectors():
    """从腾讯获取板块数据"""
    sectors = []
    
    # 腾讯行业板块API
    url = "https://web.ifzq.gtimg.cn/appstock/app/fqhybchart/getdata"
    params = "_var=data&code=bk0801"
    
    try:
        req = urllib.request.Request(f"{url}?{params}")
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=10) as response:
            text = response.read().decode('utf-8')
            # 解析数据
            if 'data' in text:
                log.info("从腾讯获取板块数据成功")
                # 使用备用方法
    except Exception as e:
        log.warning(f"腾讯API失败: {e}")
    
    # 使用自定义板块列表 + 腾讯实时数据
    sector_stocks = {
        "人工智能": ["sh600570", "sh688300", "sh688666", "sh002410", "sh300212"],
        "新能源汽车": ["sh600418", "sh002594", "sh300750", "sh002466", "sh002812"],
        "半导体": ["sh688981", "sh603986", "sh688008", "sh002371", "sh603260"],
        "消费电子": ["sh000725", "sh002475", "sh002236", "sh002920", "sh603501"],
        "医药医疗": ["sh600276", "sh600529", "sh002223", "sh300003", "sh600566"],
        "银行": ["sh601398", "sh601939", "sh601988", "sh601328", "sh600016"],
    }
    
    # 获取每只股票的实时涨跌幅
    sector_pcts = {}
    
    for sector, stocks in sector_stocks.items():
        pcts = []
        for stock in stocks[:3]:
            try:
                url = f'https://qt.gtimg.cn/q={stock}'
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=3) as response:
                    text = response.read().decode('gbk')
                    if '~' in text:
                        parts = text.split('~')
                        pct = float(parts[5]) / 100 if parts[5] else 0
                        pcts.append(pct)
            except:
                pass
        
        if pcts:
            sector_pcts[sector] = sum(pcts) / len(pcts)
    
    # 排序
    sorted_sectors = sorted(sector_pcts.items(), key=lambda x: x[1], reverse=True)
    
    result = []
    for name, pct in sorted_sectors:
        result.append({
            'name': name,
            'pct': pct,
            'code': f"bk_{name}"
        })
    
    return result

def main():
    log.info("▶️  西风V2.1 板块分析开始")
    
    sectors = get_sectors()
    
    if sectors:
        log.info(f"获取到 {len(sectors)} 个板块")
        
        # 保存到数据库
        import sqlite3
        db_path = WORKDIR / "xifeng/data/xifeng.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 清除旧数据
        cursor.execute("DELETE FROM sectors")
        
        for s in sectors:
            cursor.execute("""
                INSERT INTO sectors (sector_code, sector_name, change_pct, timestamp)
                VALUES (?, ?, ?, ?)
            """, (s['code'], s['name'], s['pct'], timestamp))
        
        conn.commit()
        conn.close()
        
        log.info(f"已保存 {len(sectors)} 个板块到数据库")
        
        print(f"\n=== 今日板块涨幅 ({datetime.now().strftime('%H:%M')}) ===")
        for i, s in enumerate(sectors, 1):
            print(f"{i}. {s['name']}: {s['pct']:+.1f}%")
    else:
        log.warning("未获取到板块数据")

if __name__ == "__main__":
    main()
