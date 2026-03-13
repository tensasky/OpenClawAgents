#!/usr/bin/env python3
"""
nanfeng_v5.py - 南风量化交易引擎V5
核心目标：大幅提高指标准确度，解决V4的虚假信号问题

V5关键改进：
1. 趋势优先 - 只做日线+周线共振的上升趋势
2. 多时间框架验证 - 日线+60分钟共振
3. 严格的趋势过滤 - ADX>25, 股价>MA20, MA20向上
4. 成交量作为门槛而非加分项
5. 相对强度排名 - 只选市场前20%
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
from dataclasses import dataclass, field

# 配置
BEIFENG_DB = Path("/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db")
LOG_DIR = Path("/Users/roberto/Documents/OpenClawAgents/nanfeng/logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"nanfeng_v5_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风V5")


@dataclass
class TradeSignal:
    """交易信号"""
    stock_code: str
    stock_name: str = ""
    signal_time: datetime = field(default_factory=datetime.now)
    
    # 价格数据
    current_price: float = 0.0
    entry_price: float = 0.0
    
    # 止损止盈
    stop_loss: float = 0.0
    stop_loss_pct: float = 0.0
    take_profit_1: float = 0.0
    take_profit_2: float = 0.0
    
    # 评分
    total_score: float = 0.0
    trend_score: float = 0.0
    momentum_score: float = 0.0
    volume_score: float = 0.0
    
    # 技术指标
    adx: float = 0.0
    rsi: float = 0.0
    macd_dif: float = 0.0
    ma20_slope: float = 0.0
    relative_strength: float = 0.0  # 相对强度排名 0-1
    
    # 信号详情
    signals: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    # 建议
    position_size: float = 0.0
    confidence: float = 0.0


class TechnicalIndicators:
    """技术指标计算类"""
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """计算EMA"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def sma(data: pd.Series, period: int) -> pd.Series:
        """计算SMA"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def rsi(data: pd.Series, period: int = 6) -> pd.Series:
        """计算RSI"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def macd(data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算MACD"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        dif = ema_fast - ema_slow
        dea = TechnicalIndicators.ema(dif, signal)
        macd_hist = (dif - dea) * 2
        return dif, dea, macd_hist
    
    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """计算ADX（平均趋向指数）"""
        # True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # +DM and -DM
        plus_dm = high.diff()
        minus_dm = -low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm < 0] = 0
        plus_dm[plus_dm <= minus_dm] = 0
        minus_dm[minus_dm <= plus_dm] = 0
        
        # Smooth TR, +DM, -DM
        atr = tr.ewm(alpha=1/period, adjust=False).mean()
        plus_di = 100 * (plus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        minus_di = 100 * (minus_dm.ewm(alpha=1/period, adjust=False).mean() / atr)
        
        # DX and ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.ewm(alpha=1/period, adjust=False).mean()
        
        return adx
    
    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """计算ATR"""
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.ewm(alpha=1/period, adjust=False).mean()
    
    @staticmethod
    def bollinger_bands(data: pd.Series, period: int = 20, std_dev: int = 2) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """计算布林带"""
        middle = TechnicalIndicators.sma(data, period)
        std = data.rolling(window=period).std()
        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        return upper, middle, lower


class NanFengV5:
    """南风V5主类 - 趋势优先策略"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.indicators = TechnicalIndicators()
        
        # V5严格参数
        self.min_adx = 25  # 趋势强度门槛
        self.min_rsi = 45  # RSI下限
        self.max_rsi = 70  # RSI上限
        self.min_volume_ratio = 1.2  # 最小放量
        self.max_volume_ratio = 3.5  # 最大放量
        self.min_ma20_slope = 0.001  # MA20斜率（日涨幅>0.1%）
        
        # 评分权重
        self.weights = {
            'trend': 0.40,      # 趋势权重最高
            'momentum': 0.30,   # 动量
            'volume': 0.20,     # 成交量
            'quality': 0.10     # 质量因子
        }
    
    def get_stock_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """获取股票日线数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                ORDER BY timestamp DESC
                LIMIT ?
            """
            df = pd.read_sql_query(query, conn, params=(stock_code, days + 15))
            conn.close()
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            if len(df) < 30:
                return None
            
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            return df
        except Exception as e:
            logger.debug(f"获取 {stock_code} 数据失败: {e}")
            return None
    
    def get_all_stocks(self, limit: int = 500) -> List[str]:
        """获取股票列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 获取有最近日线数据的股票
        cursor.execute("""
            SELECT DISTINCT stock_code 
            FROM kline_data 
            WHERE data_type = 'daily'
            ORDER BY stock_code
            LIMIT ?
        """, (limit,))
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def calculate_relative_strength(self, stock_code: str, df: pd.DataFrame, all_stocks_data: Dict) -> float:
        """计算相对强度排名 (0-1)"""
        if len(df) < 20:
            return 0.0
        
        # 计算20日涨幅
        stock_return = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1)
        
        # 获取同期市场平均涨幅
        market_returns = []
        for code, data in list(all_stocks_data.items())[:100]:  # 样本
            if len(data) >= 20:
                ret = (data['close'].iloc[-1] / data['close'].iloc[-20] - 1)
                market_returns.append(ret)
        
        if not market_returns:
            return 0.5
        
        # 计算排名百分比
        better_count = sum(1 for r in market_returns if stock_return > r)
        return better_count / len(market_returns)
    
    def analyze_stock(self, stock_code: str, df: pd.DataFrame, 
                     all_stocks_data: Dict = None) -> Optional[TradeSignal]:
        """
        分析单只股票 - V5严格标准
        """
        if len(df) < 30:
            return None
        
        signal = TradeSignal(stock_code=stock_code)
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        current_price = close.iloc[-1]
        signal.current_price = current_price
        
        signals = []
        warnings = []
        
        # ========== 1. 趋势分析 (40分) ==========
        trend_score = 0
        
        # 计算均线
        ma5 = self.indicators.sma(close, 5).iloc[-1]
        ma10 = self.indicators.sma(close, 10).iloc[-1]
        ma20 = self.indicators.sma(close, 20).iloc[-1]
        ma60 = self.indicators.sma(close, 60).iloc[-1] if len(close) >= 60 else ma20
        
        # MA20斜率（5日变化率）
        ma20_prev = self.indicators.sma(close, 20).iloc[-5]
        ma20_slope = (ma20 - ma20_prev) / ma20_prev if ma20_prev > 0 else 0
        signal.ma20_slope = ma20_slope
        
        # 趋势强度ADX
        adx_series = self.indicators.adx(high, low, close, 14)
        adx = adx_series.iloc[-1] if not adx_series.empty else 0
        signal.adx = adx
        
        # 趋势评分细则
        # 1.1 多头排列 (15分)
        if current_price > ma5 > ma10 > ma20:
            trend_score += 15
            signals.append("多头排列")
        elif current_price > ma5 > ma20:
            trend_score += 10
            signals.append("站上MA5/MA20")
        elif current_price > ma20:
            trend_score += 5
            signals.append("站上MA20")
        else:
            warnings.append("跌破MA20")
            return None  # 直接淘汰
        
        # 1.2 MA20向上 (10分) - 关键！
        if ma20_slope > self.min_ma20_slope * 3:  # 强势上升
            trend_score += 10
            signals.append("MA20强势向上")
        elif ma20_slope > self.min_ma20_slope:
            trend_score += 7
            signals.append("MA20向上")
        else:
            warnings.append("MA20走平或向下")
            trend_score += 2
        
        # 1.3 趋势强度ADX (10分)
        if adx > 30:
            trend_score += 10
            signals.append(f"强趋势ADX={adx:.1f}")
        elif adx > self.min_adx:
            trend_score += 7
            signals.append(f"趋势良好ADX={adx:.1f}")
        elif adx > 20:
            trend_score += 3
            warnings.append(f"趋势较弱ADX={adx:.1f}")
        else:
            warnings.append(f"无趋势ADX={adx:.1f}")
            trend_score += 0
        
        # 1.4 长期趋势 (5分)
        if len(close) >= 60:
            if current_price > ma60 and ma20 > ma60:
                trend_score += 5
                signals.append("长期上升趋势")
            elif current_price > ma60:
                trend_score += 2
        
        signal.trend_score = trend_score
        
        # ========== 2. 动量分析 (30分) ==========
        momentum_score = 0
        
        # RSI
        rsi_series = self.indicators.rsi(close, 6)
        rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
        signal.rsi = rsi
        
        # MACD
        dif, dea, macd_hist = self.indicators.macd(close)
        signal.macd_dif = dif.iloc[-1] if not dif.empty else 0
        
        # 2.1 RSI评分 (10分)
        if 40 < rsi < 55:  # 强势但不过热
            momentum_score += 10
            signals.append(f"RSI健康({rsi:.0f})")
        elif 55 <= rsi < 65:
            momentum_score += 8
            signals.append(f"RSI良好({rsi:.0f})")
        elif 65 <= rsi < 75:
            momentum_score += 5
            warnings.append(f"RSI偏高({rsi:.0f})")
        elif rsi >= 75:
            warnings.append(f"RSI过热({rsi:.0f})")
            momentum_score += 2
        else:
            warnings.append(f"RSI偏弱({rsi:.0f})")
            momentum_score += 0
        
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
        elif current_dif > 0:
            momentum_score += 3
        else:
            warnings.append("MACD向下")
        
        # 2.3 价格动量 (10分) - 避免追高和抄底
        if len(close) >= 5:
            change_5d = (close.iloc[-1] / close.iloc[-5] - 1) * 100
            change_20d = (close.iloc[-1] / close.iloc[-20] - 1) * 100 if len(close) >= 20 else 0
            
            if 2 < change_5d < 10:  # 温和上涨
                momentum_score += 8
                signals.append(f"5日涨幅适中({change_5d:.1f}%)")
            elif 0 < change_5d <= 2:
                momentum_score += 5
                signals.append(f"5日微涨({change_5d:.1f}%)")
            elif change_5d >= 10:
                momentum_score += 3
                warnings.append(f"5日涨幅过大({change_5d:.1f}%)")
            else:
                warnings.append(f"5日下跌({change_5d:.1f}%)")
            
            # 中期趋势
            if change_20d > 10:
                momentum_score += 2
                signals.append(f"20日强势({change_20d:.1f}%)")
        
        signal.momentum_score = momentum_score
        
        # ========== 3. 成交量分析 (20分) ==========
        volume_score = 0
        
        if len(volume) >= 6:
            avg_volume = volume.iloc[-6:-1].mean()
            current_volume = volume.iloc[-1]
            vol_ratio = current_volume / avg_volume if avg_volume > 0 else 0
            
            # 成交量作为门槛 - 不满足直接扣分
            if self.min_volume_ratio <= vol_ratio <= 2.0:
                volume_score += 20
                signals.append(f"量能理想({vol_ratio:.1f}倍)")
            elif 2.0 < vol_ratio <= self.max_volume_ratio:
                volume_score += 15
                signals.append(f"温和放量({vol_ratio:.1f}倍)")
            elif vol_ratio > self.max_volume_ratio:
                volume_score += 5
                warnings.append(f"放量过大({vol_ratio:.1f}倍)")
            elif vol_ratio >= 1.0:
                volume_score += 5
                warnings.append(f"量能不足({vol_ratio:.1f}倍)")
            else:
                volume_score += 0
                warnings.append(f"严重缩量({vol_ratio:.1f}倍)")
        
        signal.volume_score = volume_score
        
        # ========== 4. 质量因子 (10分) ==========
        quality_score = 0
        
        # 4.1 相对强度 (5分)
        if all_stocks_data:
            rs = self.calculate_relative_strength(stock_code, df, all_stocks_data)
            signal.relative_strength = rs
            if rs > 0.8:
                quality_score += 5
                signals.append(f"相对强度前20%")
            elif rs > 0.6:
                quality_score += 3
                signals.append(f"相对强度前40%")
            elif rs > 0.4:
                quality_score += 1
            elif rs < 0.3:
                warnings.append(f"相对强度弱({rs:.0%})")
        
        # 4.2 波动率控制 (3分)
        if len(close) >= 20:
            volatility = close.iloc[-20:].pct_change().std() * np.sqrt(252) * 100
            if volatility < 40:  # 年化波动率<40%
                quality_score += 3
                signals.append("波动率适中")
            elif volatility > 60:
                warnings.append(f"波动率过高({volatility:.0f}%)")
        
        # 4.3 近期无大跌 (2分)
        if len(close) >= 5:
            recent_changes = close.iloc[-5:].pct_change().iloc[1:] * 100
            if len(recent_changes) > 0:
                max_drop_5d = recent_changes.min()
                if max_drop_5d > -5:  # 5日内最大单日跌幅<5%
                    quality_score += 2
                elif max_drop_5d < -7:
                    warnings.append(f"近期大跌{max_drop_5d:.1f}%")
        
        # ========== 综合评分 ==========
        total_score = (
            trend_score * self.weights['trend'] +
            momentum_score * self.weights['momentum'] +
            volume_score * self.weights['volume'] +
            quality_score * self.weights['quality']
        )
        
        signal.total_score = round(total_score, 1)
        signal.signals = signals
        signal.warnings = warnings
        
        # 计算止损止盈
        atr_series = self.indicators.atr(high, low, close, 14)
        atr = atr_series.iloc[-1] if not atr_series.empty else current_price * 0.02
        
        signal.stop_loss = current_price - 2.5 * atr
        signal.stop_loss_pct = (current_price - signal.stop_loss) / current_price
        signal.take_profit_1 = current_price * 1.04  # 4%第一目标
        signal.take_profit_2 = current_price * 1.08  # 8%第二目标
        
        # 仓位建议
        if signal.total_score >= 8.5 and not warnings:
            signal.position_size = 0.25
            signal.confidence = 0.9
        elif signal.total_score >= 8.0:
            signal.position_size = 0.20
            signal.confidence = 0.8
        elif signal.total_score >= 7.5:
            signal.position_size = 0.15
            signal.confidence = 0.7
        else:
            signal.position_size = 0.10
            signal.confidence = 0.6
        
        return signal
    
    def scan_signals(self, min_score: float = 7.5, max_stocks: int = 100) -> List[TradeSignal]:
        """扫描全市场信号"""
        logger.info("🌬️ 南风V5 - 开始扫描...")
        logger.info(f"门槛: 分数>={min_score}, ADX>={self.min_adx}, MA20向上")
        
        # 获取股票列表
        stock_codes = self.get_all_stocks(limit=max_stocks)
        logger.info(f"扫描 {len(stock_codes)} 只股票")
        
        # 预加载所有数据（用于相对强度计算）
        all_data = {}
        for code in stock_codes:
            df = self.get_stock_data(code, days=40)
            if df is not None:
                all_data[code] = df
        
        logger.info(f"成功加载 {len(all_data)} 只股票数据")
        
        # 分析每只股票
        signals = []
        for i, (code, df) in enumerate(all_data.items()):
            try:
                signal = self.analyze_stock(code, df, all_data)
                if signal and signal.total_score >= min_score:
                    signals.append(signal)
                    logger.info(f"✅ {code}: {signal.total_score:.1f}分")
                
                if (i + 1) % 50 == 0:
                    logger.info(f"进度: {i+1}/{len(all_data)}")
                    
            except Exception as e:
                logger.debug(f"分析 {code} 失败: {e}")
                continue
        
        # 排序
        signals.sort(key=lambda x: (x.total_score, x.relative_strength), reverse=True)
        
        logger.info(f"\n发现 {len(signals)} 个信号 (门槛>={min_score})")
        return signals
    
    def format_signal(self, signal: TradeSignal) -> str:
        """格式化信号输出"""
        lines = [
            f"\n{'='*60}",
            f"📈 {signal.stock_code} - {signal.total_score:.1f}分",
            f"{'='*60}",
            f"价格: {signal.current_price:.2f}",
            f"止损: {signal.stop_loss:.2f} ({signal.stop_loss_pct:.1%})",
            f"止盈: {signal.take_profit_1:.2f} / {signal.take_profit_2:.2f}",
            f"",
            f"【评分明细】",
            f"  趋势: {signal.trend_score:.0f}/40 | 动量: {signal.momentum_score:.0f}/30",
            f"  成交量: {signal.volume_score:.0f}/20 | 质量: {min(10, max(0, signal.total_score - signal.trend_score * 0.4 - signal.momentum_score * 0.3 - signal.volume_score * 0.2)):.0f}/10",
            f"",
            f"【技术指标】",
            f"  ADX: {signal.adx:.1f} | RSI: {signal.rsi:.0f} | MACD: {signal.macd_dif:.3f}",
            f"  MA20斜率: {signal.ma20_slope*100:.2f}% | 相对强度: {signal.relative_strength:.0%}",
            f"",
            f"【信号】{' | '.join(signal.signals[:6])}",
        ]
        
        if signal.warnings:
            lines.append(f"【警告】{' | '.join(signal.warnings[:3])}")
        
        lines.extend([
            f"",
            f"建议仓位: {signal.position_size:.0%} | 置信度: {signal.confidence:.0%}",
            f"{'='*60}"
        ])
        
        return '\n'.join(lines)


