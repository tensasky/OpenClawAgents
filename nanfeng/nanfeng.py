#!/usr/bin/env python3
"""
nanfeng.py - 南风量化分析 Agent
基于北风数据，计算技术指标，识别交易信号，生成打分报告
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

# 配置
WORKSPACE = Path("/Users/roberto/Documents/OpenClawAgents/nanfeng")
DATA_DIR = WORKSPACE / "data"
LOG_DIR = WORKSPACE / "logs"
BEIFENG_DB = Path("/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db")

DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"nanfeng_{datetime.now():%Y%m%d}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风")


@dataclass
class SignalScore:
    """信号打分结果"""
    stock_code: str
    stock_name: str
    signal_time: datetime
    total_score: float  # 满分10分
    indicators: Dict[str, float]  # 各指标得分
    signals: List[str]  # 触发信号列表
    confidence: str  # high/medium/low


class TechnicalIndicators:
    """技术指标计算"""
    
    @staticmethod
    def ma(data: pd.Series, period: int) -> pd.Series:
        """简单移动平均线"""
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        """指数移动平均线"""
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def macd(data: pd.Series, fast=12, slow=26, signal=9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        """MACD指标"""
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        dif = ema_fast - ema_slow
        dea = TechnicalIndicators.ema(dif, signal)
        macd = (dif - dea) * 2
        return dif, dea, macd
    
    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n=9, m1=3, m2=3):
        """KDJ指标"""
        rsv = (close - low.rolling(window=n).min()) / (high.rolling(window=n).max() - low.rolling(window=n).min()) * 100
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j
    
    @staticmethod
    def rsi(data: pd.Series, period=14):
        """RSI指标"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def boll(data: pd.Series, period=20, std_dev=2):
        """布林带"""
        ma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        return upper, ma, lower


