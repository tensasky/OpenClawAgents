#!/usr/bin/env python3
"""
南风回测分析 - 基于最近30天数据验证打分效果
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Tuple
import statistics

# 配置
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"backtest_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风回测")


class NanfengBacktest:
    """南风回测器"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.results = []
    
    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        # 从kline_data获取所有股票代码
        cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type='daily' LIMIT 100")
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def get_stock_data(self, stock_code: str, days: int = 30) -> List[Dict]:
        """获取股票最近N天数据"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume
            FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            ORDER BY timestamp DESC
            LIMIT ?
        """, (stock_code, days + 10))  # 多取10天用于计算指标
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                'timestamp': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5]
            }
            for row in reversed(rows)
        ]
    
    def calculate_score(self, data: List[Dict]) -> Tuple[float, List[str]]:
        """
        计算股票得分（南风V4算法）
        返回: (分数, 信号列表)
        """
        if len(data) < 10:
            return 0, []
        
        closes = [d['close'] for d in data]
        volumes = [d['volume'] for d in data]
        current_price = closes[-1]
        
        score = 0
        signals = []
        
        # 1. 均线系统 (30分)
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else ma5
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma10
        
        if current_price > ma5 > ma10:
            score += 20
            signals.append("均线多头排列")
        elif current_price > ma5:
            score += 10
            signals.append("站上MA5")
        
        if current_price > ma20:
            score += 10
            signals.append("价格在中轨之上")
        
        # 2. MACD (20分)
        if len(closes) >= 12:
            ema12 = self._ema(closes, 12) or 0
            ema26 = self._ema(closes, 26) or 0
            dif = ema12 - ema26
            if dif > 0:
                score += 15
                signals.append("MACD正值")
        
        # 3. RSI (15分)
        rsi = self._rsi(closes)
        if rsi and 50 < rsi < 70:
            score += 15
            signals.append(f"RSI强势({rsi:.0f})")
        elif rsi and 30 < rsi < 50:
            score += 10
            signals.append(f"RSI中性({rsi:.0f})")
        
        # 4. 成交量 (15分)
        if len(volumes) >= 6:
            avg_volume = sum(volumes[-6:-1]) / 5
            if avg_volume > 0:
                vol_ratio = volumes[-1] / avg_volume
                if 1.2 <= vol_ratio <= 2.5:
                    score += 15
                    signals.append(f"温和放量({vol_ratio:.1f}倍)")
                elif vol_ratio > 1.0:
                    score += 10
                    signals.append(f"量能配合({vol_ratio:.1f}倍)")
        
        # 5. 波动率 (10分)
        atr = self._atr(data[-10:])
        if atr:
            atr_pct = atr / current_price
            if 0.01 <= atr_pct <= 0.05:
                score += 10
        
        return min(score, 10), signals
    
    def _ema(self, data: list, period: int) -> float:
        """计算EMA"""
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def _rsi(self, closes: list, period: int = 6) -> float:
        """计算RSI"""
        if len(closes) < period + 1:
            return None
        gains = losses = 0
        for i in range(1, period + 1):
            change = closes[-i] - closes[-i-1]
            if change > 0:
                gains += change
            else:
                losses += abs(change)
        if losses == 0:
            return 100
        rs = gains / losses
        return 100 - (100 / (1 + rs))
    
    def _atr(self, data: list) -> float:
        """计算ATR"""
        if len(data) < 2:
            return None
        tr_list = []
        for i in range(1, len(data)):
            high = data[i]['high']
            low = data[i]['low']
            prev_close = data[i-1]['close']
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return sum(tr_list) / len(tr_list) if tr_list else None
    
    def simulate_return(self, data: List[Dict], hold_days: int = 5) -> float:
        """
        模拟持有N天的收益率
        返回: 收益率 (%)
        """
        if len(data) < hold_days + 1:
            return 0
        
        entry_price = data[-1]['close']  # 当前价格买入
        exit_price = data[-(hold_days+1)]['close'] if len(data) >= hold_days + 1 else data[0]['close']
        
        return (exit_price / entry_price - 1) * 100
    
    def run_backtest(self, score_threshold: float = 7.0, hold_days: int = 5):
        """
        运行回测
        score_threshold: 买入分数阈值
        hold_days: 持有天数
        """
        logger.info("=" * 60)
        logger.info(f"🌬️ 南风回测开始 - 最近30天数据")
        logger.info(f"买入阈值: {score_threshold}分, 持有: {hold_days}天")
        logger.info("=" * 60)
        
        stocks = self.get_stock_list()
        logger.info(f"测试股票数: {len(stocks)}")
        
        results = []
        
        for i, code in enumerate(stocks):
            try:
                data = self.get_stock_data(code, days=30)
                if len(data) < 10:
                    continue
                
                # 计算得分
                score, signals = self.calculate_score(data)
                
                # 模拟收益
                actual_return = self.simulate_return(data, hold_days)
                
                results.append({
                    'code': code,
                    'score': score,
                    'signals': signals,
                    'return': actual_return,
                    'selected': score >= score_threshold
                })
                
                if (i + 1) % 20 == 0:
                    logger.info(f"进度: {i+1}/{len(stocks)}")
                
            except Exception as e:
                logger.debug(f"处理 {code} 失败: {e}")
                continue
        
        # 分析结果
        self._analyze_results(results, score_threshold)
        
        return results
    
    def _analyze_results(self, results: List[Dict], threshold: float):
        """分析回测结果"""
        if not results:
            logger.warning("无回测结果")
            return
        
        # 分组统计
        selected = [r for r in results if r['selected']]
        not_selected = [r for r in results if not r['selected']]
        
        logger.info("=" * 60)
        logger.info("📊 回测结果分析")
        logger.info("=" * 60)
        
        logger.info(f"总测试数: {len(results)}")
        logger.info(f"选中数 (>= {threshold}分): {len(selected)}")
        logger.info(f"未选中数 (< {threshold}分): {len(not_selected)}")
        
        if selected:
            returns = [r['return'] for r in selected]
            avg_return = statistics.mean(returns)
            win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
            max_return = max(returns)
            min_return = min(returns)
            
            logger.info(f"\n🎯 选中股票表现:")
            logger.info(f"  平均收益: {avg_return:+.2f}%")
            logger.info(f"  胜率: {win_rate:.1f}%")
            logger.info(f"  最高收益: {max_return:+.2f}%")
            logger.info(f"  最低收益: {min_return:+.2f}%")
        
        if not_selected:
            returns = [r['return'] for r in not_selected]
            avg_return = statistics.mean(returns)
            win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
            
            logger.info(f"\n📉 未选中股票表现:")
            logger.info(f"  平均收益: {avg_return:+.2f}%")
            logger.info(f"  胜率: {win_rate:.1f}%")
        
        # Top 10 表现
        if selected:
            top10 = sorted(selected, key=lambda x: x['return'], reverse=True)[:10]
            logger.info(f"\n🏆 Top 10 收益股票:")
            for i, r in enumerate(top10, 1):
                logger.info(f"  {i}. {r['code']}: {r['return']:+.2f}% (得分: {r['score']:.1f})")
        
        # 分数分布
        score_ranges = {
            '8-10分': len([r for r in results if 8 <= r['score'] <= 10]),
            '7-8分': len([r for r in results if 7 <= r['score'] < 8]),
            '6-7分': len([r for r in results if 6 <= r['score'] < 7]),
            '<6分': len([r for r in results if r['score'] < 6])
        }
        
        logger.info(f"\n📈 分数分布:")
        for range_name, count in score_ranges.items():
            logger.info(f"  {range_name}: {count}只")
        
        logger.info("=" * 60)
        
        # 保存结果
        self._save_results(results)
    
    def _save_results(self, results: List[Dict]):
        """保存回测结果"""
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/backtest_30d.json"
        output_file.parent.mkdir(exist_ok=True)
        
        output = {
            'backtest_date': datetime.now().isoformat(),
            'period': '30d',
            'total_stocks': len(results),
            'results': sorted(results, key=lambda x: x['score'], reverse=True)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 结果已保存: {output_file}")


def main():
    """主函数"""
    backtest = NanfengBacktest()
    
    # 运行回测：买入阈值7分，持有5天
    results = backtest.run_backtest(score_threshold=7.0, hold_days=5)
    
    print("\n" + "=" * 60)
    print("🌬️ 南风30天回测完成")
    print("=" * 60)
    print("查看详细日志: ~/Documents/OpenClawAgents/nanfeng/logs/")
    print("查看结果文件: ~/Documents/OpenClawAgents/nanfeng/data/backtest_30d.json")
    print("=" * 60)


if __name__ == "__main__":
    main()
