#!/usr/bin/env python3
"""
白板 (The Whiteboard) —— 策略进化与回测系统
收盘后/周末全量回测，策略进化，动态调整参数
"""

import json
import sys
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
import statistics

# 导入统一日志
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
REPORT_DIR = BASE_DIR / "reports"

# 输入文件
FACAI_DB = Path.home() / "Documents/OpenClawAgents/facai/data/portfolio.db"
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"

# 输出文件
BACKTEST_RESULTS = DATA_DIR / "backtest_results.json"
SENTIMENT_STATE = DATA_DIR / "sentiment_state.json"
EVOLUTION_LOG = DATA_DIR / "evolution_log.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
REPORT_DIR.mkdir(exist_ok=True)

# 初始化日志
log = get_logger("白板")


@dataclass
class TradeRecord:
    """交易记录"""
    timestamp: str
    action: str
    symbol: str
    name: str
    price: float
    quantity: int
    total_amount: float
    logic: str
    total_assets: float


@dataclass
class BacktestResult:
    """回测结果"""
    period: str
    total_trades: int
    win_rate: float
    avg_profit: float
    max_drawdown: float
    total_return: float
    sharpe_ratio: float


@dataclass
class EvolutionCommand:
    """进化指令"""
    timestamp: str
    market_sentiment: str
    nanfeng_adjustments: Dict
    dongfeng_adjustments: Dict
    facai_adjustments: Dict
    reason: str


class TradeLoader:
    """交易记录加载器"""
    
    def load_facai_trades(self, days: int = 30) -> List[TradeRecord]:
        """加载发财的交易记录"""
        trades = []
        
        try:
            conn = sqlite3.connect(FACAI_DB)
            cursor = conn.cursor()
            
            since = (datetime.now() - timedelta(days=days)).isoformat()
            cursor.execute("""
                SELECT timestamp, action, symbol, name, price, quantity, total_amount, logic, total_assets
                FROM trades
                WHERE timestamp > ?
                ORDER BY timestamp DESC
            """, (since,))
            
            for row in cursor.fetchall():
                trades.append(TradeRecord(
                    timestamp=row[0],
                    action=row[1],
                    symbol=row[2],
                    name=row[3],
                    price=row[4],
                    quantity=row[5],
                    total_amount=row[6],
                    logic=row[7],
                    total_assets=row[8]
                ))
            
            conn.close()
            log.info(f"加载交易记录: {len(trades)} 笔")
            
        except Exception as e:
            log.fail(f"加载交易记录失败: {e}")
        
        return trades


class AttributionAnalyzer:
    """归因分析器"""
    
    def __init__(self, trades: List[TradeRecord]):
        self.trades = trades
    
    def analyze_win_rate_by_factor(self) -> Dict:
        """按因子分析胜率"""
        # 西风热点 vs 南风技术
        theme_wins = theme_total = 0
        tech_wins = tech_total = 0
        
        # 配对买卖记录
        positions = {}
        for trade in self.trades:
            if trade.action == 'BUY':
                positions[trade.symbol] = trade
            elif trade.action == 'SELL' and trade.symbol in positions:
                buy = positions[trade.symbol]
                sell = trade
                profit = (sell.price - buy.price) * buy.quantity
                
                # 分析买入理由
                logic = buy.logic.lower()
                is_theme = '板块' in logic or '热点' in logic or '西风' in logic
                is_tech = 'macd' in logic or 'rsi' in logic or '均线' in logic or '南风' in logic
                
                if is_theme:
                    theme_total += 1
                    if profit > 0:
                        theme_wins += 1
                
                if is_tech:
                    tech_total += 1
                    if profit > 0:
                        tech_wins += 1
                
                del positions[trade.symbol]
        
        return {
            'theme': {
                'total': theme_total,
                'wins': theme_wins,
                'win_rate': theme_wins / theme_total * 100 if theme_total > 0 else 0
            },
            'tech': {
                'total': tech_total,
                'wins': tech_wins,
                'win_rate': tech_wins / tech_total * 100 if tech_total > 0 else 0
            }
        }
    
    def analyze_stop_losses(self) -> List[Dict]:
        """分析止损记录"""
        stop_losses = []
        
        positions = {}
        for trade in self.trades:
            if trade.action == 'BUY':
                positions[trade.symbol] = trade
            elif trade.action == 'SELL' and trade.symbol in positions:
                buy = positions[trade.symbol]
                sell = trade
                
                # 检查是否是止损卖出
                if '止损' in sell.logic or sell.price < buy.price * 0.97:
                    stop_losses.append({
                        'symbol': sell.symbol,
                        'name': sell.name,
                        'buy_price': buy.price,
                        'sell_price': sell.price,
                        'loss_pct': (sell.price / buy.price - 1) * 100,
                        'reason': sell.logic,
                        'buy_logic': buy.logic
                    })
                
                del positions[trade.symbol]
        
        return stop_losses


