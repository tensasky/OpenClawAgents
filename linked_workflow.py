#!/usr/bin/env python3
"""
联动选股系统 - 优化版
西风(热点板块) → 东风(板块选股) → 南风(策略评分) → 红中(信号) → 发财(交易)

优化:
- 读取西风热点板块数据
- 从数据库获取股票名称
"""

import sqlite3
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

# 统一架构
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils.db_pool import get_pool
from utils.agent_logger import get_logger
from utils.stock_info import get_stock_detail

log = get_logger("联动选股")

# 配置路径
DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HOT_SPOTS_PATH = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"


# ============ 数据模型 ============

@dataclass
class SectorData:
    """板块数据"""
    sector_name: str
    heat_score: float
    change_pct: float
    stocks: List[Dict]  # [{"code": "xxx", "name": "yyy", "weight": 10}]


@dataclass
class StockCandidate:
    """候选股票"""
    code: str
    name: str
    sector: str
    
    # 筛选条件
    volume_ratio: float = 0
    amplitude: float = 0
    net_inflow: float = 0
    
    # 评分
    score: float = 0


# ============ Step 1: 西风 - 热点板块 ============

def load_hot_sectors(limit: int = 5) -> List[SectorData]:
    """加载西风热点板块"""
    try:
        with open(HOT_SPOTS_PATH) as f:
            data = json.load(f)
        
        sectors = []
        for item in data.get('summary', [])[:limit]:
            # 获取板块内领涨股
            leading = item.get('leading_stocks', [])
            
            sectors.append(SectorData(
                sector_name=item.get('sector', ''),
                heat_score=item.get('heat_score', 0),
                change_pct=item.get('sentiment', 0) * 100,
                stocks=leading
            ))
        
        log.info(f"西风: 加载 {len(sectors)} 个热点板块")
        return sectors
        
    except Exception as e:
        log.warning(f"加载热点板块失败: {e}")
        return []


# ============ Step 2: 东风 - 板块选股 ============

def get_stock_from_db(code: str) -> str:
    """从数据库获取股票名称"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        cursor.execute('SELECT stock_name FROM master_stocks WHERE stock_code = ?', (code,))
        row = cursor.fetchone()
        conn.close()
        return row[0] if row else code
    except:
        return code


def scan_sector_stocks(sector: SectorData, limit: int = 20) -> List[StockCandidate]:
    """扫描板块内活跃股票"""
    pool = get_pool(DB_PATH)
    conn = pool.get_connection()
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 获取板块内股票(从领涨股票开始)
    candidates = []
    for stock_info in sector.stocks[:10]:
        code = stock_info.get('code', '')
        if not code:
            continue
        
        # 格式化股票代码
        if len(code) == 6:
            code = 'sh' + code if code.startswith('6') else 'sz' + code
        
        # 获取实时数据
        name = get_stock_from_db(code)
        
        # 计算筛选条件
        candidates.append(StockCandidate(
            code=code,
            name=name,
            sector=sector.sector_name,
            volume_ratio=2.5,  # 简化
            amplitude=sector.change_pct,  # 用板块涨幅
            net_inflow=stock_info.get('weight', 0) * 1000000  # 模拟
        ))
    
    pool.release_connection(conn)
    return candidates


# ============ Step 3: 南风 - 策略评分 ============

def calculate_strategy_score(stock: StockCandidate) -> float:
    """计算策略评分"""
    score = 50.0
    
    # 量比加分
    if stock.volume_ratio > 3:
        score += 15
    elif stock.volume_ratio > 2:
        score += 10
    
    # 振幅加分
    if stock.amplitude > 5:
        score += 15
    elif stock.amplitude > 3:
        score += 10
    
    # 资金流向加分
    if stock.net_inflow > 0:
        score += 10
    
    # 板块热度加分
    score += min(10, stock.amplitude * 2)
    
    return min(score, 100)


# ============ Step 4: 红中 - 生成信号 ============

def create_trade_signal(stock: StockCandidate) -> Dict:
    """创建交易信号"""
    detail = get_stock_detail(stock.code)
    
    price = detail.get('price', 0) if detail else 0
    
    return {
        'code': stock.code,
        'name': stock.name,
        'price': price,
        'score': stock.score,
        'strategy': '联动选股策略',
        'sector': stock.sector,
        'entry_price': price * 1.02,  # 开盘+2%
        'stop_loss': price * 0.95  # 止损-5%
    }


# ============ 主流程 ============

def run_linked_workflow() -> Dict:
    """运行联动选股"""
    log.step("=" * 50)
    log.step("🚀 联动选股系统")
    log.step("=" * 50)
    
    # Step 1: 西风 - 热点板块
    log.step("Step 1: 西风 - 热点板块")
    sectors = load_hot_sectors(limit=5)
    log.info(f"  热点板块: {len(sectors)}")
    for s in sectors:
        log.info(f"    - {s.sector_name} (热度:{s.heat_score})")
    
    # Step 2: 东风 - 板块选股
    log.step("Step 2: 东风 - 板块选股")
    all_candidates = []
    for sector in sectors:
        candidates = scan_sector_stocks(sector)
        all_candidates.extend(candidates)
        log.info(f"    {sector.sector_name}: {len(candidates)}只")
    log.info(f"  共筛选: {len(all_candidates)}只")
    
    # Step 3: 南风 - 策略评分
    log.step("Step 3: 南风 - 策略评分")
    for stock in all_candidates:
        stock.score = calculate_strategy_score(stock)
    
    scored = [s for s in all_candidates if s.score >= 60]
    scored.sort(key=lambda x: x.score, reverse=True)
    log.info(f"  评分合格: {len(scored)}只")
    
    # Step 4: 红中 - 信号
    log.step("Step 4: 红中 - 信号")
    signals = []
    for stock in scored[:10]:
        signal = create_trade_signal(stock)
        signals.append(signal)
        log.info(f"    {signal['code']} {signal['name']} 评分:{signal['score']:.1f}")
    
    # Step 5: 发财 - 交易(简化)
    log.step("Step 5: 发财 - 执行")
    log.success(f"  可执行: {len(signals)}笔")
    
    result = {
        'sectors': len(sectors),
        'candidates': len(all_candidates),
        'scored': len(scored),
        'signals': len(signals)
    }
    
    log.success("=" * 50)
    log.success(f"✅ 完成: {result}")
    log.success("=" * 50)
    
    return result


if __name__ == '__main__':
    run_linked_workflow()
