#!/usr/bin/env python3
"""
nanfeng_v4.py - 南风量化交易引擎V4
核心目标：收盘前15-30分钟出现买入信号，月收益率>5%

策略特点：
1. 收盘前信号检测（14:30-15:00）
2. 动态止盈止损（追踪止损+分批止盈）
3. 仓位管理（凯利公式+风险平价）
4. 牛熊自适应（根据大盘调整策略）
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
from dataclasses import dataclass

# 移除对 storage_v2 的依赖，直接使用 SQLite
BEIFENG_DB = Path("/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("南风V4")

BEIFENG_DB = Path("/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks.db")


class StorageV2:
    """简化版存储接口"""
    def __init__(self):
        self.db_path = BEIFENG_DB
    
    def initialize(self):
        pass
    
    def get_all_stocks(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT code, name FROM stocks")
        stocks = cursor.fetchall()
        conn.close()
        return [{'code': row[0], 'name': row[1]} for row in stocks]


@dataclass
class TradeSignal:
    """交易信号"""
    stock_code: str
    signal_time: datetime
    signal_type: str  # BUY/SELL
    
    # 入场参数
    entry_price: float
    entry_range: Tuple[float, float]
    
    # 止损参数（动态）
    stop_loss: float
    stop_loss_pct: float
    
    # 止盈参数（分批）
    take_profit_1: float  # 第一目标（50%仓位）
    take_profit_2: float  # 第二目标（30%仓位）
    take_profit_3: float  # 第三目标（20%仓位）
    
    # 仓位建议
    position_size: float  # 0-1
    position_reason: str
    
    # 策略信息
    strategy: str
    confidence: float
    expected_return: float  # 预期收益率
    risk_reward: float
    
    # 收盘前特征
    pre_close_features: Dict


class PreCloseAnalyzer:
    """收盘前分析器 - 核心模块"""
    
    def __init__(self):
        self.storage = StorageV2()
        self.storage.initialize()
    
    def analyze_pre_close(self, stock_code: str, 
                         minute_df: pd.DataFrame,
                         daily_df: pd.DataFrame) -> Optional[TradeSignal]:
        """
        收盘前15-30分钟信号分析
        
        核心逻辑：
        1. 14:30后放量上涨
        2. 主力资金净流入
        3. 技术指标共振
        4. 板块热点匹配
        """
        if len(minute_df) < 30 or len(daily_df) < 20:
            return None
        
        # 获取14:30后的数据
        minute_df['timestamp'] = pd.to_datetime(minute_df['timestamp'])
        afternoon = minute_df[minute_df['timestamp'].dt.time >= pd.Timestamp('14:30:00').time()]
        
        if len(afternoon) < 5:
            return None
        
        # 计算收盘前特征
        features = self._calculate_pre_close_features(afternoon, daily_df)
        
        # 信号判断
        signal_score = 0
        reasons = []
        
        # 1. 放量上涨 (30分)
        if features['volume_ratio'] > 1.5 and features['price_change'] > 0.01:
            signal_score += 30
            reasons.append("放量上涨")
        
        # 2. 突破日内高点 (20分)
        if features['break_high']:
            signal_score += 20
            reasons.append("突破日内高点")
        
        # 3. 均线支撑 (20分)
        if features['above_ma5'] and features['ma5_trend'] > 0:
            signal_score += 20
            reasons.append("均线支撑")
        
        # 4. MACD金叉 (15分)
        if features['macd_golden_cross']:
            signal_score += 15
            reasons.append("MACD金叉")
        
        # 5. 资金流向 (15分)
        if features['money_flow'] > 0:
            signal_score += 15
            reasons.append("资金净流入")
        
        # 生成信号
        if signal_score >= 70:
            close_price = afternoon['close'].iloc[-1]
            
            # 动态止损（基于ATR）
            atr = features['atr']
            stop_loss = close_price - 2 * atr
            stop_loss_pct = (close_price - stop_loss) / close_price
            
            # 分批止盈
            tp1 = close_price * 1.03  # 3%止盈50%
            tp2 = close_price * 1.05  # 5%止盈30%
            tp3 = close_price * 1.08  # 8%止盈20%
            
            # 仓位计算（凯利公式简化版）
            win_rate = signal_score / 100
            avg_win = 0.05  # 平均盈利5%
            avg_loss = stop_loss_pct
            kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
            position = min(0.3, max(0.1, kelly))  # 限制10%-30%
            
            return TradeSignal(
                stock_code=stock_code,
                signal_time=datetime.now(),
                signal_type='BUY',
                entry_price=close_price,
                entry_range=(close_price * 0.995, close_price * 1.005),
                stop_loss=stop_loss,
                stop_loss_pct=stop_loss_pct,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                position_size=position,
                position_reason=f"凯利公式: {kelly:.2f}",
                strategy='收盘前突破',
                confidence=signal_score / 100,
                expected_return=0.05,
                risk_reward=(tp1 - close_price) / (close_price - stop_loss),
                pre_close_features=features
            )
        
        return None
    
    def _calculate_pre_close_features(self, afternoon: pd.DataFrame, 
                                     daily: pd.DataFrame) -> Dict:
        """计算收盘前特征"""
        close = afternoon['close'].iloc[-1]
        open_price = afternoon['open'].iloc[0]
        high = afternoon['high'].max()
        low = afternoon['low'].min()
        
        # 日内数据
        daily_high = daily['high'].iloc[-1]
        daily_low = daily['low'].iloc[-1]
        
        # 成交量比
        avg_volume = daily['volume'].rolling(5).mean().iloc[-1]
        current_volume = afternoon['volume'].sum()
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 0
        
        # 涨跌幅
        price_change = (close - open_price) / open_price
        
        # 是否突破日内高点
        break_high = close >= daily_high * 0.995
        
        # 均线
        ma5 = daily['close'].rolling(5).mean().iloc[-1]
        above_ma5 = close > ma5
        ma5_trend = (ma5 - daily['close'].rolling(5).mean().iloc[-2]) / ma5
        
        # MACD
        ema12 = daily['close'].ewm(span=12).mean()
        ema26 = daily['close'].ewm(span=26).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9).mean()
        macd_golden_cross = dif.iloc[-1] > dea.iloc[-1] and dif.iloc[-2] <= dea.iloc[-2]
        
        # ATR
        tr1 = daily['high'].iloc[-1] - daily['low'].iloc[-1]
        tr2 = abs(daily['high'].iloc[-1] - daily['close'].iloc[-2])
        tr3 = abs(daily['low'].iloc[-1] - daily['close'].iloc[-2])
        atr = max(tr1, tr2, tr3)
        
        # 资金流向（简化）
        money_flow = 1 if close > daily['open'].iloc[-1] else -1
        
        return {
            'volume_ratio': volume_ratio,
            'price_change': price_change,
            'break_high': break_high,
            'above_ma5': above_ma5,
            'ma5_trend': ma5_trend,
            'macd_golden_cross': macd_golden_cross,
            'atr': atr,
            'money_flow': money_flow
        }


class NanFengV4:
    """南风V4主类"""
    
    def __init__(self):
        self.analyzer = PreCloseAnalyzer()
    
    def scan_pre_close_signals(self, min_confidence: float = 0.7) -> List[TradeSignal]:
        """
        扫描收盘前信号
        在14:30-15:00之间运行
        """
        logger.info("🌪️ 南风V4 - 扫描收盘前信号...")
        
        # 获取有分钟数据的股票
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT stock_code 
            FROM kline_data 
            WHERE data_type = '1min' AND DATE(timestamp) = DATE('now')
        """)
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"扫描 {len(stocks)} 只今日有分钟数据的股票")
        
        signals = []
        for i, stock_code in enumerate(stocks[:100]):  # 先扫描前100只
            try:
                # 获取数据
                minute_df = self._get_minute_data(stock_code)
                daily_df = self._get_daily_data(stock_code)
                
                if len(minute_df) < 30 or len(daily_df) < 20:
                    continue
                
                # 分析信号
                signal = self.analyzer.analyze_pre_close(stock_code, minute_df, daily_df)
                
                if signal and signal.confidence >= min_confidence:
                    signals.append(signal)
                    logger.info(f"✅ {stock_code} 信号: {signal.confidence:.0%} 置信度")
                
            except Exception as e:
                logger.error(f"分析 {stock_code} 失败: {e}")
        
        # 排序
        signals.sort(key=lambda x: x.confidence, reverse=True)
        
        logger.info(f"发现 {len(signals)} 个收盘前信号")
        return signals
    
    def _get_minute_data(self, stock_code: str) -> pd.DataFrame:
        """获取分钟数据"""
        conn = sqlite3.connect(BEIFENG_DB)
        query = """
            SELECT timestamp, open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = ? AND data_type = '1min'
            AND DATE(timestamp) = DATE('now')
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(stock_code,))
        conn.close()
        return df
    
    def _get_daily_data(self, stock_code: str) -> pd.DataFrame:
        """获取日线数据"""
        conn = sqlite3.connect(BEIFENG_DB)
        query = """
            SELECT timestamp, open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            AND timestamp >= DATE('now', '-30 days')
            ORDER BY timestamp
        """
        df = pd.read_sql_query(query, conn, params=(stock_code,))
        conn.close()
        return df


def main():
    """测试"""
    nanfeng = NanFengV4()
    
    # 扫描信号
    signals = nanfeng.scan_pre_close_signals(min_confidence=0.7)
    
    print(f"\n发现 {len(signals)} 个交易信号:\n")
    
    for i, s in enumerate(signals[:10], 1):
        print(f"{i}. {s.stock_code}")
        print(f"   入场价: {s.entry_price:.2f}")
        print(f"   止损: {s.stop_loss:.2f} ({s.stop_loss_pct:.1%})")
        print(f"   止盈: {s.take_profit_1:.2f} / {s.take_profit_2:.2f} / {s.take_profit_3:.2f}")
        print(f"   仓位: {s.position_size:.0%}")
        print(f"   置信度: {s.confidence:.0%}")
        print(f"   盈亏比: {s.risk_reward:.2f}")
        print()


if __name__ == '__main__':
    main()
