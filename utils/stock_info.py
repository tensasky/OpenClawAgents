#!/usr/bin/env python3
"""
股票信息模块 - 统一获取板块、财务、市值数据
使用统一架构: db_pool + agent_logger

数据来源:
- 腾讯API: 实时价格、市值
- 东方财富API: 板块、行业、财务
"""

import requests
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

# 统一架构
import sys
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents"))
from utils.db_pool import get_pool
from utils.agent_logger import get_logger

log = get_logger("股票信息")

# 配置
DB_PATH = Path.home() / "Documents/OpenClawAgents" / "beifeng/data/stocks_real.db"


@dataclass
class StockInfo:
    """股票完整信息"""
    code: str
    name: str
    
    # 实时数据
    price: float = 0
    change: float = 0
    change_pct: float = 0
    volume: int = 0
    amount: float = 0
    market_cap: float = 0  # 总市值(亿)
    float_cap: float = 0   # 流通市值(亿)
    
    # 基本信息
    sector: str = ""     # 所属板块
    industry: str = ""    # 所属行业
    
    # 财务数据
    revenue: float = 0    # 营收(亿)
    profit: float = 0     # 净利润(亿)
    roe: float = 0       # ROE
    gross_margin: float = 0  # 毛利率


class StockInfoAPI:
    """股票信息统一API"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
    
    def get_realtime(self, code: str) -> Optional[Dict]:
        """
        获取实时行情
        腾讯API: qt.gtimg.cn/q=code
        """
        try:
            url = f"https://qt.gtimg.cn/q={code}"
            resp = self.session.get(url, timeout=3)
            
            if '~' not in resp.text:
                return None
            
            parts = resp.text.split('~')
            
            return {
                'price': float(parts[3]) if parts[3] else 0,
                'change': float(parts[31]) if parts[31] else 0,
                'change_pct': float(parts[32]) if parts[32] else 0,
                'volume': int(parts[36]) if parts[36] else 0,
                'amount': float(parts[37]) if parts[37] else 0,
                'market_cap': float(parts[45]) if parts[45] else 0,
                'float_cap': float(parts[46]) if parts[46] else 0,
            }
        except Exception as e:
            log.warning(f"获取实时行情失败 {code}: {e}")
            return None
    
    def get_batch_realtime(self, codes: List[str]) -> Dict[str, Dict]:
        """
        批量获取实时行情
        腾讯批量API: qt.gtimg.cn/q=sh600519,sz000001,...
        """
        result = {}
        
        # 每批50只
        batch_size = 50
        for i in range(0, len(codes), batch_size):
            batch = codes[i:i+batch_size]
            codes_str = ','.join(batch)
            
            try:
                url = f"https://qt.gtimg.cn/q={codes_str}"
                resp = self.session.get(url, timeout=5)
                
                # 解析响应
                for code in batch:
                    if f'v_{code}=' in resp.text:
                        idx = resp.text.find(f'v_{code}=')
                        start = resp.text.find('"', idx) + 1
                        end = resp.text.find('"', start)
                        data = resp.text[start:end]
                        
                        if '~' in data:
                            parts = data.split('~')
                            result[code] = {
                                'price': float(parts[3]) if parts[3] else 0,
                                'change': float(parts[31]) if parts[31] else 0,
                                'change_pct': float(parts[32]) if parts[32] else 0,
                                'volume': int(parts[36]) if parts[36] else 0,
                                'market_cap': float(parts[45]) if parts[45] else 0,
                                'float_cap': float(parts[46]) if parts[46] else 0,
                            }
                
                time.sleep(0.1)  # 避免请求过快
                
            except Exception as e:
                log.warning(f"批量获取失败: {e}")
        
        return result
    
    def get_sector_info(self, code: str) -> Optional[Dict]:
        """
        获取板块信息
        使用东方财富搜索API
        """
        try:
            # 从股票代码提取
            secid = code[2:]  # 600519
            
            url = f"https://searchapi.eastmoney.com/api/suggest/get?input={secid}&type=14&count=1"
            resp = self.session.get(url, timeout=5)
            data = resp.json()
            
            if data.get('QuotationCodeTable', {}).get('Data'):
                item = data['QuotationCodeTable']['Data'][0]
                return {
                    'code': code,
                    'name': item.get('Name', ''),
                }
        except Exception as e:
            log.debug(f"获取板块信息失败 {code}: {e}")
        
        return None
    
    def get_financial(self, code: str) -> Optional[Dict]:
        """
        获取财务数据
        使用东方财富财务API
        """
        try:
            secid = f"1.{code[2:]}" if code.startswith('sh') else f"0.{code[2:]}"
            url = f"https://emweb.securities.eastmoney.com/PC_HSF10/FinanceAnalysis/GetMainFinanceAjax?code={secid}"
            
            resp = self.session.get(url, timeout=5)
            data = resp.json()
            
            if data.get('data'):
                d = data['data']
                return {
                    'revenue': d.get('totalRevenue', 0),
                    'profit': d.get('netProfit', 0),
                    'roe': d.get('roe', 0),
                    'gross_margin': d.get('grossProfitMargin', 0),
                }
        except Exception as e:
            log.debug(f"获取财务数据失败 {code}: {e}")
        
        return None
    
    def get_full_info(self, code: str) -> StockInfo:
        """获取完整股票信息"""
        info = StockInfo(code=code, name="")
        
        # 1. 实时数据
        realtime = self.get_realtime(code)
        if realtime:
            info.price = realtime.get('price', 0)
            info.change = realtime.get('change', 0)
            info.change_pct = realtime.get('change_pct', 0)
            info.volume = realtime.get('volume', 0)
            info.amount = realtime.get('amount', 0)
            info.market_cap = realtime.get('market_cap', 0)
            info.float_cap = realtime.get('float_cap', 0)
        
        # 2. 板块信息
        sector = self.get_sector_info(code)
        if sector:
            info.name = sector.get('name', '')
        
        # 3. 财务数据(可选，耗时长)
        # financial = self.get_financial(code)
        
        return info


# ============ 数据库操作 ============

def update_stock_info(code: str) -> bool:
    """
    更新单个股票信息到数据库
    使用db_pool连接池
    """
    api = StockInfoAPI()
    
    # 获取实时数据
    realtime = api.get_realtime(code)
    if not realtime:
        return False
    
    # 获取板块信息
    sector = api.get_sector_info(code)
    
    # 更新数据库
    pool = get_pool(DB_PATH)
    conn = pool.get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            UPDATE master_stocks
            SET sector = ?, industry = ?, updated_at = datetime('now')
            WHERE stock_code = ?
        """, (
            sector.get('name', '') if sector else '',
            sector.get('industry', '') if sector else '',
            code
        ))
        conn.commit()
        return True
    except Exception as e:
        log.error(f"更新失败 {code}: {e}")
        return False
    finally:
        pool.release_connection(conn)


