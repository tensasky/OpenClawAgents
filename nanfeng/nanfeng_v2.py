#!/usr/bin/env python3
"""
nanfeng_v2.py - 南风量化分析 Agent V2
综合西风舆情 + 北风技术数据 + 尾盘异动系数(LAMI)
权重: 题材溢价40% + 技术多维60%，含风险控制减分项
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
BEIFENG_DB = Path("/Users/roberto/.openclaw/agents/beifeng/data/stocks.db")
XIFENG_DATA = Path("/Users/roberto/Documents/OpenClawAgents/xifeng/data/hot_spots.json")

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
    theme_score: float  # 题材溢价分 (0-4)
    tech_score: float   # 技术打分 (0-6)
    penalty_score: float # 减分项
    lami: float         # 尾盘异动系数
    indicators: Dict[str, float]
    signals: List[str]
    penalties: List[str]
    confidence: str
    hot_spot: str       # 关联热点板块


class XifengData:
    """西风舆情数据接口"""
    
    @staticmethod
    def load_hot_spots() -> Dict:
        """加载热点板块数据"""
        try:
            with open(XIFENG_DATA, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载西风数据失败: {e}")
            return {}
    
    @staticmethod
    def get_stock_hot_spot(stock_code: str, hot_spots: Dict) -> Tuple[str, str, float]:
        """
        获取股票关联的热点板块
        Returns: (板块名称, 热度等级, 溢价分)
        """
        # 解析西风数据格式
        summary = hot_spots.get('summary', [])
        
        for sector_data in summary:
            level = sector_data.get('level', 'Low')
            sector_name = sector_data.get('sector', '')
            
            # 检查股票是否在该板块的龙头股中
            leading_stocks = sector_data.get('leading_stocks', [])
            for stock in leading_stocks:
                code = stock.get('code', '')
                # 匹配股票代码（处理sh/sz前缀）
                if code in stock_code or stock_code.endswith(code):
                    if level == 'High':
                        return sector_name, 'high', 3.0
                    elif level == 'Medium':
                        return sector_name, 'medium', 1.5
                    else:
                        return sector_name, 'low', 0.5
        
        # 检查hot_spots列表
        hot_spots_list = hot_spots.get('hot_spots', [])
        for spot in hot_spots_list:
            level = spot.get('level', 'Low')
            sector_name = spot.get('sector', '')
            
            if level == 'High':
                return sector_name, 'high', 3.0
            elif level == 'Medium':
                return sector_name, 'medium', 1.5
        
        return '', 'low', 0.0


class TechnicalIndicators:
    """技术指标计算"""
    
    @staticmethod
    def ma(data: pd.Series, period: int) -> pd.Series:
        return data.rolling(window=period).mean()
    
    @staticmethod
    def ema(data: pd.Series, period: int) -> pd.Series:
        return data.ewm(span=period, adjust=False).mean()
    
    @staticmethod
    def macd(data: pd.Series, fast=12, slow=26, signal=9):
        ema_fast = TechnicalIndicators.ema(data, fast)
        ema_slow = TechnicalIndicators.ema(data, slow)
        dif = ema_fast - ema_slow
        dea = TechnicalIndicators.ema(dif, signal)
        macd = (dif - dea) * 2
        return dif, dea, macd
    
    @staticmethod
    def kdj(high: pd.Series, low: pd.Series, close: pd.Series, n=9, m1=3, m2=3):
        rsv = (close - low.rolling(window=n).min()) / (high.rolling(window=n).max() - low.rolling(window=n).min()) * 100
        k = rsv.ewm(alpha=1/m1, adjust=False).mean()
        d = k.ewm(alpha=1/m2, adjust=False).mean()
        j = 3 * k - 2 * d
        return k, d, j
    
    @staticmethod
    def rsi(data: pd.Series, period=14):
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))
    
    @staticmethod
    def boll(data: pd.Series, period=20, std_dev=2):
        ma = data.rolling(window=period).mean()
        std = data.rolling(window=period).std()
        upper = ma + (std * std_dev)
        lower = ma - (std * std_dev)
        return upper, ma, lower


class LAMICalculator:
    """尾盘异动系数计算器 (Last-hour Abnormal Momentum Index)"""
    
    @staticmethod
    def calculate(df: pd.DataFrame) -> float:
        """
        计算尾盘异动系数
        LAMI = (14:30后的涨幅 / 全天振幅) * (14:30后的成交量 / 全天平均每小时成交量)
        
        Returns:
            LAMI系数，>1.5表示尾盘抢筹信号
        """
        if len(df) < 2:
            return 0.0
        
        # 获取当日数据（最后一条）
        today = df.iloc[-1]
        
        # 计算14:30后的涨幅（简化：用收盘价-均价估算）
        price_change = today['close'] - today['open']
        amplitude = today['high'] - today['low']
        
        if amplitude == 0:
            return 0.0
        
        # 涨幅占比（简化计算）
        price_ratio = price_change / amplitude if amplitude > 0 else 0
        
        # 成交量占比（假设尾盘1小时占全天30%为正常）
        avg_volume = df['volume'].mean()
        if avg_volume == 0:
            return 0.0
        
        volume_ratio = today['volume'] / avg_volume
        
        # LAMI = 价格动量 * 成交量异常度
        lami = abs(price_ratio) * volume_ratio
        
        return round(lami, 2)


class SignalAnalyzer:
    """信号分析器 V2"""
    
    def __init__(self):
        self.indicators = TechnicalIndicators()
        self.lami_calc = LAMICalculator()
        self.xifeng = XifengData()
    
    def analyze_stock(self, stock_code: str, df: pd.DataFrame, 
                     hot_spots: Dict = None) -> Optional[SignalScore]:
        """
        综合打分分析
        
        总分 = 题材溢价(40%) + 技术多维(60%) - 减分项
        满分10分
        """
        if len(df) < 20:
            return None
        
        if hot_spots is None:
            hot_spots = self.xifeng.load_hot_spots()
        
        df = df.sort_values('timestamp')
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # ========== A. 题材溢价分 (权重40%，满分4分) ==========
        theme_score, hot_spot_name = self._score_theme(stock_code, hot_spots)
        
        # ========== B. 技术多维打分 (权重60%，满分6分) ==========
        tech_score, tech_signals = self._score_technical(df, close, high, low, volume)
        
        # ========== C. 减分项与风险控制 ==========
        penalty_score, penalties = self._calculate_penalties(df, close, volume, hot_spots)
        
        # ========== D. 尾盘异动系数 (LAMI) ==========
        lami = self.lami_calc.calculate(df)
        if lami > 1.5:
            tech_signals.append(f"尾盘抢筹(LAMI={lami})")
            tech_score = min(tech_score + 0.5, 6.0)  # LAMI加分
        
        # ========== 计算总分 ==========
        total_score = theme_score + tech_score - penalty_score
        total_score = max(0, min(10, total_score))  # 限制在0-10分
        
        # 置信度分级
        if total_score >= 8 and lami > 1.5:
            confidence = "high"
        elif total_score >= 6:
            confidence = "medium"
        else:
            confidence = "low"
        
        return SignalScore(
            stock_code=stock_code,
            stock_name="",
            signal_time=df['timestamp'].iloc[-1],
            total_score=round(total_score, 2),
            theme_score=round(theme_score, 2),
            tech_score=round(tech_score, 2),
            penalty_score=round(penalty_score, 2),
            lami=lami,
            indicators={},
            signals=tech_signals,
            penalties=penalties,
            confidence=confidence,
            hot_spot=hot_spot_name
        )
    
    def _score_theme(self, stock_code: str, hot_spots: Dict) -> Tuple[float, str]:
        """
        题材溢价打分 (满分4分)
        - 高热度板块关联: +3
        - 新热点首现(15天内): +1
        - 舆情反转: +0.5
        """
        score = 0.0
        spot_name, level, base_score = self.xifeng.get_stock_hot_spot(stock_code, hot_spots)
        
        score += base_score
        
        return min(score, 4.0), spot_name
    
    def _score_technical(self, df: pd.DataFrame, close: pd.Series, 
                        high: pd.Series, low: pd.Series, 
                        volume: pd.Series) -> Tuple[float, List[str]]:
        """
        技术多维打分 (满分6分)
        - 均线系统: 1.5分
        - MACD/KDJ: 1.5分
        - 量能: 1.5分
        - 布林带: 1分
        - RSI: 0.5分
        """
        score = 0.0
        signals = []
        
        # 1. 均线系统 (1.5分)
        ma5 = self.indicators.ma(close, 5)
        ma10 = self.indicators.ma(close, 10)
        ma20 = self.indicators.ma(close, 20)
        
        if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
            score += 1.0
            signals.append("均线多头排列")
        
        if close.iloc[-1] > ma20.iloc[-1]:
            score += 0.5
        
        # 2. MACD/KDJ (1.5分)
        dif, dea, macd = self.indicators.macd(close)
        if dif.iloc[-2] < dea.iloc[-2] and dif.iloc[-1] > dea.iloc[-1]:
            score += 0.8
            signals.append("MACD金叉")
        
        k, d, j = self.indicators.kdj(high, low, close)
        if j.iloc[-2] < 20 and j.iloc[-1] > j.iloc[-2]:
            score += 0.7
            signals.append("KDJ超卖反弹")
        
        # 3. 量能 (1.5分)
        vol_ma5 = volume.rolling(5).mean()
        if volume.iloc[-1] > vol_ma5.iloc[-1] * 1.3:
            score += 0.8
            signals.append("放量上涨")
        
        if close.iloc[-1] > close.iloc[-2] and volume.iloc[-1] > volume.iloc[-2]:
            score += 0.7
        
        # 4. 布林带 (1分)
        upper, middle, lower = self.indicators.boll(close)
        if close.iloc[-2] < middle.iloc[-2] and close.iloc[-1] > middle.iloc[-1]:
            score += 0.6
            signals.append("布林带中轨突破")
        
        if close.iloc[-1] > middle.iloc[-1]:
            score += 0.4
        
        # 5. RSI (0.5分)
        rsi = self.indicators.rsi(close, 6)
        if 50 < rsi.iloc[-1] < 70:
            score += 0.3
        if rsi.iloc[-1] > rsi.iloc[-3]:
            score += 0.2
        
        return min(score, 6.0), signals
    
    def _calculate_penalties(self, df: pd.DataFrame, close: pd.Series, 
                            volume: pd.Series, hot_spots: Dict) -> Tuple[float, List[str]]:
        """
        减分项与风险控制
        """
        penalty = 0.0
        penalties = []
        
        # 1. 上方抛压: 距离30天高点<2%且无放量 -2分
        high_30 = close.rolling(30).max()
        if (high_30.iloc[-1] - close.iloc[-1]) / high_30.iloc[-1] < 0.02:
            vol_ma5 = volume.rolling(5).mean()
            if volume.iloc[-1] < vol_ma5.iloc[-1] * 1.2:  # 无放量
                penalty += 2.0
                penalties.append("上方抛压(距高点<2%)")
        
        # 2. 量价背离: 价格涨但量缩 -3分
        if close.iloc[-1] > close.iloc[-5] and volume.iloc[-1] < volume.iloc[-5] * 0.8:
            penalty += 3.0
            penalties.append("量价背离")
        
        # 3. 西风预警: 板块热度骤降 -2分
        # 简化处理，实际需要对比历史数据
        
        # 4. 大盘熊市保护: 均线空头排列 -2分
        # 简化处理，实际需要大盘数据
        
        return penalty, penalties


class NanFeng:
    """南风量化分析主类 V2"""
    
    def __init__(self):
        self.analyzer = SignalAnalyzer()
        self.beifeng_db = BEIFENG_DB
    
    def get_stock_data(self, stock_code: str, days: int = 30) -> pd.DataFrame:
        """从北风数据库获取股票数据"""
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
    
    def scan_all_stocks(self, min_score: float = 6.0) -> List[SignalScore]:
        """扫描全市场"""
        logger.info("🌪️ 南风V2启动 - 全市场扫描")
        
        # 加载西风数据
        hot_spots = self.analyzer.xifeng.load_hot_spots()
        logger.info(f"加载西风热点: {len(hot_spots.get('high', []))} 个高热度板块")
        
        # 获取所有股票
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
                
                score = self.analyzer.analyze_stock(stock_code, df, hot_spots)
                if score and score.total_score >= min_score:
                    results.append(score)
                    logger.info(f"[{i+1}/{len(stocks)}] {stock_code} 得分: {score.total_score} "
                              f"(题材:{score.theme_score} 技术:{score.tech_score} LAMI:{score.lami})")
                
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
            "high_confidence": [self._score_to_dict(r) for r in results if r.confidence == "high"],
            "medium_confidence": [self._score_to_dict(r) for r in results if r.confidence == "medium"],
            "all_signals": [self._score_to_dict(r) for r in results]
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"报告已生成: {output_file}")
        return output_file
    
    def _score_to_dict(self, score: SignalScore) -> Dict:
        """转换Score为字典"""
        return {
            "stock_code": score.stock_code,
            "signal_time": str(score.signal_time),
            "total_score": score.total_score,
            "theme_score": score.theme_score,
            "tech_score": score.tech_score,
            "penalty_score": score.penalty_score,
            "lami": score.lami,
            "signals": score.signals,
            "penalties": score.penalties,
            "confidence": score.confidence,
            "hot_spot": score.hot_spot
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='南风量化分析V2')
    parser.add_argument('--scan', action='store_true', help='扫描全市场')
    parser.add_argument('--stock', type=str, help='分析单只股票')
    parser.add_argument('--min-score', type=float, default=6.0, help='最低分数门槛')
    parser.add_argument('--output', type=str, help='输出文件')
    
    args = parser.parse_args()
    
    nanfeng = NanFeng()
    
    if args.stock:
        df = nanfeng.get_stock_data(args.stock)
        hot_spots = nanfeng.analyzer.xifeng.load_hot_spots()
        score = nanfeng.analyzer.analyze_stock(args.stock, df, hot_spots)
        
        if score:
            print(f"\n📊 {args.stock} 分析结果:")
            print(f"  总分: {score.total_score}/10 (题材:{score.theme_score} + 技术:{score.tech_score} - 惩罚:{score.penalty_score})")
            print(f"  LAMI: {score.lami} {'✅尾盘抢筹' if score.lami > 1.5 else ''}")
            print(f"  置信度: {score.confidence}")
            print(f"  热点板块: {score.hot_spot}")
            print(f"  买入信号: {', '.join(score.signals) if score.signals else '无'}")
            print(f"  风险提示: {', '.join(score.penalties) if score.penalties else '无'}")
    
    elif args.scan:
        results = nanfeng.scan_all_stocks(min_score=args.min_score)
        nanfeng.generate_report(results, args.output)
        
        print("\n🏆 TOP 10 信号股票:")
        for i, r in enumerate(results[:10], 1):
            lami_flag = "🔥" if r.lami > 1.5 else ""
            print(f"{i}. {r.stock_code} - {r.total_score}分 {lami_flag} [{r.confidence}]")
            print(f"   题材:{r.theme_score} 技术:{r.tech_score} LAMI:{r.lami}")
            print(f"   信号: {', '.join(r.signals[:3])}")
    
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
