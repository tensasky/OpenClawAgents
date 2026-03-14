#!/usr/bin/env python3
"""
发财 V2.0 - 模拟交易完善版
每个策略10万资金，记录买入条件、金额、手续费
"""

import sqlite3
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("发财")

# 配置
FACAI_DIR = Path(__file__).parent
DATA_DIR = FACAI_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "portfolio_v2.db"
CONFIG_PATH = FACAI_DIR / "config" / "strategies.json"

# 交易配置
TRADE_CONFIG = {
    'initial_capital_per_strategy': 100000,  # 每个策略10万
    'max_position_per_stock': 0.25,          # 单票最大25%
    'buy_fee_rate': 0.0,                     # 买入手续费0%
    'sell_fee_rate': 0.0003,                 # 卖出手续费万分之三
    'min_buy_amount': 1000,                  # 最小买入金额1000元
}


class TradeRecord:
    """交易记录"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                strategy TEXT NOT NULL,           -- 策略名称
                stock_code TEXT NOT NULL,         -- 股票代码
                stock_name TEXT,                  -- 股票名称
                buy_date TEXT NOT NULL,           -- 买入日期
                buy_price REAL NOT NULL,          -- 买入价格
                buy_quantity INTEGER NOT NULL,    -- 买入数量
                buy_amount REAL NOT NULL,         -- 买入金额
                buy_conditions TEXT,              -- 买入条件(JSON)
                sell_price REAL,                  -- 卖出价格
                sell_date TEXT,                   -- 卖出日期
                sell_fee REAL,                    -- 卖出手续费
                sell_reason TEXT,                 -- 卖出原因
                profit REAL,                      -- 盈亏金额
                profit_pct REAL,                  -- 盈亏比例
                status TEXT DEFAULT 'holding',    -- 状态
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 资金表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS capital (
                strategy TEXT PRIMARY KEY,
                initial REAL NOT NULL,
                available REAL NOT NULL,
                frozen REAL DEFAULT 0,
                market_value REAL DEFAULT 0,
                total_profit REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def init_strategy_capital(self, strategy_name: str):
        """初始化策略资金"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO capital 
            (strategy, initial, available) 
            VALUES (?, ?, ?)
        ''', (strategy_name, 
              TRADE_CONFIG['initial_capital_per_strategy'],
              TRADE_CONFIG['initial_capital_per_strategy']))
        
        conn.commit()
        conn.close()
    
    def buy(self, strategy: str, stock_code: str, stock_name: str,
            price: float, conditions: Dict) -> Dict:
        """
        买入股票
        
        Args:
            strategy: 策略名称
            stock_code: 股票代码
            stock_name: 股票名称
            price: 买入价格
            conditions: 买入条件 {
                'signal_score': 信号分数,
                'adx': ADX值,
                'rsi': RSI值,
                'volume_ratio': 量比,
                'sector': 所属板块,
                'is_hot_sector': 是否热点,
                'buy_reason': 买入理由
            }
        
        Returns:
            交易结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 检查可用资金
        cursor.execute('SELECT available FROM capital WHERE strategy = ?', (strategy,))
        result = cursor.fetchone()
        
        if not result:
            self.init_strategy_capital(strategy)
            available = TRADE_CONFIG['initial_capital_per_strategy']
        else:
            available = result[0]
        
        # 计算买入金额（单票不超过25%）
        max_position = TRADE_CONFIG['initial_capital_per_strategy'] * \
                       TRADE_CONFIG['max_position_per_stock']
        buy_amount = min(max_position, available * 0.9)  # 留10%现金
        
        if buy_amount < TRADE_CONFIG['min_buy_amount']:
            conn.close()
            return {'success': False, 'error': '可用资金不足'}
        
        # 计算数量（100股整数倍）
        quantity = int(buy_amount / price / 100) * 100
        if quantity < 100:
            conn.close()
            return {'success': False, 'error': '数量不足100股'}
        
        actual_amount = quantity * price
        
        # 记录买入
        buy_conditions_json = json.dumps(conditions, ensure_ascii=False)
        
        cursor.execute('''
            INSERT INTO positions 
            (strategy, stock_code, stock_name, buy_date, buy_price, 
             buy_quantity, buy_amount, buy_conditions, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'holding')
        ''', (strategy, stock_code, stock_name,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              price, quantity, actual_amount, buy_conditions_json))
        
        # 冻结资金
        cursor.execute('''
            UPDATE capital 
            SET available = available - ?, frozen = frozen + ?
            WHERE strategy = ?
        ''', (actual_amount, actual_amount, strategy))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'strategy': strategy,
            'stock_code': stock_code,
            'stock_name': stock_name,
            'buy_price': price,
            'quantity': quantity,
            'amount': actual_amount,
            'conditions': conditions,
            'available_after': available - actual_amount
        }
    
    def sell(self, position_id: int, sell_price: float, reason: str) -> Dict:
        """
        卖出股票
        
        Args:
            position_id: 持仓ID
            sell_price: 卖出价格
            reason: 卖出原因（止盈/止损/时间）
        
        Returns:
            交易结果
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取持仓信息
        cursor.execute('''
            SELECT strategy, stock_code, buy_price, buy_quantity, buy_amount
            FROM positions WHERE id = ? AND status = 'holding'
        ''', (position_id,))
        
        position = cursor.fetchone()
        if not position:
            conn.close()
            return {'success': False, 'error': '持仓不存在或已卖出'}
        
        strategy, stock_code, buy_price, quantity, buy_amount = position
        
        # 计算卖出金额和手续费
        sell_amount = sell_price * quantity
        sell_fee = sell_amount * TRADE_CONFIG['sell_fee_rate']
        net_amount = sell_amount - sell_fee
        
        # 计算盈亏
        profit = net_amount - buy_amount
        profit_pct = (sell_price - buy_price) / buy_price * 100
        
        # 更新持仓
        cursor.execute('''
            UPDATE positions 
            SET sell_price = ?, sell_date = ?, sell_fee = ?,
                sell_reason = ?, profit = ?, profit_pct = ?, status = 'sold'
            WHERE id = ?
        ''', (sell_price, datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
              sell_fee, reason, profit, profit_pct, position_id))
        
        # 更新资金
        cursor.execute('''
            UPDATE capital 
            SET available = available + ?, frozen = frozen - ?,
                total_profit = total_profit + ?
            WHERE strategy = ?
        ''', (net_amount, buy_amount, profit, strategy))
        
        conn.commit()
        conn.close()
        
        return {
            'success': True,
            'stock_code': stock_code,
            'sell_price': sell_price,
            'quantity': quantity,
            'sell_amount': sell_amount,
            'sell_fee': sell_fee,
            'net_amount': net_amount,
            'profit': profit,
            'profit_pct': profit_pct,
            'reason': reason
        }
    
    def get_portfolio(self, strategy: str = None) -> List[Dict]:
        """获取持仓"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if strategy:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE strategy = ? AND status = 'holding'
                ORDER BY buy_date DESC
            ''', (strategy,))
        else:
            cursor.execute('''
                SELECT * FROM positions 
                WHERE status = 'holding'
                ORDER BY buy_date DESC
            ''')
        
        columns = [description[0] for description in cursor.description]
        positions = []
        
        for row in cursor.fetchall():
            pos = dict(zip(columns, row))
            if pos['buy_conditions']:
                pos['buy_conditions'] = json.loads(pos['buy_conditions'])
            positions.append(pos)
        
        conn.close()
        return positions
    
    def get_capital(self, strategy: str = None) -> Dict:
        """获取资金状况"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if strategy:
            cursor.execute('SELECT * FROM capital WHERE strategy = ?', (strategy,))
            row = cursor.fetchone()
            if row:
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
        else:
            cursor.execute('SELECT * FROM capital')
            columns = [description[0] for description in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def generate_report(self) -> str:
        """生成交易报告"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 总体统计
        cursor.execute('''
            SELECT 
                COUNT(*) as total_trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as win_count,
                SUM(profit) as total_profit,
                AVG(profit_pct) as avg_profit_pct
            FROM positions WHERE status = 'sold'
        ''')
        
        stats = cursor.fetchone()
        total_trades, win_count, total_profit, avg_profit_pct = stats
        
        win_rate = (win_count / total_trades * 100) if total_trades > 0 else 0
        
        # 各策略统计
        cursor.execute('''
            SELECT 
                strategy,
                COUNT(*) as trades,
                SUM(CASE WHEN profit > 0 THEN 1 ELSE 0 END) as wins,
                SUM(profit) as profit
            FROM positions WHERE status = 'sold'
            GROUP BY strategy
        ''')
        
        strategy_stats = cursor.fetchall()
        
        conn.close()
        
        report = f"""💰 **发财模拟交易报告**
📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}

📊 **总体统计**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
总交易次数: {total_trades or 0}
盈利次数: {win_count or 0}
胜率: {win_rate:.1f}%
总盈亏: ¥{total_profit or 0:,.2f}
平均收益率: {avg_profit_pct or 0:.2f}%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **各策略表现**
"""
        
        for strategy, trades, wins, profit in strategy_stats:
            s_win_rate = (wins / trades * 100) if trades > 0 else 0
            report += f"\n{strategy}:\n"
            report += f"  交易: {trades}次 | 胜率: {s_win_rate:.1f}% | 盈亏: ¥{profit:,.2f}\n"
        
        # 当前持仓
        positions = self.get_portfolio()
        if positions:
            report += f"\n📋 **当前持仓** ({len(positions)}只)\n"
            for pos in positions[:5]:
                report += f"\n• {pos['stock_code']} | {pos['strategy']}\n"
                report += f"  买入: ¥{pos['buy_price']:.2f} x {pos['buy_quantity']}股\n"
                cond = pos.get('buy_conditions', {})
                report += f"  条件: 分数{cond.get('signal_score', 'N/A')}, ADX{cond.get('adx', 'N/A')}\n"
        
        return report


def main():
    """测试"""
    log.step("发财V2.0初始化")
    
    trade = TradeRecord()
    
    # 初始化策略资金
    strategies = ["趋势跟踪", "均值回归", "突破策略", "稳健增长", "热点追击"]
    for s in strategies:
        trade.init_strategy_capital(s)
    
    log.info("初始资金:")
    for cap in trade.get_capital():
        log.info(f"  {cap['strategy']}: ¥{cap['available']:,.0f}")
    
    log.success("发财V2.0初始化完成")
    log.info("每个策略10万资金，买入记录完整条件，卖出手续费万分之三")


if __name__ == '__main__':
    main()
