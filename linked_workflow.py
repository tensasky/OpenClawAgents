#!/usr/bin/env python3
"""
联动选股系统 - 统一工作流
西风(热点板块) → 东风(板块选股) → 南风(策略评分) → 红中(信号) → 发财(交易)

使用统一架构: db_pool + agent_logger
"""

import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

# 统一架构
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from utils.db_pool import get_pool
from utils.agent_logger import get_logger

log = get_logger("联动选股")

# 配置路径
BASE_DIR = Path(__file__).parent.parent
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_DB = BASE_DIR / "xifeng/data/hot_sectors.db"
DONGFENG_DB = BASE_DIR / "dongfeng/data/candidates.db"
NANFENG_DB = BASE_DIR / "nanfeng/data/strategies.db"
HONGZHONG_DB = BASE_DIR / "hongzhong/data/signals_v3.db"
FACAI_DB = BASE_DIR / "facai/data/portfolio.db"


# ============ 数据模型 ============

@dataclass
class SectorData:
    """板块数据"""
    sector_name: str
    change_pct: float
    volume_ratio: float
    stock_count: int
    lead_stock: str = ""  # 领涨股票


@dataclass
class StockCandidate:
    """候选股票"""
    code: str
    name: str
    sector: str
    
    # 筛选条件
    volume_ratio: float = 0  # 量比
    amplitude: float = 0      # 振幅
    net_inflow: float = 0    # 净流入
    
    # 评分
    score: float = 0


@dataclass
class TradeSignal:
    """交易信号"""
    code: str
    name: str
    price: float
    score: float
    strategy: str
    entry_price: float = 0
    stop_loss: float = 0


# ============ Step 1: 西风 - 热点板块 ============

class XiFeng:
    """西风 - 热点板块识别"""
    
    def get_hot_sectors(self, limit: int = 5) -> List[SectorData]:
        """获取热点板块"""
        conn = sqlite3.connect(str(BEIFENG_DB))
        cursor = conn.cursor()
        
        # 从分钟数据聚合板块涨幅
        # 简化：使用有分钟数据的股票作为热点
        cursor.execute("""
            SELECT stock_code, MAX(timestamp) as latest
            FROM minute
            WHERE timestamp LIKE ?
            GROUP BY stock_code
            ORDER BY latest DESC
            LIMIT ?
        """, (f"{datetime.now().strftime('%Y-%m-%d')}%", limit))
        
        sectors = []
        for i, row in enumerate(cursor.fetchall()):
            sectors.append(SectorData(
                sector_name=f"热点{i+1}",
                change_pct=3.0 + i * 0.5,
                volume_ratio=2.0 + i * 0.3,
                stock_count=50 + i * 10,
                lead_stock=row[0]
            ))
        
        conn.close()
        return sectors


# ============ Step 2: 东风 - 板块选股 ============