class SentimentSensor:
    """市场情绪感知器"""
    
    def __init__(self):
        self.db_path = BEIFENG_DB
    
    def detect_sentiment(self) -> Dict:
        """
        检测当前市场情绪
        返回: {'sentiment': 'Bull'|'Flat'|'Bear', 'indicators': {...}}
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取大盘指数（以上证指数为例）
            cursor.execute("""
                SELECT timestamp, close, volume
                FROM kline_data
                WHERE stock_code = 'sh000001' AND data_type = 'daily'
                ORDER BY timestamp DESC
                LIMIT 30
            """)
            
            rows = cursor.fetchall()
            if len(rows) < 20:
                return {'sentiment': 'Unknown', 'indicators': {}}
            
            closes = [row[1] for row in reversed(rows)]
            
            # 计算MA20
            ma20 = sum(closes[-20:]) / 20
            current_price = closes[-1]
            
            # 计算上涨家数（简化：统计最近一日涨跌）
            cursor.execute("""
                SELECT COUNT(*) FROM (
                    SELECT stock_code, 
                           (SELECT close FROM kline_data k2 
                            WHERE k2.stock_code = k1.stock_code AND k2.data_type = 'daily'
                            ORDER BY timestamp DESC LIMIT 1) as close,
                           (SELECT close FROM kline_data k3 
                            WHERE k3.stock_code = k1.stock_code AND k3.data_type = 'daily'
                            ORDER BY timestamp DESC LIMIT 1 OFFSET 1) as prev_close
                    FROM (SELECT DISTINCT stock_code FROM kline_data WHERE data_type = 'daily') k1
                )
                WHERE close > prev_close
            """)
            
            up_count = cursor.fetchone()[0] if cursor.fetchone() else 0
            
            conn.close()
            
            # 判断情绪
            indicators = {
                'ma20': ma20,
                'current_price': current_price,
                'ma20_trend': 'up' if current_price > ma20 else 'down',
                'up_count': up_count
            }
            
            if current_price > ma20 and up_count > 3000:
                sentiment = 'Bull'
            elif current_price < ma20 * 0.95:
                sentiment = 'Bear'
            else:
                sentiment = 'Flat'
            
            return {
                'sentiment': sentiment,
                'indicators': indicators
            }
            
        except Exception as e:
            log.fail(f"情绪检测失败: {e}")
            return {'sentiment': 'Unknown', 'indicators': {}}
    
    def get_strategy_advice(self, sentiment: str) -> Dict:
        """根据情绪给出策略建议"""
        advice = {
            'Bull': {
                'description': '进攻型',
                'nanfeng': {'theme_weight': 0.6, 'tech_weight': 0.4, 'rsi_limit': 80},
                'dongfeng': {'amplitude_threshold': 3.0},
                'facai': {'position_limit': 0.5, 'take_profit': 0.15}
            },
            'Flat': {
                'description': '波段型',
                'nanfeng': {'theme_weight': 0.5, 'tech_weight': 0.5, 'boll_weight': 1.5},
                'dongfeng': {'amplitude_threshold': 3.0, 'strict_timing': True},
                'facai': {'position_limit': 0.3, 'take_profit': 0.05}
            },
            'Bear': {
                'description': '防守型',
                'nanfeng': {'theme_weight': 0.3, 'tech_weight': 0.7, 'score_penalty': -2},
                'dongfeng': {'amplitude_threshold': 4.0, 'hot_only': True},
                'facai': {'position_limit': 0.2, 'stop_loss': 0.03}
            }
        }
        
        return advice.get(sentiment, advice['Flat'])


class Optimizer:
    """参数优化器"""
    
    def __init__(self, trades: List[TradeRecord]):
        self.trades = trades
    
    def optimize_trailing_stop(self) -> Dict:
        """优化动态止盈步长"""
        # 分析最近10笔盈利订单
        profits = []
        positions = {}
        
        for trade in self.trades:
            if trade.action == 'BUY':
                positions[trade.symbol] = trade
            elif trade.action == 'SELL' and trade.symbol in positions:
                buy = positions[trade.symbol]
                sell = trade
                profit = (sell.price - buy.price) / buy.price
                
                if profit > 0:
                    profits.append({
                        'symbol': sell.symbol,
                        'profit_pct': profit * 100,
                        'continued_rising': False  # 简化：实际需要后续数据
                    })
                
                del positions[trade.symbol]
        
        # 取最近10笔
        recent = profits[-10:]
        if len(recent) < 5:
            return {'current_step': 1.0, 'recommended_step': 1.0, 'confidence': 0}
        
        # 如果8/10笔卖出后继续涨，建议提高止盈步长
        continued_rising_count = sum(1 for p in recent if p.get('continued_rising', False))
        
        if continued_rising_count >= 8:
            return {
                'current_step': 1.0,
                'recommended_step': 2.5,
                'confidence': continued_rising_count / 10,
                'reason': f'最近10笔盈利中{continued_rising_count}笔卖出后继续上涨'
            }
        
        return {'current_step': 1.0, 'recommended_step': 1.0, 'confidence': 0}
    
    def optimize_scoring_weights(self) -> Dict:
        """优化打分权重"""
        # 需要三周的数据
        # 简化：返回当前权重和建议
        return {
            'current': {'theme': 0.4, 'tech': 0.6},
            'recommended': {'theme': 0.5, 'tech': 0.5},
            'reason': '需要更多历史数据进行统计分析'
        }


class BaibanSystem:
    """白板系统核心"""
    
    def __init__(self):
        self.trade_loader = TradeLoader()
        self.sentiment_sensor = SentimentSensor()
        self.current_sentiment = None
    
    def run_daily_backtest(self):
        """每日收盘后回测"""
        log.info("=" * 60)
        log.info("🀆 白板执行每日回测...")
        log.info("=" * 60)
        
        # 1. 加载交易记录
        trades = self.trade_loader.load_facai_trades(days=7)
        
        if len(trades) < 2:
            log.warning("交易记录不足，跳过回测")
            return
        
        # 2. 归因分析
        analyzer = AttributionAnalyzer(trades)
        win_rate_by_factor = analyzer.analyze_win_rate_by_factor()
        stop_losses = analyzer.analyze_stop_losses()
        
        log.info("归因分析结果:")
        log.info(f"  西风题材胜率: {win_rate_by_factor.get('theme', {}).get('win_rate', 0):.1f}%")
        log.info(f"  南风技术胜率: {win_rate_by_factor.get('tech', {}).get('win_rate', 0):.1f}%")
        log.info(f"  止损次数: {len(stop_losses)}")
        
        # 3. 情绪检测
        sentiment_result = self.sentiment_sensor.detect_sentiment()
        self.current_sentiment = sentiment_result['sentiment']
        
        log.info(f"市场情绪: {self.current_sentiment}")
        log.info(f"  指标: {sentiment_result['indicators']}")
        
        # 4. 保存结果
        result = {
            'date': datetime.now().isoformat(),
            'type': 'daily',
            'trades_count': len(trades),
            'win_rate_by_factor': win_rate_by_factor,
            'stop_losses_count': len(stop_losses),
            'sentiment': sentiment_result
        }
        
        self._save_backtest_result(result)
        
        log.info("=" * 60)
        log.info("🀆 每日回测完成")
        log.info("=" * 60)
    
    def run_weekly_evolution(self):
        """周末全量回测与进化"""
        log.info("=" * 60)
        log.info("🀆 白板执行周末全量回测与进化...")
        log.info("=" * 60)
        
        # 1. 加载30天交易记录
        trades = self.trade_loader.load_facai_trades(days=30)
        
        # 2. 计算回测指标
        result = self._calculate_backtest_metrics(trades)
        
        log.info(f"回测结果:")
        log.info(f"  总交易: {result.total_trades}")
        log.info(f"  胜率: {result.win_rate:.1f}%")
        log.info(f"  平均盈利: {result.avg_profit:.2f}%")
        log.info(f"  最大回撤: {result.max_drawdown:.2f}%")
        log.info(f"  总收益: {result.total_return:.2f}%")
        
        # 3. 参数优化
        optimizer = Optimizer(trades)
        trailing_stop_opt = optimizer.optimize_trailing_stop()
        weight_opt = optimizer.optimize_scoring_weights()
        
        # 4. 生成进化指令
        sentiment = self.sentiment_sensor.detect_sentiment()
        advice = self.sentiment_sensor.get_strategy_advice(sentiment['sentiment'])
        
        command = EvolutionCommand(
            timestamp=datetime.now().isoformat(),
            market_sentiment=sentiment['sentiment'],
            nanfeng_adjustments=advice.get('nanfeng', {}),
            dongfeng_adjustments=advice.get('dongfeng', {}),
            facai_adjustments=advice.get('facai', {}),
            reason=f"本周胜率{result.win_rate:.1f}%，情绪{sentiment['sentiment']}"
        )
        
        # 5. 保存并生成报告
        self._save_evolution_command(command)
        self._generate_weekly_report(result, command, trailing_stop_opt)
        
        log.info("=" * 60)
        log.info("🀆 周末进化完成")
        log.info("=" * 60)
    
    def _calculate_backtest_metrics(self, trades: List[TradeRecord]) -> BacktestResult:
        """计算回测指标"""
        # 简化计算
        total_trades = len([t for t in trades if t.action == 'SELL'])
        
        # 计算胜率
        wins = 0
        profits = []
        positions = {}
        
        for trade in trades:
            if trade.action == 'BUY':
                positions[trade.symbol] = trade
            elif trade.action == 'SELL' and trade.symbol in positions:
                buy = positions[trade.symbol]
                profit_pct = (trade.price - buy.price) / buy.price * 100
                profits.append(profit_pct)
                if profit_pct > 0:
                    wins += 1
                del positions[trade.symbol]
        
        win_rate = wins / total_trades * 100 if total_trades > 0 else 0
        avg_profit = statistics.mean(profits) if profits else 0
        max_drawdown = min(profits) if profits else 0
        
        # 总收益（简化：用最后总资产/初始资金）
        if trades:
            final_assets = trades[0].total_assets  # 最新的在前面
            total_return = (final_assets / 100000 - 1) * 100
        else:
            total_return = 0
        
        return BacktestResult(
            period='30d',
            total_trades=total_trades,
            win_rate=win_rate,
            avg_profit=avg_profit,
            max_drawdown=max_drawdown,
            total_return=total_return,
            sharpe_ratio=0  # 简化
        )
    
    def _save_backtest_result(self, result: Dict):
        """保存回测结果"""
        results = []
        if BACKTEST_RESULTS.exists():
            try:
                with open(BACKTEST_RESULTS, 'r', encoding='utf-8') as f:
                    results = json.load(f)
            except:
                pass
        
        results.insert(0, result)
        results = results[:100]
        
        with open(BACKTEST_RESULTS, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        
        log.info(f"回测结果已保存: {BACKTEST_RESULTS}")
    
    def _save_evolution_command(self, command: EvolutionCommand):
        """保存进化指令"""
        logs = []
        if EVOLUTION_LOG.exists():
            try:
                with open(EVOLUTION_LOG, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                pass
        
        logs.insert(0, asdict(command))
        logs = logs[:50]
        
        with open(EVOLUTION_LOG, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        log.info(f"进化指令已保存: {EVOLUTION_LOG}")
    
    def _generate_weekly_report(self, result: BacktestResult, command: EvolutionCommand, 
                                trailing_opt: Dict):
        """生成周报"""
        report_path = REPORT_DIR / f"weekly_report_{datetime.now().strftime('%Y%m%d')}.md"
        
        report = f"""# 白板·策略进化周报

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**回测周期**: 最近30天

