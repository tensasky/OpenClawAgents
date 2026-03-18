#!/usr/bin/env python3
"""
风险控制模块 - ATR动态止损 + 组合风控
"""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.db_pool import get_pool
from utils.agent_logger import get_logger

log = get_logger("风控")

# 配置
DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

# 风控参数
ATR_PERIOD = 14  # ATR周期
ATR_MULTIPLIER = 2.0  # ATR倍数
SECTOR_LIMIT = 0.30  # 单行业30%上限
DAILY_TRADE_LIMIT = 5  # 每日最多5笔
STRATEGY_INITIAL_CAPITAL = 100000  # 每策略10万


class ATRCalculator:
    """ATR计算器"""
    
    def __init__(self):
        self.pool = get_pool(DB_PATH)
    
    def get_daily_data(self, stock_code: str, days: int = 20) -> List[Dict]:
        """获取历史日线数据"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT timestamp, open, high, low, close
            FROM daily
            WHERE stock_code = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (stock_code, days))
        
        data = []
        for row in cursor.fetchall():
            data.append({
                'date': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4]
            })
        
        self.pool.release_connection(conn)
        
        # 按时间正序
        return list(reversed(data))
    
    def calculate_atr(self, stock_code: str, period: int = ATR_PERIOD) -> Optional[float]:
        """计算ATR (Average True Range)"""
        data = self.get_daily_data(stock_code, period + 1)
        
        if len(data) < period + 1:
            log.warning(f"数据不足，无法计算ATR: {stock_code}")
            return None
        
        tr_list = []
        for i in range(1, len(data)):
            high = data[i]['high']
            low = data[i]['low']
            prev_close = data[i-1]['close']
            
            # True Range = max(H-L, |H-PC|, |L-PC|)
            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            tr_list.append(tr)
        
        if not tr_list:
            return None
        
        atr = sum(tr_list) / len(tr_list)
        return atr
    
    def calculate_dynamic_stop_loss(
        self, 
        stock_code: str, 
        current_price: float,
        highest_price: float,
        k: float = ATR_MULTIPLIER
    ) -> float:
        """计算动态止损价"""
        atr = self.calculate_atr(stock_code)
        
        if atr is None:
            # 数据不足，使用固定止损
            return current_price * 0.95
        
        # 动态止损 = 最高价 - k * ATR
        stop_loss = highest_price - (k * atr)
        
        # 不能低于当前价格的90%
        return max(stop_loss, current_price * 0.90)


class PortfolioRiskController:
    """组合风险控制器"""
    
    def __init__(self, portfolio_path: Path = None):
        if portfolio_path is None:
            portfolio_path = Path.home() / "Documents/OpenClawAgents/facai/data/portfolio.db"
        
        self.pool = get_pool(portfolio_path)
    
    def get_positions(self) -> List[Dict]:
        """获取所有持仓"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, symbol, name, quantity, avg_price, current_price, 
                   highest_price, stop_loss, entry_time
            FROM positions
        """)
        
        positions = []
        for row in cursor.fetchall():
            positions.append({
                'id': row[0],
                'symbol': row[1],
                'name': row[2],
                'quantity': row[3],
                'avg_price': row[4],
                'current_price': row[5],
                'highest_price': row[6],
                'stop_loss': row[7],
                'entry_time': row[8]
            })
        
        self.pool.release_connection(conn)
        return positions
    
    def get_sector_exposure(self, stock_code: str = None) -> Dict[str, float]:
        """获取行业暴露度"""
        # 简化: 从股票代码推断市场(实际应从数据库读取行业)
        # 上海(sh) -> 主板, 深圳(sz) -> 中小板/创业板
        
        positions = self.get_positions()
        
        total_value = sum(p['quantity'] * p['current_price'] for p in positions)
        
        if total_value == 0:
            return {}
        
        # 按市场分组(简化)
        sector_map = {}
        for p in positions:
            sector = 'SH' if p['symbol'].startswith('sh') else 'SZ'
            value = p['quantity'] * p['current_price']
            sector_map[sector] = sector_map.get(sector, 0) + value
        
        # 转为百分比
        return {k: v/total_value for k, v in sector_map.items()}
    
    def check_sector_limit(self, stock_code: str) -> bool:
        """检查行业限制"""
        # 简化: 假设新股票属于其市场
        new_sector = 'SH' if stock_code.startswith('sh') else 'SZ'
        
        exposure = self.get_sector_exposure()
        current_exposure = exposure.get(new_sector, 0)
        
        if current_exposure >= SECTOR_LIMIT:
            log.warning(f"行业限制: {new_sector}已达{current_exposure:.1%}")
            return False
        
        return True
    
    def get_today_trades_count(self) -> int:
        """获取今日交易次数"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        cursor.execute("""
            SELECT COUNT(*) FROM trades
            WHERE timestamp LIKE ?
        """, (f"{today}%",))
        
        count = cursor.fetchone()[0]
        
        self.pool.release_connection(conn)
        return count
    
    def check_daily_limit(self) -> bool:
        """检查每日交易限额"""
        count = self.get_today_trades_count()
        
        if count >= DAILY_TRADE_LIMIT:
            log.warning(f"每日交易限额: 今日已{count}笔，达到上限{DAILY_TRADE_LIMIT}")
            return False
        
        return True
    
    def get_strategy_cash(self, strategy_name: str) -> float:
        """获取策略可用资金"""
        # 简化: 从信号表读取策略初始资金
        # 实际应该从专门的策略账户表读取
        return STRATEGY_INITIAL_CAPITAL


class StrategyPortfolio:
    """策略资金池"""
    
    def __init__(self, strategy_name: str, initial_capital: float = STRATEGY_INITIAL_CAPITAL):
        self.strategy_name = strategy_name
        self.initial_capital = initial_capital
        self.pool = get_pool(
            Path.home() / "Documents/OpenClawAgents/facai/data/portfolio.db"
        )
    
    def get_available_cash(self) -> float:
        """获取策略可用资金"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        # 查找该策略最近的信号买入
        # 简化: 使用总账户现金
        cursor.execute("SELECT cash_balance FROM account LIMIT 1")
        row = cursor.fetchone()
        
        cash = row[0] if row else self.initial_capital
        
        # 减去已持仓成本
        cursor.execute("SELECT SUM(quantity * avg_price) FROM positions")
        row = cursor.fetchone()
        positions_cost = row[0] if row and row[0] else 0
        
        self.pool.release_connection(conn)
        
        return max(0, cash - positions_cost * 0.5)  # 预留一半仓位
    
    def calculate_position_size(self, price: float, risk_pct: float = 0.02) -> int:
        """计算仓位"""
        available = self.get_available_cash()
        
        # 按风险比例计算
        max_position = available * 0.5  # 单股最大50%
        
        # 100股整数
        quantity = int(max_position / price / 100) * 100
        
        return max(0, quantity)
    
    def can_buy(self, price: float) -> bool:
        """是否可以买入"""
        return self.get_available_cash() >= price * 100


