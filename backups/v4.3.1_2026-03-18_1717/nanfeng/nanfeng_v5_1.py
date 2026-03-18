#!/usr/bin/env python3
"""
nanfeng_v5_1.py - 南风量化交易引擎V5.5 (精选版)
核心改进：每天只选Top 5，大幅提高信号质量

V5.5关键改进：
1. 严格门槛 - 分数>=8.5, ADX>=30, MA20强势向上
2. 精选策略 - 每天最多选5只，按综合评分排序
3. 市场环境过滤 - 大盘ADX<20时暂停
4. 板块共振 - 优先选热点板块内的股票
"""

import os
import sys
import json
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

# 导入实时数据聚合器和策略配置
sys.path.insert(0, str(Path(__file__).parent))
from realtime_aggregator import RealtimeAggregator
from strategy_config import StrategyConfig, get_strategy, STRATEGIES

# 初始化日志
log = get_logger("南风")

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)


@dataclass
class TradeSignal:
    """交易信号"""
    stock_code: str
    stock_name: str = ""
    signal_time: datetime = field(default_factory=datetime.now)
    
    current_price: float = 0.0
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    
    total_score: float = 0.0
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volume_score: float = 0.0
    quality_score: float = 0.0
    
    adx: float = 0.0
    rsi: float = 0.0
    macd_dif: float = 0.0
    ma20_slope: float = 0.0
    relative_strength: float = 0.0
    
    is_hot_sector: bool = False
    sector: str = ""
    
    signals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    position_size: float = 0.0
    confidence: float = 0.0


class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 6) -> pd.Series:
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        dif = ema_fast - ema_slow
        dea = TechnicalIndicators.ema(dif, signal)
        macd_hist = (dif - dea) * 2
        return dif, dea, macd_hist
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        return adx
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/period, adjust=False).mean()