## 回测表现

| 指标 | 数值 |
|------|------|
| 总交易次数 | {result.total_trades} |
| 胜率 | {result.win_rate:.1f}% |
| 平均盈利 | {result.avg_profit:.2f}% |
| 最大回撤 | {result.max_drawdown:.2f}% |
| 总收益率 | {result.total_return:+.2f}% |

## 市场情绪诊断

**当前情绪**: {command.market_sentiment}

**策略建议**: {self.sentiment_sensor.get_strategy_advice(command.market_sentiment).get('description', 'Unknown')}

## 进化指令

### 南风 (Quant)
{json.dumps(command.nanfeng_adjustments, ensure_ascii=False, indent=2)}

### 东风 (Screener)
{json.dumps(command.dongfeng_adjustments, ensure_ascii=False, indent=2)}

### 发财 (Trader)
{json.dumps(command.facai_adjustments, ensure_ascii=False, indent=2)}

## 参数优化建议

### 动态止盈步长
- 当前: {trailing_opt.get('current_step', 1.0)}%
- 建议: {trailing_opt.get('recommended_step', 1.0)}%
- 置信度: {trailing_opt.get('confidence', 0) * 100:.0f}%
- 理由: {trailing_opt.get('reason', 'N/A')}

## 执行说明

请将上述进化指令手动同步到各Agent的配置文件中：
- 南风: `~/Documents/OpenClawAgents/nanfeng/config.yaml`
- 东风: `~/Documents/OpenClawAgents/dongfeng/config.yaml`
- 发财: `~/Documents/OpenClawAgents/facai/config.yaml`

