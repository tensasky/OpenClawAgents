#!/usr/bin/env python3
"""
nanfeng_v3.py - 南风实时量化分析引擎
核心功能:
1. 分钟数据实时汇聚成日线/小时线
2. 动态量化指标计算（自适应参数）
3. 实时信号监控与输出
4. 盘中选股策略执行

进化点:
- 从"打分器"进化为"量化策略引擎"
- 输出具体交易参数（入场价、止损价、目标价）
- 实时监控，分钟级响应
"""

import os
import sys
import json
import logging
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, asdict

# 配置
WORKSPACE = Path("/Users/roberto/Documents/OpenClawAgents/nanfeng")
DATA_DIR = WORKSPACE / "data"
LOG_DIR = WORKSPACE / "logs"
SIGNAL_DIR = WORKSPACE / "signals"
BEIFENG_DB = Path("/Users/roberto/.openclaw/agents/beifeng/data/stocks.db")

for d in [DATA_DIR, LOG_DIR, SIGNAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"nanfeng_v3_{datetime.now():%Y%m%d}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风V3")


@dataclass
class QuantSignal:
    """量化交易信号"""
    stock_code: str
    signal_time: datetime
    signal_type: str  # BUY/SELL/HOLD
    
    # 入场参数
    entry_price: float
    entry_range: Tuple[float, float]  # 建议入场区间
    
    # 风控参数
    stop_loss: float
    take_profit: float
    risk_reward: float  # 盈亏比
    
    # 策略参数
    strategy: str  # 策略名称
    confidence: float  # 置信度 0-1
    holding_period: int  # 建议持有周期(天)
    
    # 指标值
    indicators: Dict[str, float]
    
    def to_dict(self):
        return {
            **asdict(self),
            'signal_time': self.signal_time.isoformat()
        }


class MinuteAggregator:
    """分钟数据聚合器 - 实时生成日线/小时线"""
    
    @staticmethod
    def aggregate_to_daily(minute_df: pd.DataFrame) -> pd.DataFrame:
        """
        将分钟数据聚合成日线
        
        Input: 分钟数据 [timestamp, open, high, low, close, volume]
        Output: 日线数据
        """
        if len(minute_df) == 0:
            return pd.DataFrame()
        
        minute_df['timestamp'] = pd.to_datetime(minute_df['timestamp'])
        minute_df['date'] = minute_df['timestamp'].dt.date
        
        daily = minute_df.groupby('date').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
            'amount': 'sum'
        }).reset_index()
        
        daily['timestamp'] = pd.to_datetime(daily['date'])
        return daily
    
    @staticmethod
    def get_intraday_status(minute_df: pd.DataFrame) -> Dict:
        """
        获取当日盘中状态
        
        Returns:
            {
                'current_price': 当前价格,
                'today_open': 今开,
                'today_high': 最高,
                'today_low': 最低,
                'volume_ratio': 量比,
                'price_change': 涨跌幅,
                'last_hour_trend': 最后一小时趋势
            }
        """
        if len(minute_df) == 0:
            return {}
        
        minute_df = minute_df.sort_values('timestamp')
        
        today = minute_df.iloc[-1]
        prev_close = minute_df.iloc[0]['close']  # 简化，实际应该用昨日收盘
        
        # 计算量比（当前成交量 vs 历史平均）
        avg_volume = minute_df['volume'].rolling(20).mean().iloc[-1]
        volume_ratio = today['volume'] / avg_volume if avg_volume > 0 else 0
        
        # 最后一小时趋势
        last_hour = minute_df.tail(60)  # 假设1分钟数据
        last_hour_trend = (last_hour['close'].iloc[-1] - last_hour['close'].iloc[0]) / last_hour['close'].iloc[0]
        
        return {
            'current_price': today['close'],
            'today_open': today['open'],
            'today_high': today['high'],
            'today_low': today['low'],
            'volume_ratio': volume_ratio,
            'price_change': (today['close'] - prev_close) / prev_close,
            'last_hour_trend': last_hour_trend
        }