# ============ 风险检查主函数 ============

def check_buy_risk(signal: Dict) -> tuple[bool, str]:
    """
    综合风险检查
    返回: (是否可买, 原因)
    """
    # 1. 每日限额检查
    controller = PortfolioRiskController()
    if not controller.check_daily_limit():
        return False, "每日交易限额已达上限"
    
    # 2. 行业限制检查
    if not controller.check_sector_limit(signal.get('code', '')):
        return False, "行业仓位已达30%上限"
    
    # 3. 策略资金检查
    strategy = signal.get('strategy', 'default')
    sp = StrategyPortfolio(strategy)
    if not sp.can_buy(signal.get('entry_price', 0)):
        return False, f"策略{strategy}资金不足"
    
    return True, "通过"


def update_stop_loss(symbol: str, current_price: float, highest_price: float) -> Optional[float]:
    """
    更新动态止损价
    """
    atr_calc = ATRCalculator()
    new_stop_loss = atr_calc.calculate_dynamic_stop_loss(
        symbol, current_price, highest_price
    )
    
    log.info(f"动态止损更新: {symbol} {highest_price:.2f} -> {new_stop_loss:.2f}")
    return new_stop_loss


# ============ 测试 ============

if __name__ == '__main__':
    print("=== ATR计算测试 ===")
    
    atr = ATRCalculator()
    
    # 测试ATR计算
    test_stocks = ['sh600519', 'sh000001', 'sz000001']
    for code in test_stocks:
        atr_val = atr.calculate_atr(code)
        if atr_val:
            print(f"{code} ATR: {atr_val:.2f}")
    
    print("\n=== 风险检查测试 ===")
    
    # 测试风险检查
    test_signal = {
        'code': 'sh600519',
        'name': '贵州茅台',
        'strategy': '趋势跟踪',
        'entry_price': 1500.0
    }
    
    can_buy, reason = check_buy_risk(test_signal)
    print(f"买入检查: {can_buy} - {reason}")
    
    print("\n=== 行业暴露度 ===")
    controller = PortfolioRiskController()
    print(controller.get_sector_exposure())
    
    print("\n=== 今日交易次数 ===")
    print(f"今日交易: {controller.get_today_trades_count()}笔")