class DongFeng:
    """东风 - 板块内筛选活跃股"""
    
    def __init__(self, sectors: List[SectorData]):
        self.sectors = sectors
    
    def scan_sector_stocks(self, sector: SectorData, limit: int = 10) -> List[StockCandidate]:
        """扫描板块内活跃股票"""
        pool = get_pool(BEIFENG_DB)
        conn = pool.get_connection()
        cursor = conn.cursor()
        
        # 从分钟数据筛选活跃股票
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT 
                stock_code,
                MIN(timestamp) as open_time,
                MAX(high) as high,
                MIN(low) as low,
                MAX(close) as close,
                SUM(volume) as total_vol
            FROM minute
            WHERE timestamp LIKE ?
            GROUP BY stock_code
            HAVING total_vol > 0
            ORDER BY total_vol DESC
            LIMIT ?
        """, (f"{today}%", limit))
        
        candidates = []
        
        for row in cursor.fetchall():
            code = row[0]
            high = row[3]
            low = row[4]
            close = row[5]
            
            # 计算振幅
            amplitude = ((high - low) / low * 100) if low > 0 else 0
            
            # 计算量比(简化:用成交量替代)
            volume_ratio = 2.5  # 简化计算
            
            # 筛选条件: 量比>2 或 振幅>3
            if volume_ratio > 2 or amplitude > 3:
                candidates.append(StockCandidate(
                    code=code,
                    name=code,
                    sector=sector.sector_name,
                    volume_ratio=volume_ratio,
                    amplitude=amplitude,
                    net_inflow=0  # 简化
                ))
        
        pool.release_connection(conn)
        return candidates
    
    def run(self) -> List[StockCandidate]:
        """执行板块筛选"""
        all_candidates = []
        
        for sector in self.sectors:
            log.info(f"扫描板块: {sector.sector_name}")
            stocks = self.scan_sector_stocks(sector)
            all_candidates.extend(stocks)
            log.info(f"  找到 {len(stocks)} 只活跃股")
        
        # 排序
        all_candidates.sort(key=lambda x: x.volume_ratio + x.amplitude, reverse=True)
        
        return all_candidates[:20]  # 最多20只


# ============ Step 3: 南风 - 策略评分 ============

class NanFeng:
    """南风 - 策略评分"""
    
    def __init__(self, candidates: List[StockCandidate]):
        self.candidates = candidates
    
    def calculate_score(self, stock: StockCandidate) -> float:
        """计算综合评分"""
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
        
        return min(score, 100)
    
    def run(self) -> List[StockCandidate]:
        """执行评分"""
        for stock in self.candidates:
            stock.score = self.calculate_score(stock)
        
        # 排序返回
        self.candidates.sort(key=lambda x: x.score, reverse=True)
        
        return [s for s in self.candidates if s.score >= 60]


# ============ Step 4: 红中 - 交易信号 ============

class HongZhong:
    """红中 - 生成交易信号"""
    
    def __init__(self, candidates: List[StockCandidate]):
        self.candidates = candidates
    
    def create_signal(self, stock: StockCandidate) -> TradeSignal:
        """创建交易信号"""
        return TradeSignal(
            code=stock.code,
            name=stock.name,
            price=0,  # 实时获取
            score=stock.score,
            strategy="联动选股策略",
            entry_price=0,
            stop_loss=0
        )
    
    def run(self) -> List[TradeSignal]:
        """生成信号"""
        signals = []
        
        for stock in self.candidates[:10]:  # 最多10只
            signal = self.create_signal(stock)
            signals.append(signal)
        
        return signals


# ============ Step 5: 发财 - 模拟交易 ============

class FaCai:
    """发财 - 执行交易"""
    
    def __init__(self, signals: List[TradeSignal]):
        self.signals = signals
    
    def execute_buy(self, signal: TradeSignal) -> bool:
        """执行买入"""
        # 简化实现
        log.info(f"买入信号: {signal.code} {signal.name} 评分:{signal.score}")
        return True
    
    def run(self) -> int:
        """执行交易"""
        executed = 0
        
        for signal in self.signals:
            if self.execute_buy(signal):
                executed += 1
        
        return executed


# ============ 主流程 ============

class LinkedWorkflow:
    """联动选股工作流"""
    
    def __init__(self):
        self.step1_sectors = []
        self.step2_candidates = []
        self.step3_scored = []
        self.step4_signals = []
        self.step5_executed = 0
    
    def run(self) -> Dict:
        """执行完整工作流"""
        log.step("=" * 50)
        log.step("🚀 联动选股系统启动")
        log.step("=" * 50)
        
        # Step 1: 西风 - 热点板块
        log.step("Step 1: 西风 - 热点板块识别")
        xifeng = XiFeng()
        self.step1_sectors = xifeng.get_hot_sectors(limit=5)
        log.info(f"  发现 {len(self.step1_sectors)} 个热点板块")
        
        # Step 2: 东风 - 板块选股
        log.step("Step 2: 东风 - 板块内筛选")
        dongfeng = DongFeng(self.step1_sectors)
        self.step2_candidates = dongfeng.run()
        log.info(f"  筛选出 {len(self.step2_candidates)} 只候选股")
        
        # Step 3: 南风 - 策略评分
        log.step("Step 3: 南风 - 策略评分")
        nanfeng = NanFeng(self.step2_candidates)
        self.step3_scored = nanfeng.run()
        log.info(f"  评分合格 {len(self.step3_scored)} 只")
        
        # Step 4: 红中 - 交易信号
        log.step("Step 4: 红中 - 生成信号")
        hongzhong = HongZhong(self.step3_scored)
        self.step4_signals = hongzhong.run()
        log.info(f"  生成 {len(self.step4_signals)} 个信号")
        
        # Step 5: 发财 - 执行交易
        log.step("Step 5: 发财 - 执行交易")
        facai = FaCai(self.step4_signals)
        self.step5_executed = facai.run()
        log.success(f"  执行 {self.step5_executed} 笔交易")
        
        # 返回结果
        return {
            'sectors': len(self.step1_sectors),
            'candidates': len(self.step2_candidates),
            'scored': len(self.step3_scored),
            'signals': len(self.step4_signals),
            'executed': self.step5_executed
        }


def run_linked_workflow():
    """运行联动选股"""
    workflow = LinkedWorkflow()
    result = workflow.run()
    
    log.success("=" * 50)
    log.success(f"✅ 联动选股完成: {result}")
    log.success("=" * 50)
    
    return result


if __name__ == '__main__':
    run_linked_workflow()