**下次全量回测时间**: 下周日 20:00

---
*报告生成: 白板🀆*
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        log.info(f"周报已生成: {report_path}")


def main():
    parser = argparse.ArgumentParser(description='白板 - 策略进化与回测系统')
    parser.add_argument('--daily', action='store_true', help='每日收盘后回测')
    parser.add_argument('--weekly', action='store_true', help='周末全量回测')
    parser.add_argument('--sentiment', action='store_true', help='情绪诊断')
    parser.add_argument('--report', action='store_true', help='查看最新报告')
    
    args = parser.parse_args()
    
    baiban = BaibanSystem()
    
    if args.daily:
        baiban.run_daily_backtest()
    elif args.weekly:
        baiban.run_weekly_evolution()
    elif args.sentiment:
        result = baiban.sentiment_sensor.detect_sentiment()
        print(f"\n🀆 市场情绪诊断\n")
        print(f"情绪: {result['sentiment']}")
        print(f"指标: {json.dumps(result['indicators'], ensure_ascii=False, indent=2)}")
        advice = baiban.sentiment_sensor.get_strategy_advice(result['sentiment'])
        print(f"\n策略建议: {advice.get('description', 'Unknown')}")
        print()
    elif args.report:
        reports = sorted(REPORT_DIR.glob("weekly_report_*.md"))
        if reports:
            print(f"\n🀆 最新周报:\n")
            with open(reports[-1], 'r', encoding='utf-8') as f:
                print(f.read())
        else:
            print("暂无周报")
    else:
        # 默认执行每日回测
        baiban.run_daily_backtest()