class SignalAnalyzer:
    """信号分析器"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
    
    def analyze_stock(self, df: pd.DataFrame) -> Optional[SignalScore]:
        """
        分析单只股票，生成打分
        
        Args:
            df: DataFrame with columns [timestamp, open, high, low, close, volume]
        
        Returns:
            SignalScore or None
        """
        if len(df) < 20:  # 需要至少20条数据
            return None
        
        df = df.sort_values('timestamp')
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        scores = {}
        signals = []
        
        # 1. 均线系统 (2分)
        scores['ma'] = self._score_ma(close)
        if scores['ma'] > 1.5:
            signals.append("均线多头排列")
        
        # 2. MACD (2分)
        scores['macd'] = self._score_macd(close)
        if scores['macd'] > 1.5:
            signals.append("MACD金叉")
        
        # 3. KDJ (1.5分)
        scores['kdj'] = self._score_kdj(high, low, close)
        if scores['kdj'] > 1.0:
            signals.append("KDJ超卖反弹")
        
        # 4. RSI (1.5分)
        scores['rsi'] = self._score_rsi(close)
        if scores['rsi'] > 1.0:
            signals.append("RSI强势")
        
        # 5. 布林带 (1.5分)
        scores['boll'] = self._score_boll(close)
        if scores['boll'] > 1.0:
            signals.append("布林带突破")
        
        # 6. 量能 (1.5分)
        scores['volume'] = self._score_volume(volume, close)
        if scores['volume'] > 1.0:
            signals.append("放量上涨")
        
        total_score = sum(scores.values())
        
        # 确定置信度
        if total_score >= 8:
            confidence = "high"
        elif total_score >= 6:
            confidence = "medium"
        else:
            confidence = "low"
        
        return SignalScore(
            stock_code=df['stock_code'].iloc[0] if 'stock_code' in df.columns else "",
            stock_name=df['stock_name'].iloc[0] if 'stock_name' in df.columns else "",
            signal_time=df['timestamp'].iloc[-1],
            total_score=round(total_score, 2),
            indicators=scores,
            signals=signals,
            confidence=confidence
        )
    
    def _score_ma(self, close: pd.Series) -> float:
        """均线打分 (满分2分)"""
        score = 0.0
        
        # 计算不同周期均线
        ma5 = self.indicators.ma(close, 5)
        ma10 = self.indicators.ma(close, 10)
        ma20 = self.indicators.ma(close, 20)
        ma60 = self.indicators.ma(close, 60)
        
        # 多头排列 (短期在长期之上)
        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            score += 0.8
        
        # 价格在60日均线之上
        if close.iloc[-1] > ma60.iloc[-1]:
            score += 0.6
        
        # 均线向上发散
        if ma5.iloc[-1] > ma5.iloc[-5] and ma10.iloc[-1] > ma10.iloc[-5]:
            score += 0.6
        
        return min(score, 2.0)
    
    def _score_macd(self, close: pd.Series) -> float:
        """MACD打分 (满分2分)"""
        score = 0.0
        
        dif, dea, macd = self.indicators.macd(close)
        
        # MACD金叉 (DIF上穿DEA)
        if dif.iloc[-2] < dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            score += 1.2
        
        # MACD在零轴之上
        if dif.iloc[-1] > 0 and dea.iloc[-1] > 0:
            score += 0.5
        
        # MACD柱状图扩大
        if macd.iloc[-1] > macd.iloc[-2] > macd.iloc[-3]:
            score += 0.3
        
        return min(score, 2.0)
    
    def _score_kdj(self, high: pd.Series, low: pd.Series, close: pd.Series) -> float:
        """KDJ打分 (满分1.5分)"""
        score = 0.0
        
        k, d, j = self.indicators.kdj(high, low, close)
        
        # KDJ金叉 (K上穿D)
        if k.iloc[-2] < d.iloc[-2] and k.iloc[-1] > d.iloc[-1]:
            score += 0.8
        
        # J值从超卖区反弹 (<20)
        if j.iloc[-2] < 20 and j.iloc[-1] > j.iloc[-2]:
            score += 0.7
        
        return min(score, 1.5)
    
    def _score_rsi(self, close: pd.Series) -> float:
        """RSI打分 (满分1.5分)"""
        score = 0.0
        
        rsi6 = self.indicators.rsi(close, 6)
        rsi12 = self.indicators.rsi(close, 12)
        
        # RSI在强势区 (>50)
        if rsi6.iloc[-1] > 50 and rsi12.iloc[-1] > 50:
            score += 0.6
        
        # RSI上升
        if rsi6.iloc[-1] > rsi6.iloc[-3]:
            score += 0.5
        
        # RSI未超买 (<80)
        if rsi6.iloc[-1] < 80:
            score += 0.4
        
        return min(score, 1.5)
    
    def _score_boll(self, close: pd.Series) -> float:
        """布林带打分 (满分1.5分)"""
        score = 0.0
        
        upper, middle, lower = self.indicators.boll(close)
        
        # 价格突破中轨向上
        if close.iloc[-2] < middle.iloc[-2] and close.iloc[-1] > middle.iloc[-1]:
            score += 0.8
        
        # 价格在中轨之上
        if close.iloc[-1] > middle.iloc[-1]:
            score += 0.4
        
        # 布林带开口向上 (波动率扩大)
        band_width = (upper - lower) / middle
        if band_width.iloc[-1] > band_width.iloc[-5]:
            score += 0.3
        
        return min(score, 1.5)
    
    def _score_volume(self, volume: pd.Series, close: pd.Series) -> float:
        """量能打分 (满分1.5分)"""
        score = 0.0
        
        # 成交量放大 (相比5日均量)
        vol_ma5 = volume.rolling(5).mean()
        if volume.iloc[-1] > vol_ma5.iloc[-1] * 1.5:
            score += 0.6
        
        # 量价齐升
        if close.iloc[-1] > close.iloc[-2] and volume.iloc[-1] > volume.iloc[-2]:
            score += 0.5
        
        # 成交量趋势向上
        if volume.iloc[-1] > volume.iloc[-3] > volume.iloc[-5]:
            score += 0.4
        
        return min(score, 1.5)


class NanFeng:
    """南风量化分析主类"""
    
    def __init__(self):
        self.analyzer = SignalAnalyzer()
        self.beifeng_db = BEIFENG_DB
    
    def get_stock_data(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """从北风数据库获取股票数据"""
        conn = sqlite3.connect(self.beifeng_db)
        
        # 获取日线数据
        query = f"""
        SELECT timestamp, open, high, low, close, volume, amount
        FROM kline_data
        WHERE stock_code = '{stock_code}' AND data_type = 'daily'
        AND timestamp >= date('now', '-{days} days')
        ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        df['stock_code'] = stock_code
        return df
    
    def scan_all_stocks(self, min_score: float = 6.0) -> List[SignalScore]:
        """
        扫描所有股票，找出符合条件的信号
        
        Args:
            min_score: 最低分数门槛（默认6分）
        """
        logger.info("🌪️ 南风启动 - 全市场扫描")
        
        # 获取所有股票列表
        conn = sqlite3.connect(self.beifeng_db)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type = 'daily'")
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        logger.info(f"扫描 {len(stocks)} 只股票...")
        
        results = []
        for i, stock_code in enumerate(stocks):
            try:
                df = self.get_stock_data(stock_code, days=30)
                if len(df) < 20:
                    continue
                
                score = self.analyzer.analyze_stock(df)
                if score and score.total_score >= min_score:
                    results.append(score)
                    logger.info(f"[{i+1}/{len(stocks)}] {stock_code} 得分: {score.total_score}")
                
            except Exception as e:
                logger.error(f"分析 {stock_code} 失败: {e}")
        
        # 按分数排序
        results.sort(key=lambda x: x.total_score, reverse=True)
        
        logger.info(f"扫描完成，发现 {len(results)} 只符合条件的股票")
        return results
    
    def generate_report(self, results: List[SignalScore], output_file: str = None):
        """生成分析报告"""
        if output_file is None:
            output_file = DATA_DIR / f"signals_{datetime.now():%Y%m%d_%H%M}.json"
        
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_stocks": len(results),
            "high_confidence": [r.__dict__ for r in results if r.confidence == "high"],
            "medium_confidence": [r.__dict__ for r in results if r.confidence == "medium"],
            "all_signals": [r.__dict__ for r in results]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        logger.info(f"报告已生成: {output_file}")
        return output_file