class AdaptiveIndicators:
    """自适应技术指标 - 根据市场状态调整参数"""
    
    def __init__(self, df: pd.DataFrame):
        self.df = df
        self.close = df['close']
        self.high = df['high']
        self.low = df['low']
        self.volume = df['volume']
        
        # 检测市场状态
        self.market_state = self._detect_market_state()
    
    def _detect_market_state(self) -> str:
        """检测市场状态: trending/ranging/volatile"""
        # 计算波动率
        returns = self.close.pct_change()
        volatility = returns.std() * np.sqrt(252)  # 年化波动率
        
        # 计算趋势强度
        ma20 = self.close.rolling(20).mean()
        trend_strength = abs(self.close.iloc[-1] - ma20.iloc[-1]) / ma20.iloc[-1]
        
        if volatility > 0.3:
            return 'volatile'
        elif trend_strength > 0.05:
            return 'trending'
        else:
            return 'ranging'
    
    def get_ma_periods(self) -> Dict[str, int]:
        """根据市场状态返回最佳均线周期"""
        if self.market_state == 'trending':
            return {'short': 5, 'medium': 10, 'long': 20}
        elif self.market_state == 'volatile':
            return {'short': 3, 'medium': 8, 'long': 15}
        else:  # ranging
            return {'short': 10, 'medium': 20, 'long': 60}
    
    def calculate_all(self) -> Dict[str, float]:
        """计算所有自适应指标"""
        periods = self.get_ma_periods()
        
        # 均线
        ma_short = self.close.rolling(periods['short']).mean().iloc[-1]
        ma_medium = self.close.rolling(periods['medium']).mean().mean()
        ma_long = self.close.rolling(periods['long']).mean().iloc[-1]
        
        # MACD自适应
        if self.market_state == 'volatile':
            fast, slow, signal = 8, 17, 9
        else:
            fast, slow, signal = 12, 26, 9
        
        ema_fast = self.close.ewm(span=fast).mean()
        ema_slow = self.close.ewm(span=slow).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal).mean()
        macd = (dif - dea) * 2
        
        # RSI自适应
        rsi_period = 6 if self.market_state == 'volatile' else 14
        delta = self.close.diff()
        gain = delta.where(delta > 0, 0).rolling(rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        # 布林带自适应
        boll_period = 15 if self.market_state == 'volatile' else 20
        ma = self.close.rolling(boll_period).mean()
        std = self.close.rolling(boll_period).std()
        
        return {
            'ma_short': ma_short,
            'ma_medium': ma_medium,
            'ma_long': ma_long,
            'macd_dif': dif.iloc[-1],
            'macd_dea': dea.iloc[-1],
            'macd': macd.iloc[-1],
            'rsi': rsi.iloc[-1],
            'boll_upper': (ma + std * 2).iloc[-1],
            'boll_middle': ma.iloc[-1],
            'boll_lower': (ma - std * 2).iloc[-1],
            'market_state': self.market_state
        }


class QuantStrategy:
    """量化策略引擎 - 输出具体交易参数"""
    
    def __init__(self):
        self.aggregator = MinuteAggregator()
    
    def analyze(self, stock_code: str, daily_df: pd.DataFrame, 
                minute_df: pd.DataFrame = None) -> Optional[QuantSignal]:
        """
        综合分析，输出量化交易信号
        """
        if len(daily_df) < 20:
            return None
        
        # 自适应指标
        indicators = AdaptiveIndicators(daily_df)
        vals = indicators.calculate_all()
        
        close = daily_df['close'].iloc[-1]
        
        # 策略判断
        signal_type = 'HOLD'
        strategy = ''
        confidence = 0.0
        
        # 策略1: 趋势跟踪
        if vals['ma_short'] > vals['ma_medium'] > vals['ma_long']:
            if vals['macd'] > 0 and vals['rsi'] < 70:
                signal_type = 'BUY'
                strategy = '趋势跟踪'
                confidence = 0.7
        
        # 策略2: 均值回归
        elif close < vals['boll_lower'] and vals['rsi'] < 30:
            signal_type = 'BUY'
            strategy = '均值回归'
            confidence = 0.6
        
        # 策略3: MACD底背离
        elif vals['macd_dif'] > vals['macd_dea'] and vals['macd'] > vals['macd'].shift(1).iloc[-1]:
            signal_type = 'BUY'
            strategy = 'MACD金叉'
            confidence = 0.5
        
        # 计算交易参数
        if signal_type == 'BUY':
            entry_price = close
            stop_loss = close * 0.95  # 5%止损
            take_profit = close * 1.08  # 8%止盈
            
            # 根据波动率调整
            atr = self._calculate_atr(daily_df)
            if atr > 0:
                stop_loss = close - 2 * atr
                take_profit = close + 3 * atr
            
            risk_reward = (take_profit - entry_price) / (entry_price - stop_loss)
            
            return QuantSignal(
                stock_code=stock_code,
                signal_time=datetime.now(),
                signal_type=signal_type,
                entry_price=round(entry_price, 2),
                entry_range=(round(close * 0.99, 2), round(close * 1.01, 2)),
                stop_loss=round(stop_loss, 2),
                take_profit=round(take_profit, 2),
                risk_reward=round(risk_reward, 2),
                strategy=strategy,
                confidence=round(confidence, 2),
                holding_period=5,
                indicators=vals
            )
        
        return None
    
    def _calculate_atr(self, df: pd.DataFrame, period=14) -> float:
        """计算ATR（平均真实波幅）"""
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean().iloc[-1]
        
        return atr


class NanFengV3:
    """南风V3主类 - 实时量化引擎"""
    
    def __init__(self):
        self.strategy = QuantStrategy()
        self.beifeng_db = BEIFENG_DB
    
    def get_minute_data(self, stock_code: str, days: int = 5) -> pd.DataFrame:
        """获取分钟数据"""
        conn = sqlite3.connect(self.beifeng_db)
        
        query = f"""
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE stock_code = '{stock_code}' AND data_type = '1min'
        AND timestamp >= datetime('now', '-{days} days')
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def get_daily_data(self, stock_code: str, days: int = 60) -> pd.DataFrame:
        """获取日线数据"""
        conn = sqlite3.connect(self.beifeng_db)
        
        query = f"""
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE stock_code = '{stock_code}' AND data_type = 'daily'
        AND timestamp >= date('now', '-{days} days')
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def scan_intraday(self, min_confidence: float = 0.6) -> List[QuantSignal]:
        """
        盘中扫描 - 实时选股
        
        流程:
        1. 获取分钟数据
        2. 聚合成日线
        3. 实时计算指标
        4. 输出交易信号
        """
        logger.info("🌪️ 南风V3盘中扫描启动...")
        
        # 获取股票列表
        conn = sqlite3.connect(self.beifeng_db)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type = '1min'")
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"扫描 {len(stocks)} 只有分钟数据的股票...")
        
        signals = []
        for i, stock_code in enumerate(stocks):
            try:
                # 获取分钟数据
                minute_df = self.get_minute_data(stock_code, days=5)
                if len(minute_df) < 100:  # 至少100条分钟数据
                    continue
                
                # 聚合成日线
                daily_df = self.strategy.aggregator.aggregate_to_daily(minute_df)
                if len(daily_df) < 5:
                    continue
                
                # 获取历史日线补充
                hist_daily = self.get_daily_data(stock_code, days=60)
                if len(hist_daily) > len(daily_df):
                    daily_df = pd.concat([hist_daily.iloc[:-len(daily_df)], daily_df])
                
                # 分析信号
                signal = self.strategy.analyze(stock_code, daily_df, minute_df)
                
                if signal and signal.confidence >= min_confidence:
                    signals.append(signal)
                    logger.info(f"[{i+1}/{len(stocks)}] {stock_code} "
                              f"信号:{signal.signal_type} 置信度:{signal.confidence} "
                              f"策略:{signal.strategy}")
                
            except Exception as e:
                logger.error(f"分析 {stock_code} 失败: {e}")
        
        # 按置信度排序
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"扫描完成，发现 {len(signals)} 个交易信号")
        return signals
    
    def save_signals(self, signals: List[QuantSignal], filename: str = None):
        """保存信号到文件"""
        if filename is None:
            filename = SIGNAL_DIR / f"signals_{datetime.now():%Y%m%d_%H%M%S}.json"
        
        data = {
            'generated_at': datetime.now().isoformat(),
            'total_signals': len(signals),
            'signals': [s.to_dict() for s in signals]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"信号已保存: {filename}")
        return filename


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='南风V3实时量化引擎')
    parser.add_argument('--scan', action='store_true', help='盘中扫描')
    parser.add_argument('--stock', type=str, help='分析单只股票')
    parser.add_argument('--min-confidence', type=float, default=0.6, help='最低置信度')
    
    args = parser.parse_args()
    
    nanfeng = NanFengV3()
    
    if args.stock:
        # 分析单只股票
        minute_df = nanfeng.get_minute_data(args.stock)
        daily_df = nanfeng.get_daily_data(args.stock)
        
        print(f"\n📊 {args.stock} 分析")
        print(f"  分钟数据: {len(minute_df)} 条")
        print(f"  日线数据: {len(daily_df)} 条")
        
        if len(daily_df) >= 20:
            signal = nanfeng.strategy.analyze(args.stock, daily_df, minute_df)
            if signal:
                print(f"\n🎯 交易信号: {signal.signal_type}")
                print(f"  策略: {signal.strategy}")
                print(f"  置信度: {signal.confidence}")
                print(f"  入场价: {signal.entry_price}")
                print(f"  止损价: {signal.stop_loss}")
                print(f"  目标价: {signal.take_profit}")
                print(f"  盈亏比: {signal.risk_reward}")
            else:
                print("\n⏸️ 无交易信号")
    
    elif args.scan:
        # 盘中扫描
        signals = nanfeng.scan_intraday(min_confidence=args.min_confidence)
        nanfeng.save_signals(signals)
        
        print("\n🏆 TOP 交易信号:")
        for i, s in enumerate(signals[:10], 1):
            print(f"{i}. {s.stock_code} | {s.strategy} | 置信度:{s.confidence}")
            print(f"   入场:{s.entry_price} 止损:{s.stop_loss} 目标:{s.take_profit}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