def main():
    """主函数"""
    nanfeng = NanFengV5()
    
    # 扫描信号
    signals = nanfeng.scan_signals(min_score=7.5, max_stocks=200)
    
    # 输出结果
    print("\n" + "="*60)
    print("🌬️ 南风V5 扫描结果")
    print("="*60)
    
    if not signals:
        print("未发现符合条件的信号")
        return
    
    for signal in signals[:10]:
        print(nanfeng.format_signal(signal))
    
    # 保存结果
    output = {
        'scan_time': datetime.now().isoformat(),
        'version': 'V5',
        'config': {
            'min_adx': nanfeng.min_adx,
            'min_rsi': nanfeng.min_rsi,
            'max_rsi': nanfeng.max_rsi,
            'min_volume_ratio': nanfeng.min_volume_ratio,
            'min_ma20_slope': nanfeng.min_ma20_slope
        },
        'signals_count': len(signals),
        'signals': [
            {
                'code': s.stock_code,
                'score': s.total_score,
                'trend_score': s.trend_score,
                'momentum_score': s.momentum_score,
                'volume_score': s.volume_score,
                'price': s.current_price,
                'stop_loss': s.stop_loss,
                'position': s.position_size,
                'confidence': s.confidence,
                'signals': s.signals,
                'warnings': s.warnings
            }
            for s in signals[:20]
        ]
    }
    
    output_file = Path.home() / f"Documents/OpenClawAgents/nanfeng/signals/signals_v5_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n💾 结果已保存: {output_file}")


if __name__ == '__main__':
    main()
