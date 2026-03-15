#!/usr/bin/env python3
"""
nanfeng_v5_1.py - 南风量化交易引擎V5.1 (精选版)
核心改进：每天只选Top 5，大幅提高信号质量

V5.1关键改进：
1. 严格门槛 - 分数>=8.5, ADX>=30, MA20强势向上
2. 精选策略 - 每天最多选5只，按综合评分排序
3. 市场环境过滤 - 大盘ADX<20时暂停
4. 板块共振 - 优先选热点板块内的股票
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
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("南风")


# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"nanfeng_v5_1_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风V5.1")


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
    """南风V5.1 - 精选版"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.indicators = TechnicalIndicators()
        self.hot_spots = self._load_hot_spots()
        
        # V5.1 严格参数
        self.min_adx = 30              # 提高：强趋势要求
        self.min_ma20_slope = 0.002    # 提高：MA20日涨幅>0.2%
        self.min_volume_ratio = 1.2    # 保持：温和放量
        self.score_threshold = 8.5     # 提高：高分门槛
        self.max_signals_per_day = 5   # 新增：每天最多5只
        
        # 权重
        self.weights = {
            'trend': 0.40,
            'momentum': 0.30,
            'volume': 0.20,
            'quality': 0.10
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
                        if code:
                            hot_stocks[code] = {'sector': sector, 'level': level}
            except Exception as e:
                logger.error(f"加载热点失败: {e}")
        return hot_stocks
    
    def check_market_environment(self) -> Tuple[bool, str]:
        """检查市场环境 - 大盘趋势"""
        try:
            # 用上证指数判断市场环境
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume
                FROM daily
                WHERE stock_code = 'sh000001' AND data_type = 'daily'
                ORDER BY timestamp DESC
                LIMIT 30
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            if len(df) < 20:
                return True, "无法判断市场环境，默认允许"
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            
            # 计算大盘ADX
            adx_series = self.indicators.adx(df['high'], df['low'], df['close'], 14)
            market_adx = adx_series.iloc[-1] if not adx_series.empty else 0
            
            # 计算大盘MA20斜率
            ma20 = self.indicators.sma(df['close'], 20)
            ma20_slope = (ma20.iloc[-1] - ma20.iloc[-5]) / ma20.iloc[-5] if ma20.iloc[-5] > 0 else 0
            
            if market_adx < 20:
                return False, f"大盘无趋势ADX={market_adx:.1f}，建议观望"
            elif ma20_slope < -0.001:
                return False, f"大盘下跌MA20斜率={ma20_slope*100:.2f}%，建议观望"
            else:
                return True, f"大盘环境良好ADX={market_adx:.1f}，MA20斜率={ma20_slope*100:.2f}%"
                
        except Exception as e:
            logger.error(f"市场环境检查失败: {e}")
            return True, "检查失败，默认允许"
    
    def get_stock_data(self, stock_code: str, days: int = 60) -> Optional[pd.DataFrame]:
        """获取股票数据"""
        try:
            conn = sqlite3.connect(self.db_path)
            query = """
                SELECT timestamp, open, high, low, close, volume, amount
                FROM daily
                WHERE stock_code = ? AND data_type = 'daily'
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
            WHERE data_type = 'daily'
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
        """分析单只股票 - V5.1严格标准"""
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
        
        # 检查热点板块
        if stock_code in self.hot_spots:
            hot_info = self.hot_spots[stock_code]
            signal.is_hot_sector = hot_info.get('level') in ['High', 'Medium']
            signal.sector = hot_info.get('sector', '')
        
        # ========== 1. 趋势分析 (40分) ==========
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
        
        # 严格检查：ADX必须>=30
        if adx < self.min_adx:
            return None  # 直接淘汰
        
        # 严格检查：MA20必须强势向上
        if ma20_slope < self.min_ma20_slope:
            return None  # 直接淘汰
        
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
        
        # 1.2 MA20向上 (10分)
        if ma20_slope > 0.005:  # 日涨幅>0.5%
            trend_score += 10
            signals.append("MA20强势向上")
        elif ma20_slope > self.min_ma20_slope:
            trend_score += 7
            signals.append("MA20向上")
        
        # 1.3 趋势强度ADX (10分)
        if adx > 40:
            trend_score += 10
            signals.append(f"强趋势ADX={adx:.1f}")
        elif adx > self.min_adx:
            trend_score += 7
            signals.append(f"趋势良好ADX={adx:.1f}")
        
        # 1.4 长期趋势 (5分)
        if len(close) >= 60:
            if current_price > ma60 and ma20 > ma60:
                trend_score += 5
                signals.append("长期上升趋势")
        
        signal.trend_score = trend_score
        
        # ========== 2. 动量分析 (30分) ==========
        momentum_score = 0
        
        rsi_series = self.indicators.rsi(close, 6)
        rsi = rsi_series.iloc[-1] if not rsi_series.empty else 50
        signal.rsi = rsi
        
        dif, dea, macd_hist = self.indicators.macd(close)
        signal.macd_dif = dif.iloc[-1] if not dif.empty else 0
        
        # 2.1 RSI评分 (10分) - 严格区间 45-65
        if 45 < rsi < 55:
            momentum_score += 10
            signals.append(f"RSI健康({rsi:.0f})")
        elif 55 <= rsi < 60:
            momentum_score += 8
            signals.append(f"RSI良好({rsi:.0f})")
        elif 60 <= rsi < 65:
            momentum_score += 5
            warnings.append(f"RSI偏高({rsi:.0f})")
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
            
            if 3 < change_5d < 8:  # 理想区间
                momentum_score += 8
                signals.append(f"5日涨幅适中({change_5d:.1f}%)")
            elif 0 < change_5d <= 3:
                momentum_score += 5
                signals.append(f"5日微涨({change_5d:.1f}%)")
            elif change_5d >= 8:
                momentum_score += 2
                warnings.append(f"5日涨幅过大({change_5d:.1f}%)")
            else:
                warnings.append(f"5日下跌({change_5d:.1f}%)")
            
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
            
            if self.min_volume_ratio <= vol_ratio <= 2.0:
                volume_score += 20
                signals.append(f"量能理想({vol_ratio:.1f}倍)")
            elif 2.0 < vol_ratio <= 3.5:
                volume_score += 15
                signals.append(f"温和放量({vol_ratio:.1f}倍)")
            elif vol_ratio > 3.5:
                volume_score += 5
                warnings.append(f"放量过大({vol_ratio:.1f}倍)")
            else:
                warnings.append(f"量能不足({vol_ratio:.1f}倍)")
        
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
        
        # 4.2 热点板块加分 (3分)
        if signal.is_hot_sector:
            quality_score += 3
            signals.append(f"热点板块:{signal.sector}")
        
        # 4.3 波动率控制 (2分)
        if len(close) >= 20:
            volatility = close.iloc[-20:].pct_change().std() * np.sqrt(252) * 100
            if volatility < 40:
                quality_score += 2
                signals.append("波动率适中")
            elif volatility > 70:
                warnings.append(f"波动率过高({volatility:.0f}%)")
        
        signal.quality_score = quality_score
        
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
        
        # 严格门槛检查
        if signal.total_score < self.score_threshold:
            return None
        
        # 计算止损止盈
        atr_series = self.indicators.atr(high, low, close, 14)
        atr = atr_series.iloc[-1] if not atr_series.empty else current_price * 0.02
        
        signal.stop_loss = current_price - 2.5 * atr
        signal.stop_loss_pct = (current_price - signal.stop_loss) / current_price
        signal.take_profit_1 = current_price * 1.04
        signal.take_profit_2 = current_price * 1.08
        
        # 仓位建议
        if signal.total_score >= 9.0 and signal.is_hot_sector:
            signal.position_size = 0.25
            signal.confidence = 0.9
        elif signal.total_score >= 8.5:
            signal.position_size = 0.20
            signal.confidence = 0.8
        else:
            signal.position_size = 0.15
            signal.confidence = 0.7
        
        return signal
    
    def scan_signals(self, max_stocks: int = 300) -> List[TradeSignal]:
        """扫描精选信号 - 每天最多5只"""
        logger.info("🌬️ 南风V5.1 - 精选扫描...")
        
        # 检查市场环境
        market_ok, market_msg = self.check_market_environment()
        logger.info(f"市场环境: {market_msg}")
        
        if not market_ok:
            logger.warning("市场环境不佳，建议观望")
            return []
        
        # 获取股票列表
        stock_codes = self.get_all_stocks(limit=max_stocks)
        logger.info(f"扫描 {len(stock_codes)} 只股票")
        
        # 预加载数据
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
                if signal:
                    signals.append(signal)
                
                if (i + 1) % 100 == 0:
                    logger.info(f"进度: {i+1}/{len(all_data)}, 已发现 {len(signals)} 个信号")
                    
            except Exception as e:
                logger.debug(f"分析 {code} 失败: {e}")
                continue
        
        # 排序并精选Top 5
        signals.sort(key=lambda x: (x.total_score, x.relative_strength, x.is_hot_sector), reverse=True)
        selected = signals[:self.max_signals_per_day]
        
        logger.info(f"\n发现 {len(signals)} 个合格信号，精选 Top {len(selected)}:")
        for i, s in enumerate(selected, 1):
            hot_tag = "🔥" if s.is_hot_sector else ""
            logger.info(f"  {i}. {s.stock_code}: {s.total_score:.1f}分 {hot_tag}")
        
        return selected
    
    def format_signal(self, signal: TradeSignal) -> str:
        """格式化信号输出"""
        hot_tag = "🔥热点" if signal.is_hot_sector else ""
        lines = [
            f"\n{'='*60}",
            f"📈 {signal.stock_code} {hot_tag} - {signal.total_score:.1f}分",
            f"{'='*60}",
            f"价格: {signal.current_price:.2f}",
            f"止损: {signal.stop_loss:.2f} ({signal.stop_loss_pct:.1%})",
            f"止盈: {signal.take_profit_1:.2f} / {signal.take_profit_2:.2f}",
            f"",
            f"【评分明细】",
            f"  趋势: {signal.trend_score:.0f}/40 | 动量: {signal.momentum_score:.0f}/30",
            f"  成交量: {signal.volume_score:.0f}/20 | 质量: {signal.quality_score:.0f}/10",
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
    nanfeng = NanFengV5_1()
    
    # 扫描信号
    signals = nanfeng.scan_signals(max_stocks=300)
    
    # 输出结果
    log.info("\n" + "="*60)
    log.info("🌬️ 南风V5.1 精选结果")
    log.info("="*60)
    
    if not signals:
        log.info("未发现符合条件的信号")
        return
    
    for signal in signals:
        print(nanfeng.format_signal(signal))
    
    # 保存结果
    output = {
        'scan_time': datetime.now().isoformat(),
        'version': 'V5.1',
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
    
    log.info(f"\n💾 结果已保存: {output_file}")


if __name__ == '__main__':
    main()