if __name__ == "__main__":
    main()


class SlippageAnalyzer:
    """滑点分析器"""
    
    def __init__(self, trades: List[TradeRecord]):
        self.trades = trades
    
    def calculate_slippage(self, trade: TradeRecord) -> float:
        """计算滑点百分比"""
        if not trade.entry_price or trade.entry_price == 0:
            return 0
        
        # 滑点 = (成交价 - 信号价) / 信号价 * 100%
        # 买入滑点应该是正的(买贵了), 卖出滑点是负的(卖便宜了)
        if trade.action == "BUY":
            # 实际买入价应该比信号价高(上浮0.2%)
            expected = trade.entry_price * 1.002
            slippage = (trade.price - expected) / expected * 100
        else:
            # 实际卖出价应该比信号价低(下浮0.2%)
            expected = trade.entry_price * 0.998
            slippage = (trade.price - expected) / expected * 100
        
        return slippage
    
    def analyze_by_score(self) -> Dict:
        """按评分分析滑点"""
        score_buckets = {
            "高评分(80+)": [],
            "中高评分(70-80)": [],
            "中等评分(60-70)": [],
            "低评分(<60)": []
        }
        
        for trade in self.trades:
            if not trade.score:
                continue
            
            slippage = self.calculate_slippage(trade)
            
            if trade.score >= 80:
                score_buckets["高评分(80+)"].append(slippage)
            elif trade.score >= 70:
                score_buckets["中高评分(70-80)"].append(slippage)
            elif trade.score >= 60:
                score_buckets["中等评分(60-70)"].append(slippage)
            else:
                score_buckets["低评分(<60)"].append(slippage)
        
        # 计算每个区间的平均滑点
        result = {}
        for bucket, slippages in score_buckets.items():
            if slippages:
                result[bucket] = {
                    "count": len(slippages),
                    "avg_slippage": sum(slippages) / len(slippages),
                    "max_slippage": max(slippages),
                    "min_slippage": min(slippages)
                }
            else:
                result[bucket] = {"count": 0, "avg_slippage": 0}
        
        return result
    
    def analyze_by_strategy(self) -> Dict:
        """按策略分析滑点"""
        strategy_buckets = {}
        
        for trade in self.trades:
            if not trade.strategy:
                continue
            
            slippage = self.calculate_slippage(trade)
            
            if trade.strategy not in strategy_buckets:
                strategy_buckets[trade.strategy] = []
            
            strategy_buckets[trade.strategy].append(slippage)
        
        result = {}
        for strategy, slippages in strategy_buckets.items():
            result[strategy] = {
                "count": len(slippages),
                "avg_slippage": sum(slippages) / len(slippages)
            }
        
        return result