def batch_update_stocks(codes: List[str], batch_size: int = 50) -> int:
    """
    批量更新股票信息
    返回: 更新成功的数量
    """
    api = StockInfoAPI()
    pool = get_pool(DB_PATH)
    
    updated = 0
    total = len(codes)
    
    log.info(f"开始批量更新 {total} 只股票...")
    
    for i in range(0, total, batch_size):
        batch = codes[i:i+batch_size]
        
        # 批量获取实时数据
        realtime_data = api.get_batch_realtime(batch)
        
        # 批量更新数据库
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        for code in batch:
            if code in realtime_data:
                data = realtime_data[code]
                try:
                    cursor.execute("""
                        UPDATE master_stocks
                        SET sector = ?, updated_at = datetime('now')
                        WHERE stock_code = ?
                    """, (data.get('name', ''), code))
                    updated += 1
                except Exception as e:
                    log.warning(f"更新失败 {code}: {e}")
        
        conn.commit()
        pool.release_connection(conn)
        
        log.info(f"进度: {min(i+batch_size, total)}/{total}")
        time.sleep(0.2)
    
    log.success(f"完成! 更新了 {updated}/{total} 只股票")
    return updated


# ============ 查询接口 ============

def get_stock_detail(code: str) -> Optional[Dict]:
    """
    获取股票详细信息
    返回字典格式，方便其他模块调用
    """
    api = StockInfoAPI()
    info = api.get_full_info(code)
    
    return {
        'code': info.code,
        'name': info.name,
        'price': info.price,
        'change': info.change,
        'change_pct': info.change_pct,
        'volume': info.volume,
        'market_cap': info.market_cap,
        'float_cap': info.float_cap,
        'sector': info.sector,
        'industry': info.industry,
    }


def format_notification(code: str, name: str, price: float, 
                       score: float, strategy: str) -> str:
    """
    格式化通知消息
    包含完整的股票信息
    """
    detail = get_stock_detail(code)
    
    if not detail:
        return f"⚠️ {code} {name} 无数据"
    
    lines = [
        "=" * 40,
        f"📊 {code} {name}",
        "=" * 40,
        f"💰 价格: ¥{detail['price']:.2f} ({detail['change_pct']:+.2f}%)",
        f"📈 成交量: {detail['volume']/1e6:.1f}万手",
        f"🏢 总市值: {detail['market_cap']:.1f}亿",
        f"📊 流通市值: {detail['float_cap']:.1f}亿",
        f"🎯 评分: {score:.1f}",
        f"📋 策略: {strategy}",
        "=" * 40,
    ]
    
    return "\n".join(lines)


# ============ 主程序 ============

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='股票信息工具')
    parser.add_argument('--code', type=str, help='股票代码')
    parser.add_argument('--batch', action='store_true', help='批量更新')
    parser.add_argument('--limit', type=int, default=100, help='批量更新数量')
    
    args = parser.parse_args()
    
    if args.code:
        # 单只股票
        info = get_stock_detail(args.code)
        print(format_notification(
            info['code'], info['name'], info['price'],
            0, '查询'
        ))
    elif args.batch:
        # 批量更新
        pool = get_pool(DB_PATH)
        conn = pool.get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT stock_code FROM master_stocks LIMIT {args.limit}')
        codes = [r[0] for r in cursor.fetchall()]
        pool.release_connection(conn)
        
        batch_update_stocks(codes)
    else:
        print("Usage:")
        print("  python3 stock_info.py --code sh600519")
        print("  python3 stock_info.py --batch --limit 100")
