#!/usr/bin/env python3
"""
南风回测分析 V2 - 优化版
基于最近30天数据验证打分效果
增加：中文名、板块、详细打分依据
优化：提高阈值、加入题材过滤、调整权重
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
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"
LOG_DIR = Path.home() / "Documents/OpenClawAgents/nanfeng/logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"backtest_v2_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("南风回测V2")


class NanfengBacktestV2:
    """南风回测器 V2 - 优化版"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
        self.hot_spots = self._load_hot_spots()
        self.stock_names = {}  # 缓存股票名称
        
        # 优化参数
        self.score_threshold = 8.5  # 提高阈值
        self.min_rsi = 45  # RSI下限
        self.max_rsi = 75  # RSI上限
        self.min_volume_ratio = 1.3  # 最小放量
        self.max_volume_ratio = 3.0  # 最大放量
        self.require_hot_sector = True  # 要求热点板块
    
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
                            hot_stocks[code] = {
                                'sector': sector,
                                'level': level,
                                'weight': stock.get('weight', 0)
                            }
                logger.info(f"加载热点: {len(hot_stocks)} 只股票")
            except Exception as e:
                logger.error(f"加载热点失败: {e}")
        return hot_stocks
    
    def get_stock_list(self) -> List[str]:
        """获取股票列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT stock_code FROM kline_data WHERE data_type='daily' LIMIT 200")
        stocks = [row[0] for row in cursor.fetchall()]
        conn.close()
        return stocks
    
    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        if stock_code in self.stock_names:
            return self.stock_names[stock_code]
        
        # 尝试从热点数据获取
        if stock_code in self.hot_spots:
            return self.hot_spots[stock_code].get('name', stock_code)
        
        # 尝试从数据库获取
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
        """, (stock_code, days + 15))
        
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
    
    def calculate_score(self, stock_code: str, data: List[Dict]) -> Tuple[float, Dict]:
        """
        计算股票得分 V2 - 优化版
        返回: (分数, 详细打分依据)
        """
        result = {
            'code': stock_code,
            'name': self.get_stock_name(stock_code),
            'sector': '未知',
            'sector_level': 'Low',
            'total_score': 0,
            'max_score': 10,
            'details': {},
            'signals': [],
            'passed': False
        }
        
        if len(data) < 15:
            result['details']['error'] = '数据不足15天'
            return 0, result
        
        closes = [d['close'] for d in data]
        volumes = [d['volume'] for d in data]
        current_price = closes[-1]
        
        score = 0
        details = {}
        signals = []
        
        # 1. 均线系统 (25分) - 降低权重
        ma5 = sum(closes[-5:]) / 5
        ma10 = sum(closes[-10:]) / 10
        ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma10
        
        ma_score = 0
        if current_price > ma5 > ma10:
            ma_score += 15
            signals.append("均线多头排列")
        elif current_price > ma5:
            ma_score += 8
            signals.append("站上MA5")
        
        if current_price > ma20:
            ma_score += 10
            signals.append("站稳MA20")
        
        score += ma_score
        details['均线'] = {'得分': ma_score, '满分': 25, 'MA5': round(ma5, 2), 'MA10': round(ma10, 2), 'MA20': round(ma20, 2)}
        
        # 2. MACD (25分) - 提高权重
        macd_score = 0
        if len(closes) >= 26:
            ema12 = self._ema(closes, 12) or 0
            ema26 = self._ema(closes, 26) or 0
            dif = ema12 - ema26
            
            if dif > 0:
                macd_score += 15
                signals.append("MACD正值")
            
            # 检查金叉
            prev_ema12 = self._ema(closes[:-1], 12) or 0
            prev_ema26 = self._ema(closes[:-1], 26) or 0
            prev_dif = prev_ema12 - prev_ema26
            
            if dif > 0 and prev_dif <= 0:
                macd_score += 10
                signals.append("MACD金叉")
            elif dif > prev_dif:
                macd_score += 5
                signals.append("MACD向上")
        
        score += macd_score
        details['MACD'] = {'得分': macd_score, '满分': 25, 'DIF': round(dif, 3) if len(closes) >= 26 else 'N/A'}
        
        # 3. RSI (20分) - 严格区间
        rsi = self._rsi(closes, 6)
        rsi_score = 0
        if rsi:
            if self.min_rsi < rsi < 55:  # 强势但不过热
                rsi_score = 20
                signals.append(f"RSI强势({rsi:.0f})")
            elif 55 <= rsi < self.max_rsi:
                rsi_score = 15
                signals.append(f"RSI良好({rsi:.0f})")
            elif rsi >= self.max_rsi:
                rsi_score = 5
                signals.append(f"RSI偏高({rsi:.0f})")
            elif rsi < self.min_rsi:
                rsi_score = 0
                signals.append(f"RSI偏弱({rsi:.0f})")
        
        score += rsi_score
        details['RSI'] = {'得分': rsi_score, '满分': 20, '值': round(rsi, 1) if rsi else 'N/A'}
        
        # 4. 成交量 (20分) - 严格区间
        vol_score = 0
        if len(volumes) >= 6:
            avg_volume = sum(volumes[-6:-1]) / 5
            if avg_volume > 0:
                vol_ratio = volumes[-1] / avg_volume
                if self.min_volume_ratio <= vol_ratio <= 2.0:
                    vol_score = 20
                    signals.append(f"完美放量({vol_ratio:.1f}倍)")
                elif 2.0 < vol_ratio <= self.max_volume_ratio:
                    vol_score = 15
                    signals.append(f"温和放量({vol_ratio:.1f}倍)")
                elif vol_ratio > self.max_volume_ratio:
                    vol_score = 5
                    signals.append(f"放量过大({vol_ratio:.1f}倍)")
                else:
                    signals.append(f"量能不足({vol_ratio:.1f}倍)")
                
                details['成交量'] = {'得分': vol_score, '满分': 20, '量比': round(vol_ratio, 2)}
        
        score += vol_score
        
        # 5. 题材加分 (10分) - 新增
        theme_score = 0
        if stock_code in self.hot_spots:
            hot_info = self.hot_spots[stock_code]
            result['sector'] = hot_info.get('sector', '未知')
            result['sector_level'] = hot_info.get('level', 'Low')
            
            if hot_info.get('level') == 'High':
                theme_score = 10
                signals.append(f"🔥High热点:{hot_info['sector']}")
            elif hot_info.get('level') == 'Medium':
                theme_score = 5
                signals.append(f"Medium热点:{hot_info['sector']}")
        else:
            if self.require_hot_sector:
                signals.append("❌非热点板块")
        
        score += theme_score
        details['题材'] = {'得分': theme_score, '满分': 10, '板块': result['sector'], '等级': result['sector_level']}
        
        # 6. 趋势强度 (额外加分，最高5分)
        trend_score = 0
        if len(closes) >= 5:
            # 计算5日涨幅
            change_5d = (closes[-1] / closes[-5] - 1) * 100
            if 3 < change_5d < 15:  # 3%-15%的涨幅最理想
                trend_score = 5
                signals.append(f"趋势良好(+{change_5d:.1f}%)")
            elif change_5d >= 15:
                trend_score = 2
                signals.append(f"涨幅过大(+{change_5d:.1f}%)")
            elif change_5d > 0:
                trend_score = 3
                signals.append(f"趋势向上(+{change_5d:.1f}%)")
            else:
                signals.append(f"趋势向下({change_5d:.1f}%)")
            
            details['趋势'] = {'加分': trend_score, '5日涨幅': round(change_5d, 1)}
        
        score += trend_score
        
        # 最终分数
        final_score = round(score, 1)
        result['total_score'] = final_score
        result['details'] = details
        result['signals'] = signals
        result['passed'] = (final_score >= self.score_threshold and 
                           (not self.require_hot_sector or stock_code in self.hot_spots))
        
        return final_score, result
    
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
    
    def simulate_return(self, data: List[Dict], hold_days: int = 5) -> float:
        """模拟持有N天的收益率"""
        if len(data) < hold_days + 1:
            return 0
        
        entry_price = data[-1]['close']
        exit_idx = max(0, len(data) - hold_days - 1)
        exit_price = data[exit_idx]['close']
        
        return (exit_price / entry_price - 1) * 100
    
    def run_backtest(self, hold_days: int = 5):
        """运行回测"""
        logger.info("=" * 80)
        logger.info(f"🌬️ 南风回测V2 - 最近30天数据 (优化版)")
        logger.info(f"买入阈值: {self.score_threshold}分")
        logger.info(f"RSI区间: {self.min_rsi}-{self.max_rsi}")
        logger.info(f"放量区间: {self.min_volume_ratio}-{self.max_volume_ratio}倍")
        logger.info(f"要求热点: {self.require_hot_sector}")
        logger.info("=" * 80)
        
        stocks = self.get_stock_list()
        logger.info(f"测试股票数: {len(stocks)}")
        
        results = []
        
        for i, code in enumerate(stocks):
            try:
                data = self.get_stock_data(code, days=30)
                if len(data) < 15:
                    continue
                
                # 计算得分
                score, detail = self.calculate_score(code, data)
                
                # 模拟收益
                actual_return = self.simulate_return(data, hold_days)
                
                results.append({
                    **detail,
                    'return_5d': round(actual_return, 2),
                    'current_price': data[-1]['close'],
                    'price_5d_ago': data[-6]['close'] if len(data) >= 6 else data[0]['close']
                })
                
                if (i + 1) % 50 == 0:
                    logger.info(f"进度: {i+1}/{len(stocks)}")
                
            except Exception as e:
                logger.debug(f"处理 {code} 失败: {e}")
                continue
        
        # 分析结果
        self._analyze_results(results)
        
        return results
    
    def _analyze_results(self, results: List[Dict]):
        """分析回测结果"""
        if not results:
            logger.warning("无回测结果")
            return
        
        # 分组统计
        selected = [r for r in results if r.get('passed', False)]
        not_selected = [r for r in results if not r.get('passed', False)]
        
        logger.info("=" * 80)
        logger.info("📊 回测结果分析")
        logger.info("=" * 80)
        
        logger.info(f"总测试数: {len(results)}")
        logger.info(f"✅ 选中数 (>= {self.score_threshold}分+热点): {len(selected)}")
        logger.info(f"❌ 未选中数: {len(not_selected)}")
        
        if selected:
            returns = [r['return_5d'] for r in selected]
            avg_return = statistics.mean(returns)
            win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
            max_return = max(returns)
            min_return = min(returns)
            
            logger.info(f"\n🎯 选中股票表现:")
            logger.info(f"  平均收益: {avg_return:+.2f}%")
            logger.info(f"  胜率: {win_rate:.1f}%")
            logger.info(f"  最高收益: {max_return:+.2f}%")
            logger.info(f"  最低收益: {min_return:+.2f}%")
            
            # 详细展示选中的股票
            logger.info(f"\n📋 选中股票详情 (按收益排序):")
            sorted_selected = sorted(selected, key=lambda x: x['return_5d'], reverse=True)
            for i, r in enumerate(sorted_selected[:15], 1):
                logger.info(f"\n  {i}. {r['name']} ({r['code']})")
                logger.info(f"     板块: {r['sector']} [{r['sector_level']}]")
                logger.info(f"     得分: {r['total_score']:.1f}/10")
                logger.info(f"     5日收益: {r['return_5d']:+.2f}%")
                logger.info(f"     信号: {', '.join(r['signals'][:4])}")
                logger.info(f"     打分依据:")
                for factor, info in r['details'].items():
                    if isinstance(info, dict) and '得分' in info:
                        logger.info(f"       - {factor}: {info['得分']}/{info.get('满分', '-')}")
        
        if not_selected:
            returns = [r['return_5d'] for r in not_selected]
            avg_return = statistics.mean(returns)
            win_rate = len([r for r in returns if r > 0]) / len(returns) * 100
            
            logger.info(f"\n📉 未选中股票表现:")
            logger.info(f"  平均收益: {avg_return:+.2f}%")
            logger.info(f"  胜率: {win_rate:.1f}%")
        
        # 分数分布
        score_ranges = {
            '9-10分': len([r for r in results if 9 <= r['total_score'] <= 10]),
            '8.5-9分': len([r for r in results if 8.5 <= r['total_score'] < 9]),
            '8-8.5分': len([r for r in results if 8 <= r['total_score'] < 8.5]),
            '7-8分': len([r for r in results if 7 <= r['total_score'] < 8]),
            '<7分': len([r for r in results if r['total_score'] < 7])
        }
        
        logger.info(f"\n📈 分数分布:")
        for range_name, count in score_ranges.items():
            logger.info(f"  {range_name}: {count}只")
        
        logger.info("=" * 80)
        
        # 保存结果
        self._save_results(results)
    
    def _save_results(self, results: List[Dict]):
        """保存回测结果"""
        output_file = Path.home() / "Documents/OpenClawAgents/nanfeng/data/backtest_v2_30d.json"
        output_file.parent.mkdir(exist_ok=True)
        
        output = {
            'backtest_date': datetime.now().isoformat(),
            'period': '30d',
            'config': {
                'score_threshold': self.score_threshold,
                'rsi_range': [self.min_rsi, self.max_rsi],
                'volume_range': [self.min_volume_ratio, self.max_volume_ratio],
                'require_hot_sector': self.require_hot_sector
            },
            'total_stocks': len(results),
            'results': sorted(results, key=lambda x: (x.get('passed', False), x['total_score']), reverse=True)
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 结果已保存: {output_file}")


def main():
    """主函数"""
    backtest = NanfengBacktestV2()
    
    # 运行回测
    results = backtest.run_backtest(hold_days=5)
    
    print("\n" + "=" * 80)
    print("🌬️ 南风V2回测完成")
    print("=" * 80)
    print("查看详细日志: ~/Documents/OpenClawAgents/nanfeng/logs/")
    print("查看结果文件: ~/Documents/OpenClawAgents/nanfeng/data/backtest_v2_30d.json")
    print("=" * 80)


if __name__ == "__main__":
    main()
