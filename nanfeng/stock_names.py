#!/usr/bin/env python3
"""
股票名称查询模块
支持从多个数据源获取股票中文名称
"""

import json
import sqlite3
from pathlib import Path
from typing import Optional, Dict
import requests
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("南风")


BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"

class StockNameResolver:
    """股票名称解析器"""
    
    def __init__(self):
        self.cache = {}
        self._load_hot_spots()
    
    def _load_hot_spots(self):
        """从热点数据加载股票名称"""
        if XIFENG_HOTSPOTS.exists():
            try:
                with open(XIFENG_HOTSPOTS, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for spot in data.get('hot_spots', []):
                    for stock in spot.get('leading_stocks', []):
                        code = stock.get('code', '')
                        name = stock.get('name', '')
                        if code and name:
                            self.cache[code] = name
            except Exception as e:
                log.info(f"加载热点数据失败: {e}")
    
    def get_name(self, stock_code: str) -> str:
        """获取股票名称"""
        # 1. 检查缓存
        if stock_code in self.cache:
            return self.cache[stock_code]
        
        # 2. 尝试从数据库获取
        name = self._get_from_db(stock_code)
        if name:
            self.cache[stock_code] = name
            return name
        
        # 3. 尝试从腾讯API获取
        name = self._get_from_tencent(stock_code)
        if name:
            self.cache[stock_code] = name
            return name
        
        return stock_code
    
    def _get_from_db(self, stock_code: str) -> Optional[str]:
        """从数据库获取"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            # 尝试从fundamental_raw获取
            cursor.execute("""
                SELECT stock_code FROM fundamental_raw
                WHERE stock_code = ? LIMIT 1
            """, (stock_code,))
            
            conn.close()
            return None  # 数据库里没有名称字段
        except:
            return None
    
    def _get_from_tencent(self, stock_code: str) -> Optional[str]:
        """从腾讯财经API获取"""
        try:
            # 转换代码格式
            if stock_code.startswith('sh'):
                tencent_code = stock_code.replace('sh', 'sh')  # sh600000
            elif stock_code.startswith('sz'):
                tencent_code = stock_code.replace('sz', 'sz')  # sz000001
            else:
                return None
            
            url = f"https://qt.gtimg.cn/q={tencent_code}"
            response = requests.get(url, timeout=5)
            response.encoding = 'gbk'
            
            # 解析返回数据
            # 格式: v_sh600000="1~浦发银行~600000~..."
            data = response.text
            if '~' in data:
                parts = data.split('~')
                if len(parts) >= 2:
                    name = parts[1]
                    return name
        except Exception as e:
            log.info(f"获取 {stock_code} 名称失败: {e}")
        
        return None
    
    def batch_get_names(self, stock_codes: list) -> Dict[str, str]:
        """批量获取股票名称"""
        result = {}
        for code in stock_codes:
            result[code] = self.get_name(code)
        return result


# 全局实例
_name_resolver = None

def get_stock_name(stock_code: str) -> str:
    """获取股票名称的全局函数"""
    global _name_resolver
    if _name_resolver is None:
        _name_resolver = StockNameResolver()
    return _name_resolver.get_name(stock_code)


def batch_get_stock_names(stock_codes: list) -> Dict[str, str]:
    """批量获取股票名称"""
    global _name_resolver
    if _name_resolver is None:
        _name_resolver = StockNameResolver()
    return _name_resolver.batch_get_names(stock_codes)


if __name__ == '__main__':
    # 测试
    codes = ['sh600268', 'sh600068', 'sh600233', 'sh600163', 'sh600158']
    resolver = StockNameResolver()
    
    log.info("股票名称查询测试:")
    for code in codes:
        name = resolver.get_name(code)
        log.info(f"  {code}: {name}")