def main():
    """主函数"""
    import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("南风")

    
    parser = argparse.ArgumentParser(description='南风量化分析')
    parser.add_argument('--scan', action='store_true', help='扫描全市场')
    parser.add_argument('--stock', type=str, help='分析单只股票')
    parser.add_argument('--min-score', type=float, default=6.0, help='最低分数门槛')
    parser.add_argument('--output', type=str, help='输出文件')
    
    args = parser.parse_args()
    
    nanfeng = NanFeng()
    
    if args.stock:
        # 分析单只股票
        df = nanfeng.get_stock_data(args.stock)
        score = nanfeng.analyzer.analyze_stock(df)
        if score:
            log.info(f"\n📊 {args.stock} 分析结果:")
            log.info(f"  总分: {score.total_score}/10")
            log.info(f"  置信度: {score.confidence}")
            log.info(f"  信号: {', '.join(score.signals)}")
            log.info(f"  指标得分:")
            for indicator, value in score.indicators.items():
                log.info(f"    {indicator}: {value}")
    
    elif args.scan:
        # 扫描全市场
        results = nanfeng.scan_all_stocks(min_score=args.min_score)
        nanfeng.generate_report(results, args.output)
        
        # 打印前10名
        log.info("\n🏆 TOP 10 信号股票:")
        for i, r in enumerate(results[:10], 1):
            log.info(f"{i}. {r.stock_code} - {r.total_score}分 [{r.confidence}]")
            log.info(f"   信号: {', '.join(r.signals)}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