class NanFengV5_1:
    """南风V5.5 - 精选版 (支持多策略)"""
    
    def __init__(self, use_realtime: bool = True, strategy_name: str = "趋势跟踪"):
        self.db_path = BEIFENG_DB
        self.indicators = TechnicalIndicators()
        self.hot_spots = self._load_hot_spots()
        self.realtime = RealtimeAggregator() if use_realtime else None
        self.use_realtime = use_realtime
        self.stock_names = {}  # 缓存股票名称
        self.strategy_name = strategy_name  # 保存策略名称
        
        # 加载策略配置
        self.strategy = get_strategy(strategy_name)
        log.info(f"🎯 加载策略: {self.strategy.name} - {self.strategy.description}")
        
        # 从策略配置加载参数
        self.min_adx = self.strategy.min_adx
        self.min_ma20_slope = self.strategy.min_ma20_slope
        self.min_volume_ratio = self.strategy.min_volume_ratio
        self.score_threshold = self.strategy.score_threshold
        self.max_signals_per_day = 5
        
        # RSI区间
        self.rsi_low = self.strategy.rsi_low
        self.rsi_high = self.strategy.rsi_high
        
        # 权重
        self.weights = {
            'trend': self.strategy.trend_weight,
            'momentum': self.strategy.momentum_weight,
            'volume': self.strategy.volume_weight,
            'quality': self.strategy.quality_weight
        }
    
    def _load_hot_spots(self) -> Dict:
        """加载热点板块"""
        hot_stocks = {}
        if XIFENG_HOTSPOTS.exists():
            try:
                with open(XIFENG_HOTSPOTS, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                for spot in data.get('hot_spots', []):
                    sector = spot.get('sector', '')
                    level = spot.get('level', 'Low')
                    for stock in spot.get('leading_stocks', []):
                        code = stock.get('code', '')
                        name = stock.get('name', '')
                        if code:
                            hot_stocks[code] = {'sector': sector, 'level': level, 'name': name}
            except Exception as e:
                log.error(f"加载热点失败: {e}")
        return hot_stocks
    
    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        if stock_code in self.stock_names:
            return self.stock_names[stock_code]
        
        # 从热点数据获取
        if stock_code in self.hot_spots:
            name = self.hot_spots[stock_code].get('name', '')
            if name:
                self.stock_names[stock_code] = name
                return name
        
        # 从数据库获取
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM stocks WHERE code=?", (stock_code,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                self.stock_names[stock_code] = row[0]
                return row[0]
        except:
            pass
        
        return stock_code
    
    def check_market_environment(self) -> Tuple[bool, str]:
        """检查市场环境 - 大盘趋势（使用实时数据）"""
        try:
            # 优先使用实时聚合数据
            if self.use_realtime and self.realtime:
                df = self.realtime.get_stock_data_with_realtime('sh000001', days=30)
                if df is not None and len(df) >= 20:
                    # 检查是否有实时数据
                    has_realtime = df['is_realtime'].iloc[-1] if 'is_realtime' in df.columns else False
                    data_source = "实时" if has_realtime else "历史"
                else:
                    return True, "无法获取大盘数据，默认允许"
            else:
                # 回退到传统查询
                conn = sqlite3.connect(self.db_path)
                query = """
                    SELECT timestamp, open, high, low, close, volume
                    FROM daily
                    WHERE stock_code = 'sh000001'
                    ORDER BY timestamp DESC
                    LIMIT 30
                """
                df = pd.read_sql_query(query, conn)
                conn.close()
                data_source = "历史"
                
                if len(df) < 20:
                    return True, "无法判断市场环境，默认允许"
                
                df = df.sort_values('timestamp').reset_index(drop=True)
            
            # 计算大盘ADX
            adx_series = self.indicators.adx(df['high'], df['low'], df['close'], 14)
            market_adx = adx_series.iloc[-1] if not adx_series.empty else 0
            
            # 计算大盘MA20斜率
            ma20 = self.indicators.sma(df['close'], 20)
            ma20_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] if ma20.iloc[-5] > 0 else 0
            
            # 获取当前价格
            current_price = df['close'].iloc[-1]
            open_price = df['open'].iloc[-1]
            daily_change = (current_price / open_price - 1) * 100
            
            if market_adx < 20:
                return False, f"[{data_source}]大盘无趋势ADX={market_adx:.1f}，建议观望"
            elif ma20_slope < -0.001:
                return False, f"[{data_source}]大盘下跌MA20斜率={ma20_slope*100:.2f}%，建议观望"
            else:
                return True, f"[{data_source}]大盘环境良好ADX={market_adx:.1f}，今日{daily_change:+.2f}%"
                
        except Exception as e:
            log.error(f"市场环境检查失败: {e}")
            return True, "检查失败，默认允许"
    
    def get_stock_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """获取股票数据 - 优先使用实时聚合数据"""
        # 1. 尝试获取实时聚合数据（包含今日实时）
        if self.use_realtime and self.realtime:
            df = self.realtime.get_stock_data_with_realtime(stock_code, days)
            if df is not None and len(df) >= 30:
                # 检查是否有实时数据
                has_realtime = df['is_realtime'].iloc[-1] if 'is_realtime' in df.columns else False
                if has_realtime:
                    log.debug(f"{stock_code}: 使用实时聚合数据")
                    return df.drop(columns=['is_realtime']) if 'is_realtime' in df.columns else df
        
        # 2. 回退到传统日线数据
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM daily
                WHERE stock_code = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(stock_code, days + 15))
            conn.close()
            
            if len(df) < 30:
                return None
            
            return df.sort_values('timestamp').reset_index(drop=True)
        except:
            return None
    
    def get_all_stocks(self, limit: int = 500) -> List[str]:
        """获取股票列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT stock_code 
            FROM daily 
            ORDER BY stock_code
            LIMIT ?
        """, (limit,))
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def calculate_relative_strength(self, stock_code: str, df: pd.DataFrame, all_stocks_data: Dict) -> float:
        """计算相对强度排名"""
        if len(df) < 20:
            return 0.0
        
        stock_return = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1)
        market_returns = []
        
        for code, data in list(all_stocks_data.items())[:100]:
            if len(data) >= 20 and code != stock_code:
                ret = (data['close'].iloc[-1] / data['close'].iloc[-20] - 1)
                market_returns.append(ret)
        
        if not market_returns:
            return 0.5
        
        better_count = sum(1 for r in market_returns if stock_return > r)
        return better_count / len(market_returns)
    
    def analyze_stock(self, stock_code: str, df: pd.DataFrame, 
                     all_stocks_data: Dict = None) -> Optional[TradeSignal]:
        """分析单只股票 - V5.5严格标准"""
        if len(df) < 30:
            return None
        
        signal = TradeSignal(stock_code=stock_code)
        
        # 获取股票名称
        signal.stock_name = self.get_stock_name(stock_code)
        
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        current_price = close.iloc[-1]
        signal.current_price = current_price
        
        signals = []
        warnings = []
        
        # 检查热点板块
        if stock_code in self.hot_spots:
            hot_info = self.hot_spots[stock_code]
            signal.is_hot_sector = hot_info.get('level') in ['High', 'Medium']
            signal.sector = hot_info.get('sector', '')
        
        # ========== 1. 趋势分析 (100分制) ==========
        trend_score = 0
        
        ma5 = self.indicators.sma(close, 5).iloc[-1]
        ma10 = self.indicators.sma(close, 10).iloc[-1]
        ma20 = self.indicators.sma(close, 20).iloc[-1]
        ma60 = self.indicators.sma(close, 60).iloc[-1] if len(close) >= 60 else ma20
        
        ma20_prev = self.indicators.sma(close, 20).iloc[-5]
        ma20_slope = (ma20 - ma20_prev) / ma20_prev if ma20_prev > 0 else 0
        signal.ma20_slope = ma20_slope
        
        adx_series = self.indicators.adx(high, low, close, 14)
        adx = adx_series.iloc[-1] if not adx_series.empty else 0
        signal.adx = adx
        
        # 1.1 价格相对均线位置 (40分)
        if current_price > ma5 > ma10 > ma20 > ma60:
            trend_score += 40
            signals.append("完美多头排列")
        elif current_price > ma5 > ma10 > ma20:
            trend_score += 35
            signals.append("多头排列")
        elif current_price > ma5 > ma20 and ma20 > ma60:
            trend_score += 30
            signals.append("强势排列")
        elif current_price > ma5 > ma20:
            trend_score += 25
            signals.append("站上短期均线")
        elif current_price > ma20 > ma60:
            trend_score += 20
            signals.append("中期上升趋势")
        elif current_price > ma20:
            trend_score += 15
            signals.append("站上MA20")
        elif current_price > ma60:
            trend_score += 10
            signals.append("站上MA60")
        
        # 1.2 MA20斜率 (30分)
        if ma20_slope > 0.02:  # 日涨幅>2%
            trend_score += 30
            signals.append("MA20极强向上")
        elif ma20_slope > 0.01:  # 日涨幅>1%
            trend_score += 25
            signals.append("MA20强势向上")
        elif ma20_slope > 0.005:  # 日涨幅>0.5%
            trend_score += 20
            signals.append("MA20明显向上")
        elif ma20_slope > 0.002:  # 日涨幅>0.2%
            trend_score += 15
            signals.append("MA20向上")
        elif ma20_slope > 0:
            trend_score += 10
            signals.append("MA20微升")
        
        # 1.3 趋势强度ADX (30分)
        if adx > 60:
            trend_score += 30
            signals.append(f"极强趋势ADX={adx:.1f}")
        elif adx > 45:
            trend_score += 25
            signals.append(f"强趋势ADX={adx:.1f}")
        elif adx > 35:
            trend_score += 20
            signals.append(f"趋势良好ADX={adx:.1f}")
        elif adx > 25:
            trend_score += 15
            signals.append(f"有趋势ADX={adx:.1f}")
        elif adx > 15:
            trend_score += 10
            signals.append(f"弱趋势ADX={adx:.1f}")
        
        signal.trend_score = trend_score
        
        # ========== 2. 动量分析 (100分制) ==========
        momentum_score = 0

        rsi_series = self.indicators.rsi(close, 6)
        rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
        signal.rsi = rsi

        dif, dea, macd_hist = self.indicators.macd(close)
        signal.macd_dif = dif.iloc[-1] if not dif.empty else 0

        # 2.1 RSI评分 (40分) - 覆盖全区间
        if 40 < rsi < 60:
            momentum_score += 40
            signals.append(f"RSI理想({rsi:.0f})")
        elif 30 < rsi <= 40 or 60 <= rsi < 70:
            momentum_score += 30
            signals.append(f"RSI良好({rsi:.0f})")
        elif 20 < rsi <= 30 or 70 <= rsi < 80:
            momentum_score += 20
            signals.append(f"RSI可用({rsi:.0f})")
        elif 10 < rsi <= 20 or 80 <= rsi < 90:
            momentum_score += 10
            warnings.append(f"RSI极端({rsi:.0f})")
        else:
            momentum_score += 5
            warnings.append(f"RSI严重超买超卖({rsi:.0f})")
        
        # 2.2 MACD评分 (30分)
        current_dif = dif.iloc[-1] if not dif.empty else 0
        current_dea = dea.iloc[-1] if not dea.empty else 0
        prev_dif = dif.iloc[-2] if len(dif) >= 2 else current_dif
        prev_dea = dea.iloc[-2] if len(dea) >= 2 else current_dea

        if current_dif > current_dea and prev_dif <= prev_dea:
            momentum_score += 30
            signals.append("MACD金叉")
        elif current_dif > current_dea and current_dif > 0:
            momentum_score += 25
            signals.append("MACD水上")
        elif current_dif > current_dea:
            momentum_score += 20
            signals.append("MACD向上")
        elif current_dif > 0:
            momentum_score += 15
            signals.append("DIF为正")
        else:
            momentum_score += 10
            signals.append("MACD弱势")

        # 2.3 价格动量 (30分)
        if len(close) >= 5:
            change_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            change_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0

            if 5 < change_5d < 25:
                momentum_score += 20
                signals.append(f"5日强势({change_5d:.1f}%)")
            elif 2 < change_5d <= 5:
                momentum_score += 15
                signals.append(f"5日上涨({change_5d:.1f}%)")
            elif 0 < change_5d <= 2:
                momentum_score += 10
                signals.append(f"5日微涨({change_5d:.1f}%)")
            elif -3 < change_5d <= 0:
                momentum_score += 5
                signals.append(f"5日回调({change_5d:.1f}%)")

            if change_20d > 15:
                momentum_score += 10
                signals.append(f"20日强势({change_20d:.1f}%)")
            elif change_20d > 5:
                momentum_score += 5
                signals.append(f"20日上涨({change_20d:.1f}%)")
        
        # 2.1 RSI评分 (10分) - 策略自适应区间
        rsi_min, rsi_max = self.rsi_low, self.rsi_high
        rsi_mid = (rsi_min + rsi_max) / 2
        
        if rsi_min < rsi < rsi_max:
            # RSI在策略理想区间内
            distance_from_mid = abs(rsi - rsi_mid) / (rsi_max - rsi_min) * 2
            if distance_from_mid < 0.3:
                momentum_score += 10
                signals.append(f"RSI理想({rsi:.0f})")
            elif distance_from_mid < 0.6:
                momentum_score += 8
                signals.append(f"RSI良好({rsi:.0f})")
            else:
                momentum_score += 6
                signals.append(f"RSI可用({rsi:.0f})")
        else:
            # RSI在策略区间外，根据策略类型决定是否给分
            if self.strategy_name in ['均值回归']:
                # 均值回归策略允许超卖/超买
                momentum_score += 5
                signals.append(f"RSI极端({rsi:.0f})")
            else:
                warnings.append(f"RSI不适({rsi:.0f})")
        
        # 2.2 MACD评分 (10分)
        current_dif = dif.iloc[-1] if not dif.empty else 0
        current_dea = dea.iloc[-1] if not dea.empty else 0
        prev_dif = dif.iloc[-2] if len(dif) >= 2 else current_dif
        prev_dea = dea.iloc[-2] if len(dea) >= 2 else current_dea
        
        if current_dif > current_dea and prev_dif <= prev_dea:
            momentum_score += 10
            signals.append("MACD金叉")
        elif current_dif > current_dea and current_dif > 0:
            momentum_score += 8
            signals.append("MACD水上")
        elif current_dif > current_dea:
            momentum_score += 5
            signals.append("MACD向上")
        
        # 2.3 价格动量 (10分)
        if len(close) >= 5:
            change_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            change_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
            
            if 3 < change_5d < 15:  # 放宽到15%
                momentum_score += 8
                signals.append(f"5日涨幅适中({change_5d:.1f}%)")
            elif 0 < change_5d <= 3:
                momentum_score += 5
                signals.append(f"5日微涨({change_5d:.1f}%)")
            elif change_5d >= 15:
                momentum_score += 2
                warnings.append(f"5日涨幅过大({change_5d:.1f}%)")
            else:
                warnings.append(f"5日下跌({change_5d:.1f}%)")
            
            if change_20d > 10:
                momentum_score += 2
                signals.append(f"20日强势({change_20d:.1f}%)")
        
        signal.momentum_score = momentum_score
        
        # ========== 3. 成交量分析 (15分) ==========
        volume_score = 0
        
        if len(volume) >= 6:
            avg_volume = volume.iloc[-6:-1].mean()
            current_volume = volume.iloc[-1]
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            if 1.0 <= vol_ratio <= 3.0:
                volume_score += 15
                signals.append(f"量能理想({vol_ratio:.1f}倍)")
            elif 3.0 < vol_ratio <= 5.0:
                volume_score += 12
                signals.append(f"温和放量({vol_ratio:.1f}倍)")
            elif 0.5 <= vol_ratio < 1.0:
                volume_score += 10
                signals.append(f"量能正常({vol_ratio:.1f}倍)")
            elif 5.0 < vol_ratio <= 10.0:
                volume_score += 8
                warnings.append(f"放量较大({vol_ratio:.1f}倍)")
            elif 10.0 < vol_ratio <= 50.0:
                volume_score += 5
                warnings.append(f"放量过大({vol_ratio:.1f}倍)")
            elif vol_ratio > 50.0:
                volume_score += 2  # 极端放量，可能是异常或重大消息
                warnings.append(f"极端放量({vol_ratio:.1f}倍)")
            else:
                volume_score += 3
                warnings.append(f"量能不足({vol_ratio:.1f}倍)")
        
        signal.volume_score = volume_score
        
        # ========== 4. 质量因子 (10分) ==========
        quality_score = 0
        
        # 4.1 相对强度 (4分)
        if all_stocks_data:
            rs = self.calculate_relative_strength(stock_code, df, all_stocks_data)
            signal.relative_strength = rs
            if rs > 0.9:
                quality_score += 4
                signals.append(f"相对强度前10%")
            elif rs > 0.7:
                quality_score += 3
                signals.append(f"相对强度前30%")
            elif rs > 0.5:
                quality_score += 2
                signals.append(f"相对强度前50%")
            elif rs > 0.3:
                quality_score += 1
                signals.append(f"相对强度前70%")
        
        # 4.2 热点板块加分 (3分)
        if signal.is_hot_sector:
            quality_score += 3
            signals.append(f"热点板块:{signal.sector}")
        
        # 4.3 波动率控制 (3分) - 更宽松
        if len(close) >= 20:
            volatility = close.iloc[-20:].pct_change().std() * np.sqrt(252) * 100
            if volatility < 30:
                quality_score += 3
                signals.append("波动率低")
            elif volatility < 50:
                quality_score += 2
                signals.append("波动率适中")
            elif volatility < 70:
                quality_score += 1
                signals.append("波动率偏高")
            else:
                warnings.append(f"波动率过高({volatility:.0f}%)")
        
        signal.quality_score = quality_score
        
        # ========== 综合评分 ==========
        # 加权分数 (0-100分制)
        total_score = (
            trend_score * self.weights['trend'] +
            momentum_score * self.weights['momentum'] +
            volume_score * self.weights['volume'] +
            quality_score * self.weights['quality']
        )
        
        signal.total_score = round(total_score, 1)
        signal.trend_score = trend_score
        signal.momentum_score = momentum_score
        signal.volume_score = volume_score
        signal.quality_score = quality_score
        signal.signals = signals
        signal.warnings = warnings
        
        # 门槛检查 (满分100分制，门槛40分)
        if signal.total_score < 40:
            return None
        
        # 计算止损止盈
        atr_series = self.indicators.atr(high, low, close, 14)
        atr = atr_series.iloc[-1] if not atr_series.empty else current_price * 0.02
        
        signal.stop_loss = current_price - 2.5 * atr
        signal.stop_loss_pct = (current_price - signal.stop_loss) / current_price
        signal.take_profit_1 = current_price * 1.04
        signal.take_profit_2 = current_price * 1.08
        
        # 仓位建议 (100分制)
        if signal.total_score >= 90 and signal.is_hot_sector:
            signal.position_size = 0.25
            signal.confidence = 0.9
        elif signal.total_score >= 85:
            signal.position_size = 0.20
            signal.confidence = 0.8
        elif signal.total_score >= 80:
            signal.position_size = 0.15
            signal.confidence = 0.7
        else:
            signal.position_size = 0.10
            signal.confidence = 0.6
        
        return signal
    
    def scan_signals(self, max_stocks: int = 300) -> List[TradeSignal]:
        """扫描精选信号 - 每天最多5只"""
        log.info("🌬️ 南风V5.5 - 精选扫描...")
        
        # 检查市场环境
        market_ok, market_msg = self.check_market_environment()
        log.info(f"市场环境: {market_msg}")
        
        if not market_ok:
            log.warning("市场环境不佳，建议观望")
            return []
        
        # 获取股票列表
        stock_codes = self.get_all_stocks(limit=max_stocks)
        log.info(f"扫描 {len(stock_codes)} 只股票")
        
        # 预加载数据
        all_data = {}
        for code in stock_codes:
            df = self.get_stock_data(code, days=40)
            if df is not None:
                all_data[code] = df
        
        log.info(f"成功加载 {len(all_data)} 只股票数据")
        
        # 分析每只股票
        signals = []
        for i, (code, df) in enumerate(all_data.items()):
            try:
                signal = self.analyze_stock(code, df, all_data)
                if signal:
                    signals.append(signal)
                
                if (i + 1) % 100 == 0:
                    log.info(f"进度: {i+1}/{len(all_data)}, 已发现 {len(signals)} 个信号")
                    
            except Exception as e:
                log.debug(f"分析 {code} 失败: {e}")
                continue
        
        # 排序并精选Top 5
        signals.sort(key=lambda x: (x.total_score, x.relative_strength, x.is_hot_sector), reverse=True)
        selected = signals[:self.max_signals_per_day]
        
        log.info(f"\n发现 {len(signals)} 个合格信号，精选 Top {len(selected)}:")
        for i, s in enumerate(selected, 1):
            hot_tag = "🔥" if s.is_hot_sector else ""
            log.info(f"  {i}. {s.stock_code}: {s.total_score:.1f}分 {hot_tag}")
        
        return selected
    
    def format_signal(self, signal: TradeSignal) -> str:
        """格式化信号输出 - 包含详细得分构成"""
        hot_tag = "🔥热点 " if signal.is_hot_sector else ""
        name_tag = f"({signal.stock_name}) " if signal.stock_name else ""
        
        lines = [
            f"\n{'='*70}",
            f"📈 {signal.stock_code} {name_tag}{hot_tag}- {signal.total_score:.1f}分",
            f"{'='*70}",
            f"",
            f"💰 价格信息",
            f"  当前价格: ¥{signal.current_price:.2f}",
            f"  止损价格: ¥{signal.stop_loss:.2f} (跌幅 {signal.stop_loss_pct:.1%})",
            f"  目标价格: ¥{signal.take_profit_1:.2f} (+4%) / ¥{signal.take_profit_2:.2f} (+8%)",
            f"",
            f"📊 得分构成 (满分10分)",
            f"  ├─ 趋势得分:    {signal.trend_score * 0.4:.1f}分 (权重40% × {signal.trend_score:.0f}/100)",
            f"  ├─ 动量得分:    {signal.momentum_score * 0.3:.1f}分 (权重30% × {signal.momentum_score:.0f}/100)",
            f"  ├─ 成交量得分:  {signal.volume_score * 0.2:.1f}分 (权重20% × {signal.volume_score:.0f}/100)",
            f"  └─ 质量得分:    {signal.quality_score * 0.1:.1f}分 (权重10% × {signal.quality_score:.0f}/100)",
            f"  ─────────────────────────",
            f"  综合得分:       {signal.total_score:.1f}分",
            f"",
            f"📈 技术指标",
            f"  ADX(趋势强度):  {signal.adx:.1f} (门槛≥30)",
            f"  RSI(相对强弱):  {signal.rsi:.0f} (理想区间45-65)",
            f"  MACD(DIF):      {signal.macd_dif:.3f}",
            f"  MA20斜率:       {signal.ma20_slope*100:.2f}% (门槛≥0.2%)",
            f"  相对强度排名:   前{signal.relative_strength:.0%}",
        ]
        
        if signal.sector:
            lines.append(f"  所属板块:       {signal.sector}")
        
        lines.extend([
            f"",
            f"✅ 买入信号",
            f"  " + " | ".join(signal.signals[:5]),
        ])
        
        if signal.warnings:
            lines.extend([
                f"",
                f"⚠️ 风险提示",
                f"  " + " | ".join(signal.warnings[:3]),
            ])
        
        lines.extend([
            f"",
            f"💡 交易建议",
            f"  建议仓位: {signal.position_size:.0%} | 置信度: {signal.confidence:.0%}",
            f"{'='*70}"
        ])
        
        return '\n'.join(lines)


def main():
    """主函数"""
    nanfeng = NanFengV5_1()
    
    # 扫描信号
    signals = nanfeng.scan_signals(max_stocks=300)
    
    # 输出结果
    print("\n" + "="*60)
    print("🌬️ 南风V5.5 精选结果")
    print("="*60)
    
    if not signals:
        print("未发现符合条件的信号")
        return
    
    for signal in signals:
        print(nanfeng.format_signal(signal))
    
    # 保存结果
    output = {
        'scan_time': datetime.now().isoformat(),
        'version': 'V5.5',
        'market_check': nanfeng.check_market_environment()[1],
        'signals_count': len(signals),
        'signals': [
            {
                'code': s.stock_code,
                'score': s.total_score,
                'price': s.current_price,
                'stop_loss': s.stop_loss,
                'position': s.position_size,
                'confidence': s.confidence,
                'is_hot': s.is_hot_sector,
                'sector': s.sector,
                'signals': s.signals,
                'warnings': s.warnings
            }
            for s in signals
        ]
    }
    
    output_file = Path.home() / f"Documents/OpenClawAgents/nanfeng/signals/signals_v5_1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: {output_file}")


if __name__ == '__main__':
    main()
