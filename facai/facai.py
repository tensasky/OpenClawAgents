#!/usr/bin/env python3
"""
发财 (The Trader) - 模拟交易与资产管理专家
模拟交易执行、动态风控、资产管理
"""

import json
import logging
import sqlite3
import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# 输入文件
HONGZHONG_TOP3 = Path.home() / "Documents/OpenClawAgents/hongzhong/data/top3.json"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

# 输出文件
PORTFOLIO_DB = DATA_DIR / "portfolio.db"
TRADES_FILE = DATA_DIR / "trades.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"facai_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("发财")

# 初始资金
INITIAL_CAPITAL = 100000.00
MAX_POSITION_PCT = 0.50  # 单只股票最大50%
SELL_FEE_RATE = 0.0003  # 卖出手续费万分之三


def is_trading_time() -> bool:
    """检查当前是否为可交易时间（排除集合竞价 9:15-9:25）"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    time_val = hour * 100 + minute
    
    # 上午交易时间：9:30-11:30
    # 下午交易时间：13:00-15:00
    # 排除集合竞价：9:15-9:25
    if 930 <= time_val <= 1130:
        return True
    if 1300 <= time_val <= 1500:
        return True
    return False


def is_auction_time() -> bool:
    """检查是否为集合竞价时间（9:15-9:25）"""
    now = datetime.now()
    hour = now.hour
    minute = now.minute
    time_val = hour * 100 + minute
    return 915 <= time_val <= 925


@dataclass
class Position:
    """持仓信息"""
    symbol: str
    name: str
    quantity: int
    avg_price: float
    current_price: float
    stop_loss: float
    highest_price: float  # 用于追踪止损
    entry_time: str
    entry_logic: str
    sector: str
    sector_heat: str


class PortfolioManager:
    """账户管理器"""
    
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        
        # 持仓表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT UNIQUE NOT NULL,
                name TEXT,
                quantity INTEGER,
                avg_price REAL,
                current_price REAL,
                stop_loss REAL,
                highest_price REAL,
                entry_time TIMESTAMP,
                entry_logic TEXT,
                sector TEXT,
                sector_heat TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 交易记录表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                action TEXT NOT NULL,
                symbol TEXT NOT NULL,
                name TEXT,
                price REAL,
                quantity INTEGER,
                total_amount REAL,
                fee REAL DEFAULT 0,
                logic TEXT,
                total_assets REAL,
                cash_balance REAL
            )
        """)
        
        # 资金表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS account (
                id INTEGER PRIMARY KEY,
                initial_capital REAL DEFAULT 100000.00,
                cash_balance REAL DEFAULT 100000.00,
                total_assets REAL DEFAULT 100000.00,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 初始化账户
        cursor.execute("INSERT OR IGNORE INTO account (id) VALUES (1)")
        
        conn.commit()
        conn.close()
        logger.info("账户数据库初始化完成")
    
    def get_account(self) -> Dict:
        """获取账户信息"""
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT initial_capital, cash_balance, total_assets FROM account WHERE id = 1")
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'initial_capital': row[0],
                'cash_balance': row[1],
                'total_assets': row[2]
            }
        return {'initial_capital': INITIAL_CAPITAL, 'cash_balance': INITIAL_CAPITAL, 'total_assets': INITIAL_CAPITAL}
    
    def get_positions(self) -> List[Position]:
        """获取当前持仓"""
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM positions")
        rows = cursor.fetchall()
        conn.close()
        
        positions = []
        for row in rows:
            positions.append(Position(
                symbol=row[1],
                name=row[2],
                quantity=row[3],
                avg_price=row[4],
                current_price=row[5] or row[4],
                stop_loss=row[6],
                highest_price=row[7] or row[4],
                entry_time=row[8],
                entry_logic=row[9],
                sector=row[10],
                sector_heat=row[11]
            ))
        return positions
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """获取单只股票持仓"""
        positions = self.get_positions()
        for p in positions:
            if p.symbol == symbol:
                return p
        return None
    
    def buy(self, symbol: str, name: str, price: float, score: float, 
            sector: str, sector_heat: str, signals: List[str]) -> bool:
        """执行买入"""
        # 检查交易时间
        if is_auction_time():
            logger.warning(f"集合竞价时间(9:15-9:25)不能买入 {symbol}")
            return False
        
        if not is_trading_time():
            logger.warning(f"非交易时间不能买入 {symbol}")
            return False
        
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        
        try:
            # 获取账户资金
            account = self.get_account()
            cash = account['cash_balance']
            
            # 计算买入金额（不超过现金的50%，且单只股票不超过总资产的50%）
            max_position_value = account['total_assets'] * MAX_POSITION_PCT
            buy_amount = min(cash * 0.5, max_position_value)
            
            if buy_amount < 1000:  # 最小买入金额
                logger.warning(f"资金不足，跳过买入 {symbol}")
                return False
            
            quantity = int(buy_amount / price / 100) * 100  # 100股整数
            if quantity < 100:
                logger.warning(f"计算股数不足100，跳过买入 {symbol}")
                return False
            
            total_cost = quantity * price
            
            # 检查是否已有持仓
            existing = self.get_position(symbol)
            if existing:
                # 加仓逻辑（简化：不处理）
                logger.info(f"已有持仓 {symbol}，跳过")
                return False
            
            # 计算止损价（-5%）
            stop_loss = price * 0.95
            
            # 记录持仓
            cursor.execute("""
                INSERT INTO positions 
                (symbol, name, quantity, avg_price, current_price, stop_loss, highest_price, 
                 entry_time, entry_logic, sector, sector_heat)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, name, quantity, price, price, stop_loss, price,
                datetime.now().isoformat(),
                f"南风打分{score}，{'|'.join(signals[:3])}，{sector}板块热度{sector_heat}",
                sector, sector_heat
            ))
            
            # 更新资金
            new_cash = cash - total_cost
            new_assets = account['total_assets']  # 买入时总资产不变
            cursor.execute("UPDATE account SET cash_balance = ?, total_assets = ?, updated_at = ? WHERE id = 1",
                          (new_cash, new_assets, datetime.now().isoformat()))
            
            # 记录交易
            cursor.execute("""
                INSERT INTO trades (action, symbol, name, price, quantity, total_amount, logic, total_assets, cash_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('BUY', symbol, name, price, quantity, total_cost,
                  f"南风{score}分，{sector}({sector_heat})", new_assets, new_cash))
            
            conn.commit()
            logger.info(f"💰 买入成功: {symbol}({name}) {quantity}股 @ ¥{price}，止损¥{stop_loss:.2f}")
            return True
            
        except Exception as e:
            logger.error(f"买入失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def sell(self, symbol: str, price: float, reason: str) -> bool:
        """执行卖出（含手续费）"""
        # 检查交易时间
        if is_auction_time():
            logger.warning(f"集合竞价时间(9:15-9:25)不能卖出 {symbol}")
            return False
        
        if not is_trading_time():
            logger.warning(f"非交易时间不能卖出 {symbol}")
            return False
        
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        
        try:
            position = self.get_position(symbol)
            if not position:
                logger.warning(f"没有持仓 {symbol}，无法卖出")
                return False
            
            quantity = position.quantity
            gross_amount = quantity * price
            
            # 计算手续费（万分之三）
            fee = gross_amount * SELL_FEE_RATE
            net_amount = gross_amount - fee
            
            # 计算盈亏（扣除手续费）
            cost = position.avg_price * quantity
            gross_profit = gross_amount - cost
            net_profit = net_amount - cost
            profit_pct = (net_amount / cost - 1) * 100
            
            # 删除持仓
            cursor.execute("DELETE FROM positions WHERE symbol = ?", (symbol,))
            
            # 更新资金
            account = self.get_account()
            new_cash = account['cash_balance'] + net_amount
            
            # 计算新总资产
            new_assets = new_cash
            for pos in self.get_positions():
                if pos.symbol != symbol:
                    new_assets += pos.quantity * pos.current_price
            
            cursor.execute("UPDATE account SET cash_balance = ?, total_assets = ?, updated_at = ? WHERE id = 1",
                          (new_cash, new_assets, datetime.now().isoformat()))
            
            # 记录交易（包含手续费）
            cursor.execute("""
                INSERT INTO trades (action, symbol, name, price, quantity, total_amount, fee, logic, total_assets, cash_balance)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('SELL', symbol, position.name, price, quantity, net_amount, fee,
                  f"{reason}，手续费¥{fee:.2f}", new_assets, new_cash))
            
            conn.commit()
            logger.info(f"💰 卖出成功: {symbol}({position.name}) {quantity}股 @ ¥{price}，"
                       f"毛盈亏{gross_profit:+.2f}，手续费¥{fee:.2f}，净盈亏{net_profit:+.2f}({profit_pct:+.2f}%)，原因:{reason}")
            return True
            
        except Exception as e:
            logger.error(f"卖出失败: {e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def update_prices(self):
        """更新持仓价格（从北风数据库）"""
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        
        try:
            beifeng_conn = sqlite3.connect(BEIFENG_DB)
            beifeng_cursor = beifeng_conn.cursor()
            
            positions = self.get_positions()
            total_market_value = 0
            
            for pos in positions:
                # 获取最新价格
                beifeng_cursor.execute("""
                    SELECT close FROM kline_data 
                    WHERE stock_code = ? AND data_type = 'daily'
                    ORDER BY timestamp DESC LIMIT 1
                """, (pos.symbol,))
                row = beifeng_cursor.fetchone()
                
                if row:
                    current_price = row[0]
                    # 更新最高价（用于追踪止损）
                    new_high = max(pos.highest_price, current_price)
                    cursor.execute("""
                        UPDATE positions SET current_price = ?, highest_price = ?, updated_at = ?
                        WHERE symbol = ?
                    """, (current_price, new_high, datetime.now().isoformat(), pos.symbol))
                    
                    total_market_value += pos.quantity * current_price
            
            beifeng_conn.close()
            
            # 更新总资产
            account = self.get_account()
            new_assets = account['cash_balance'] + total_market_value
            cursor.execute("UPDATE account SET total_assets = ? WHERE id = 1", (new_assets,))
            
            conn.commit()
            logger.info(f"价格更新完成，当前总资产: ¥{new_assets:.2f}")
            
        except Exception as e:
            logger.error(f"更新价格失败: {e}")
        finally:
            conn.close()


class RiskController:
    """风控控制器"""
    
    def __init__(self, portfolio: PortfolioManager):
        self.portfolio = portfolio
    
    def check_trailing_stop(self, position: Position) -> Optional[str]:
        """检查追踪止损"""
        # 计算当前止损位
        # 初始止损 -5%，随股价上涨平移
        entry_price = position.avg_price
        highest = position.highest_price
        current = position.current_price
        
        # 计算盈利比例
        profit_pct = (highest / entry_price - 1) * 100
        
        # 动态止损位
        if profit_pct > 0:
            # 盈利后，止损位上移至买入价 + 盈利的一半
            trailing_stop = entry_price + (highest - entry_price) * 0.5
        else:
            trailing_stop = entry_price * 0.95
        
        if current < trailing_stop:
            return f"触发追踪止损(当前¥{current:.2f} < 止损位¥{trailing_stop:.2f})"
        
        return None
    
    def check_sentiment_exit(self, position: Position) -> Optional[str]:
        """检查情绪止盈（西风热点降级）"""
        if not XIFENG_HOTSPOTS.exists():
            return None
        
        try:
            with open(XIFENG_HOTSPOTS, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查该股票所属板块的热度
            for sector in data.get('hot_spots', []):
                sector_name = sector.get('sector', '')
                if sector_name == position.sector:
                    current_heat = sector.get('level', 'Low')
                    if position.sector_heat == 'High' and current_heat == 'Low':
                        return f"情绪止盈: {sector_name}热度从High降至Low"
                    break
        except Exception as e:
            logger.error(f"检查情绪止盈失败: {e}")
        
        return None
    
    def check_volatility_exit(self, position: Position) -> Optional[str]:
        """检查波动止损（ATR异常）"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            # 获取今日数据
            cursor.execute("""
                SELECT high, low, close FROM kline_data 
                WHERE stock_code = ? AND data_type = 'daily'
                ORDER BY timestamp DESC LIMIT 1
            """, (position.symbol,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                high, low, close = row
                amplitude = (high - low) / close * 100
                
                # 如果振幅超过8%且收盘价接近低点
                if amplitude > 8 and (close - low) / (high - low) < 0.3:
                    return f"波动止损: 振幅{amplitude:.1f}%异常放大且向下"
        except Exception as e:
            logger.error(f"检查波动止损失败: {e}")
        
        return None
    
    def run_risk_check(self) -> List[Tuple[str, str]]:
        """运行全面风控检查"""
        positions = self.portfolio.get_positions()
        sell_signals = []
        
        for pos in positions:
            # 检查各种风控条件
            reasons = [
                self.check_trailing_stop(pos),
                self.check_sentiment_exit(pos),
                self.check_volatility_exit(pos)
            ]
            
            for reason in reasons:
                if reason:
                    sell_signals.append((pos.symbol, reason))
                    break  # 一个股票只触发一个卖出理由
        
        return sell_signals


class FacaiTrader:
    """发财交易核心"""
    
    def __init__(self):
        self.portfolio = PortfolioManager()
        self.risk = RiskController(self.portfolio)
    
    def load_hongzhong_top3(self) -> List[Dict]:
        """加载红中Top3"""
        if not HONGZHONG_TOP3.exists():
            logger.warning(f"红中Top3文件不存在: {HONGZHONG_TOP3}")
            return []
        
        try:
            with open(HONGZHONG_TOP3, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get('stocks', [])
        except Exception as e:
            logger.error(f"加载红中Top3失败: {e}")
            return []
    
    def execute_buy(self):
        """执行买入（14:50-15:00）"""
        logger.info("=" * 60)
        logger.info("💰 发财执行买入策略...")
        logger.info("=" * 60)
        
        # 1. 获取红中Top3
        top3 = self.load_hongzhong_top3()
        if not top3:
            logger.warning("没有红中Top3数据，跳过买入")
            return
        
        # 2. 筛选符合条件的（分数>=8.5）
        candidates = [s for s in top3 if s.get('score', 0) >= 8.5]
        logger.info(f"红中Top3: {len(top3)}只，>=8.5分: {len(candidates)}只")
        
        # 3. 执行买入
        for stock in candidates:
            symbol = stock.get('code', '')
            name = stock.get('name', '')
            price = stock.get('price', 0)
            score = stock.get('score', 0)
            
            # 检查是否已有持仓
            if self.portfolio.get_position(symbol):
                logger.info(f"已有持仓 {symbol}，跳过")
                continue
            
            # 获取板块信息
            sector = stock.get('sector', '未知')
            sector_heat = stock.get('sector_heat', 'Low')
            signals = stock.get('signals', [])
            
            # 执行买入
            success = self.portfolio.buy(symbol, name, price, score, sector, sector_heat, signals)
            
            if success:
                # TODO: 发送通知
                pass
        
        logger.info("=" * 60)
        logger.info("💰 买入执行完成")
        logger.info("=" * 60)
    
    def execute_risk_control(self):
        """执行风控检查"""
        logger.info("=" * 60)
        logger.info("💰 发财执行风控检查...")
        logger.info("=" * 60)
        
        # 1. 更新价格
        self.portfolio.update_prices()
        
        # 2. 风控检查
        sell_signals = self.risk.run_risk_check()
        
        if not sell_signals:
            logger.info("没有触发风控条件")
        else:
            logger.info(f"触发 {len(sell_signals)} 个卖出信号")
            
            for symbol, reason in sell_signals:
                position = self.portfolio.get_position(symbol)
                if position:
                    success = self.portfolio.sell(symbol, position.current_price, reason)
                    if success:
                        # TODO: 发送通知
                        pass
        
        logger.info("=" * 60)
        logger.info("💰 风控检查完成")
        logger.info("=" * 60)
    
    def show_portfolio(self):
        """显示账户概览"""
        account = self.portfolio.get_account()
        positions = self.portfolio.get_positions()
        
        print("\n" + "=" * 60)
        print("💰 发财·模拟账户概览")
        print("=" * 60)
        print(f"初始资金: ¥{account['initial_capital']:,.2f}")
        print(f"现金余额: ¥{account['cash_balance']:,.2f}")
        print(f"总资产:   ¥{account['total_assets']:,.2f}")
        print(f"收益率:   {(account['total_assets']/account['initial_capital']-1)*100:+.2f}%")
        print("-" * 60)
        
        if positions:
            print(f"当前持仓 ({len(positions)}只):")
            print(f"{'代码':<12} {'名称':<10} {'数量':<8} {'成本':<8} {'现价':<8} {'盈亏':<10} {'止损':<8}")
            print("-" * 60)
            for pos in positions:
                profit = (pos.current_price - pos.avg_price) * pos.quantity
                profit_pct = (pos.current_price / pos.avg_price - 1) * 100
                print(f"{pos.symbol:<12} {pos.name:<10} {pos.quantity:<8} {pos.avg_price:<8.2f} {pos.current_price:<8.2f} {profit:>+9.0f} {pos.stop_loss:<8.2f}")
        else:
            print("当前无持仓")
        
        print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='发财 - 模拟交易与资产管理')
    parser.add_argument('--buy', action='store_true', help='执行买入（14:50-15:00）')
    parser.add_argument('--risk', action='store_true', help='执行风控检查')
    parser.add_argument('--portfolio', action='store_true', help='查看账户概览')
    parser.add_argument('--history', action='store_true', help='查看交易历史')
    
    args = parser.parse_args()
    
    facai = FacaiTrader()
    
    if args.buy:
        facai.execute_buy()
    elif args.risk:
        facai.execute_risk_control()
    elif args.portfolio:
        facai.show_portfolio()
    elif args.history:
        # 显示最近10笔交易
        conn = sqlite3.connect(PORTFOLIO_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 10")
        rows = cursor.fetchall()
        conn.close()
        
        print("\n💰 最近10笔交易:")
        print(f"{'时间':<20} {'动作':<6} {'代码':<12} {'价格':<8} {'数量':<8} {'理由':<30}")
        print("-" * 80)
        for row in rows:
            print(f"{row[1][:19]:<20} {row[2]:<6} {row[3]:<12} {row[5]:<8.2f} {row[6]:<8} {row[8][:28]:<30}")
        print()
    else:
        facai.show_portfolio()


if __name__ == "__main__":
    main()
