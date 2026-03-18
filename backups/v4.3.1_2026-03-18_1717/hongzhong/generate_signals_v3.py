#!/usr/bin/env python3
"""
红中信号生成器 V3.4 - 完整版策略报告
包含: 策略版本、操盘建议、盈利预期、持股天数
"""

import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("红中V3")

# 数据库路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HONGZHONG_DB = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

# 邮件配置
EMAIL_CONFIG = {
    "sender": "3823810468@qq.com",
    "password": "tmwhuqnthrpbcgec",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587,
    "receivers": ["3823810468@qq.com", "tensasky@gmail.com", "tensasky2003@gmail.com"]
}

# 南风策略配置
STRATEGY_CONFIG = {
    "version": "南风V5.1-保守版",
    "description": "高胜率稳健策略，追求确定性",
    "win_rate_target": "85%+",
    "monthly_return_target": "5%+",
    "avg_trades_per_month": 15,
    "holding_days": {
        "min": 3,
        "max": 15,
        "avg": 7
    },
    "scoring_weights": {
        "趋势": 40,
        "动量": 30,
        "成交量": 20,
        "价格位置": 10
    }
}

class NanfengStrategyV51:
    """南风策略V5.1 - 保守版"""
    
    def __init__(self):
        self.today = datetime.now().strftime('%Y-%m-%d')
        self.config = STRATEGY_CONFIG
    
    def get_strategy_info(self) -> dict:
        """获取策略信息"""
        return self.config
    
    def get_stock_data(self, stock_code: str) -> dict:
        """获取股票数据"""
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        # 获取最近有数据的交易日
        cursor.execute("""
            SELECT DISTINCT date(timestamp) as trade_date 
            FROM daily 
            WHERE stock_code = ?
            ORDER BY trade_date DESC 
            LIMIT 1
        """, (stock_code,))
        result = cursor.fetchone()
        if not result:
            conn.close()
            return None
        latest_date = result[0]
        
        # 今日/最近交易日数据
        cursor.execute(f"""
            SELECT open, high, low, close, volume, amount,
                   (close - open) / open * 100 as change_pct
            FROM daily
            WHERE stock_code = ? AND date(timestamp) = ?
        """, (stock_code, latest_date))
        
        today_data = cursor.fetchone()
        if not today_data:
            conn.close()
            return None
        
        open_p, high, low, close, vol, amount, change = today_data
        
        # 获取股票名称
        cursor.execute("SELECT stock_name FROM stock_names WHERE stock_code = ?", (stock_code,))
        name_result = cursor.fetchone()
        stock_name = name_result[0] if name_result else stock_code
        
        # 近期数据（60日）
        cursor.execute("""
            SELECT close, volume, amount
            FROM daily
            WHERE stock_code = ?
            ORDER BY timestamp DESC
            LIMIT 60
        """, (stock_code,))
        
        recent = cursor.fetchall()
        conn.close()
        
        return {
            'code': stock_code,
            'name': stock_name,
            'open': open_p,
            'high': high,
            'low': low,
            'close': close,
            'volume': vol,
            'amount': amount,
            'change_pct': change,
            'recent_data': recent
        }
    
    def calculate_score_detailed(self, data: dict) -> dict:
        """详细评分，包含完整分析"""
        if not data:
            return None
        
        score = 0
        details = {}
        
        closes = [r[0] for r in data['recent_data']]
        volumes = [r[1] for r in data['recent_data']]
        
        # 1. 趋势评分 (40分)
        if len(closes) >= 20:
            ma5 = sum(closes[:5]) / 5
            ma10 = sum(closes[:10]) / 10
            ma20 = sum(closes[:20]) / 20
            
            # 趋势强度
            if data['close'] > ma5 > ma10 > ma20:
                trend_score = 40
                trend_comment = "多头排列，强势上涨"
                trend_level = "strong"
            elif data['close'] > ma20:
                trend_score = 30
                trend_comment = "站上20日线，趋势向上"
                trend_level = "moderate"
            elif data['close'] > ma20 * 0.95:
                trend_score = 20
                trend_comment = "20日线附近，震荡整理"
                trend_level = "neutral"
            else:
                trend_score = 10
                trend_comment = "跌破20日线，趋势走弱"
                trend_level = "weak"
        else:
            trend_score = 20
            trend_comment = "数据不足，默认评分"
            trend_level = "unknown"
        
        score += trend_score
        details['趋势'] = {
            'score': trend_score,
            'weight': 40,
            'comment': trend_comment,
            'level': trend_level,
            'ma5': ma5 if len(closes) >= 5 else data['close'],
            'ma20': ma20 if len(closes) >= 20 else data['close']
        }
        
        # 2. 动量评分 (30分)
        change = data['change_pct']
        if change >= 9.9:
            momentum_score = 30
            momentum_comment = "涨停，极强动量"
            momentum_level = "limit_up"
        elif change >= 7:
            momentum_score = 27
            momentum_comment = "大涨，强势动量"
            momentum_level = "strong"
        elif change >= 5:
            momentum_score = 24
            momentum_comment = "明显上涨，积极动量"
            momentum_level = "positive"
        elif change >= 2:
            momentum_score = 20
            momentum_comment = "温和上涨，正常动量"
            momentum_level = "moderate"
        elif change >= 0:
            momentum_score = 15
            momentum_comment = "微涨，动量一般"
            momentum_level = "weak"
        else:
            momentum_score = max(5, 15 + int(change))  # 负分但保底5分
            momentum_comment = "下跌，动量不足"
            momentum_level = "negative"
        
        score += momentum_score
        details['动量'] = {
            'score': momentum_score,
            'weight': 30,
            'comment': momentum_comment,
            'level': momentum_level,
            'change_pct': change
        }
        
        # 3. 成交量评分 (20分)
        if len(volumes) >= 20:
            avg_20_vol = sum(volumes[:20]) / 20
            vol_ratio = data['volume'] / avg_20_vol if avg_20_vol > 0 else 1
            
            if vol_ratio >= 5:
                vol_score = 20
                vol_comment = "巨量，资金大举介入"
                vol_level = "extreme"
            elif vol_ratio >= 3:
                vol_score = 18
                vol_comment = "明显放量，资金活跃"
                vol_level = "high"
            elif vol_ratio >= 2:
                vol_score = 15
                vol_comment = "温和放量，关注度高"
                vol_level = "moderate"
            elif vol_ratio >= 1:
                vol_score = 10
                vol_comment = "正常成交，关注度一般"
                vol_level = "normal"
            else:
                vol_score = 6
                vol_comment = "缩量，关注度低"
                vol_level = "low"
        else:
            vol_score = 10
            vol_comment = "数据不足"
            vol_level = "unknown"
            vol_ratio = 1
        
        score += vol_score
        details['成交量'] = {
            'score': vol_score,
            'weight': 20,
            'comment': vol_comment,
            'level': vol_level,
            'volume_ratio': round(vol_ratio, 2)
        }
        
        # 4. 价格位置评分 (10分)
        if data['high'] > data['low']:
            price_position = (data['close'] - data['low']) / (data['high'] - data['low'])
            if price_position >= 0.9:
                price_score = 10
                price_comment = "接近涨停价，极强"
                price_level = "high"
            elif price_position >= 0.7:
                price_score = 8
                price_comment = "高位收盘，强势"
                price_level = "moderate_high"
            elif price_position >= 0.5:
                price_score = 6
                price_comment = "中位收盘，正常"
                price_level = "middle"
            else:
                price_score = 4
                price_comment = "低位收盘，偏弱"
                price_level = "low"
        else:
            price_score = 5
            price_comment = "一字板"
            price_level = "limit"
            price_position = 1
        
        score += price_score
        details['价格位置'] = {
            'score': price_score,
            'weight': 10,
            'comment': price_comment,
            'level': price_level,
            'position': round(price_position * 100, 1)
        }
        
        # 信号判断和操盘建议
        if score >= 80:
            signal = "强烈买入"
            signal_emoji = "🚀"
            signal_level = 5
        elif score >= 70:
            signal = "买入"
            signal_emoji = "📈"
            signal_level = 4
        elif score >= 65:
            signal = "积极关注"
            signal_emoji = "👀"
            signal_level = 3
        elif score >= 55:
            signal = "观望"
            signal_emoji = "⏸️"
            signal_level = 2
        else:
            signal = "回避"
            signal_emoji = "❌"
            signal_level = 1
        
        # 操盘建议
        trading_plan = self._generate_trading_plan(
            signal_level, data, details, score
        )
        
        return {
            'code': data['code'],
            'name': data['name'],
            'price': data['close'],
            'change': data['change_pct'],
            'score': score,
            'signal': signal,
            'signal_emoji': signal_emoji,
            'signal_level': signal_level,
            'details': details,
            'trading_plan': trading_plan,
            'strategy_version': self.config['version']
        }
    
    def _generate_trading_plan(self, level: int, data: dict, details: dict, score: int) -> dict:
        """生成操盘计划"""
        price = data['close']
        
        if level >= 4:  # 买入信号
            # 买入策略
            entry_price = price
            stop_loss = price * 0.95  # 止损 -5%
            target_1 = price * 1.08   # 目标1 +8%
            target_2 = price * 1.15   # 目标2 +15%
            
            # 根据评分调整
            if score >= 85:
                position_size = "20%"  # 重仓
                holding_days = "5-10天"
                expected_return = "10-15%"
            elif score >= 75:
                position_size = "15%"  # 中仓
                holding_days = "3-7天"
                expected_return = "8-12%"
            else:
                position_size = "10%"  # 轻仓
                holding_days = "3-5天"
                expected_return = "5-8%"
            
            return {
                'action': '买入',
                'entry_price': entry_price,
                'stop_loss': stop_loss,
                'target_1': target_1,
                'target_2': target_2,
                'position_size': position_size,
                'holding_days': holding_days,
                'expected_return': expected_return,
                'exit_strategy': f'到达{target_1:.2f}减仓一半，到达{target_2:.2f}清仓或继续持有'
            }
        
        elif level == 3:  # 关注
            return {
                'action': '关注',
                'entry_price': price,
                'watch_price': price * 1.02,  # 突破此价位考虑买入
                'stop_loss': price * 0.93,
                'position_size': "5-10%",
                'holding_days': "观望",
                'expected_return': "待定",
                'exit_strategy': '等待明确突破信号'
            }
        
        else:  # 回避
            return {
                'action': '回避',
                'reason': '信号不足或趋势走弱',
                'watch_price': None,
                'position_size': "0%",
                'holding_days': "不参与",
                'expected_return': "N/A",
                'exit_strategy': '不参与此股'
            }

class HongzhongSignalV3:
    """红中信号生成器V3.4"""
    
    def __init__(self):
        self.strategy = NanfengStrategyV51()
        self.signals = []
        self.latest_date = None
        self.realtime_data = {}  # 存储实时日线数据
    
    def get_realtime_daily_data(self, stock_code: str) -> dict:
        """
        获取实时日线数据（当日用minute聚合，历史用daily）
        ⚠️ 交易时段只用15分钟内的minute数据
        """
        import datetime
        now = datetime.datetime.now()
        hour = now.hour
        minute = now.minute
        time_val = hour * 100 + minute
        is_trading = (930 <= time_val < 1130) or (1300 <= time_val < 1500)
        
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        # 1. 尝试从minute获取当日聚合数据
        cursor.execute('''
            SELECT 
                MIN(timestamp) as open_time,
                MAX(high) as high,
                MIN(low) as low,
                MAX(close) as close,
                SUM(volume) as volume,
                MAX(timestamp) as latest_time
            FROM minute
            WHERE stock_code = ? AND timestamp LIKE ?
        ''', (stock_code, f"{self.strategy.today}%"))
        
        minute_data = cursor.fetchone()
        
        if minute_data and minute_data[3]:  # 有close价格
            # 检查数据是否在15分钟内
            latest_time = minute_data[5]
            if latest_time:
                latest_dt = datetime.datetime.strptime(latest_time, '%Y-%m-%d %H:%M:%S')
                time_diff = (now - latest_dt).total_seconds() / 60
                
                # 交易时段：数据必须15分钟内
                if is_trading and time_diff > 15:
                    conn.close()
                    return None  # 数据太旧，交易时段不使用
            
            conn.close()
            return {
                'source': 'minute',
                'source_time': latest_time,
                'is_fresh': time_diff <= 15 if minute_data[5] else False,
                'open': minute_data[3],
                'high': minute_data[1],
                'low': minute_data[2],
                'close': minute_data[3],
                'volume': minute_data[4] or 0,
                'change_pct': 0
            }
        
        # 2. 非交易时段：可以使用历史daily数据
        if not is_trading:
            cursor.execute('''
                SELECT open, high, low, close, volume, amount,
                       (close - open) / open * 100 as change_pct
                FROM daily
                WHERE stock_code = ?
                ORDER BY timestamp DESC
                LIMIT 1
            ''', (stock_code,))
            
            daily_data = cursor.fetchone()
            conn.close()
            
            if daily_data:
                return {
                    'source': 'daily',
                    'is_fresh': False,
                    'open': daily_data[0],
                    'high': daily_data[1],
                    'low': daily_data[2],
                    'close': daily_data[3],
                    'volume': daily_data[4],
                    'amount': daily_data[5],
                    'change_pct': daily_data[6]
                }
        
        conn.close()
        return None
    
    def get_realtime_stock_list(self, limit: int = 100) -> list:
        """
        获取可用于筛选的股票列表（优先当日有minute数据的）
        """
        conn = sqlite3.connect(BEIFENG_DB)
        cursor = conn.cursor()
        
        # 获取当日有minute数据的股票（优先）
        cursor.execute('''
            SELECT DISTINCT stock_code 
            FROM minute 
            WHERE timestamp LIKE ?
            ORDER BY volume DESC
            LIMIT ?
        ''', (f"{self.strategy.today}%", limit))
        
        minute_stocks = [row[0] for row in cursor.fetchall()]
        
        # 获取昨日有daily数据的股票
        cursor.execute('''
            SELECT stock_code 
            FROM daily 
            WHERE timestamp = "2026-03-17"
            ORDER BY (close - open) / open DESC
            LIMIT ?
        ''', (limit,))
        
        daily_stocks = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        
        # 优先使用有minute数据的股票
        return minute_stocks + [s for s in daily_stocks if s not in minute_stocks]
    
    def save_signals(self):
        """保存信号到数据库"""
        if not self.signals:
            return
        
        conn = sqlite3.connect(HONGZHONG_DB)
        cursor = conn.cursor()
        
        # 获取最近有数据的交易日
        conn2 = sqlite3.connect(BEIFENG_DB)
        cursor2 = conn2.cursor()
        cursor2.execute("""
            SELECT DISTINCT date(timestamp) as trade_date 
            FROM daily 
            ORDER BY trade_date DESC 
            LIMIT 1
        """)
        latest = cursor2.fetchone()[0]
        conn2.close()
        
        saved = 0
        for s in self.signals:
            try:
                cursor.execute("""
                    INSERT INTO signals 
                    (timestamp, stock_code, stock_name, strategy, version, 
                     entry_price, stop_loss, target_1, target_2, score, sent_discord)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    latest,
                    s['code'],
                    s['name'],
                    s.get('signal', '南风V5.1'),
                    s.get('strategy_version', 'V5.1'),
                    s.get('entry_price', 0),
                    s.get('stop_loss', 0),
                    s.get('target_1', 0),
                    s.get('target_2', 0),
                    s['score'],
                    0
                ))
                saved += 1
            except Exception as e:
                log.warning(f"保存失败 {s['code']}: {e}")
        
        conn.commit()
        conn.close()
        log.success(f"✅ 已保存 {saved} 个信号到数据库")
        return saved
    
    def scan_all_stocks(self, limit: int = 100):
        """扫描股票 - 使用实时数据（minute+当日聚合）"""
        log.step("开始扫描股票，生成交易信号")
        
        # 获取股票列表（优先当日有minute数据的）
        stocks = self.get_realtime_stock_list(limit)
        
        # 统计数据类型
        minute_count = 0
        daily_count = 0
        
        for stock in stocks:
            # 获取实时数据
            realtime = self.get_realtime_daily_data(stock)
            if not realtime:
                continue
            
            # 记录数据来源
            if realtime['source'] == 'minute':
                minute_count += 1
            else:
                daily_count += 1
            
            # 获取历史数据用于计算评分
            data = self.strategy.get_stock_data(stock)
            if data:
                # 用实时数据更新当日数据
                data['open'] = realtime['open']
                data['high'] = realtime['high']
                data['low'] = realtime['low']
                data['close'] = realtime['close']
                data['volume'] = realtime['volume']
                data['change_pct'] = realtime['change_pct']
                
                result = self.strategy.calculate_score_detailed(data)
                if result and result['score'] >= 65:
                    result['data_source'] = realtime['source']
                    self.signals.append(result)
        
        log.info(f"扫描 {len(stocks)} 只股票 (实时:{minute_count}, 历史:{daily_count})")
        
        self.signals.sort(key=lambda x: x['score'], reverse=True)
        
        log.success(f"生成 {len(self.signals)} 个交易信号")
        return self.signals
    
    def generate_email_content(self) -> str:
        """生成完整邮件内容"""
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        strategy_info = self.strategy.get_strategy_info()
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; padding: 30px; text-align: center; }}
                .strategy-box {{ background: #f0f7ff; border-left: 4px solid #0066cc; padding: 15px; margin: 20px 0; }}
                .signal {{ border: 1px solid #ddd; margin: 15px 0; padding: 20px; border-radius: 8px; background: #fff; }}
                .strong-buy {{ border-left: 5px solid #ff4444; background: #fff5f5; }}
                .buy {{ border-left: 5px solid #ff8800; background: #fff9f0; }}
                .stock-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; }}
                .stock-name {{ font-size: 24px; font-weight: bold; color: #1a1a2e; }}
                .stock-code {{ font-size: 16px; color: #666; }}
                .score-box {{ text-align: center; padding: 10px 20px; background: #ff4444; color: white; border-radius: 5px; }}
                .score-number {{ font-size: 32px; font-weight: bold; }}
                .trading-plan {{ background: #f8f9fa; padding: 15px; margin-top: 15px; border-radius: 5px; }}
                .plan-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 10px; }}
                .plan-item {{ background: white; padding: 10px; border-radius: 3px; }}
                .plan-label {{ color: #666; font-size: 12px; }}
                .plan-value {{ color: #333; font-size: 16px; font-weight: bold; }}
                .price-up {{ color: #ff4444; }}
                .price-down {{ color: #00aa00; }}
                table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
                th {{ background: #f5f5f5; font-weight: 600; }}
                .section-title {{ color: #0066cc; font-size: 20px; margin: 30px 0 15px; border-bottom: 2px solid #0066cc; padding-bottom: 10px; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎯 红中交易信号报告 V3.4</h1>
                <p style="font-size: 18px; margin: 10px 0;">生成时间: {now}</p>
                <p style="font-size: 14px; opacity: 0.9;">数据来源: 北风实时采集 | 策略: {strategy_info['version']}</p>
            </div>
            
            <!-- 策略说明 -->
            <div class="strategy-box">
                <h3>📊 策略配置: {strategy_info['version']}</h3>
                <p><strong>策略理念:</strong> {strategy_info['description']}</p>
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-top: 15px;">
                    <div>
                        <div style="color: #666; font-size: 12px;">目标胜率</div>
                        <div style="font-size: 24px; font-weight: bold; color: #0066cc;">{strategy_info['win_rate_target']}</div>
                    </div>
                    <div>
                        <div style="color: #666; font-size: 12px;">月收益目标</div>
                        <div style="font-size: 24px; font-weight: bold; color: #00aa00;">{strategy_info['monthly_return_target']}</div>
                    </div>
                    <div>
                        <div style="color: #666; font-size: 12px;">月均交易</div>
                        <div style="font-size: 24px; font-weight: bold; color: #ff8800;">{strategy_info['avg_trades_per_month']}笔</div>
                    </div>
                    <div>
                        <div style="color: #666; font-size: 12px;">持股周期</div>
                        <div style="font-size: 24px; font-weight: bold; color: #666;">{strategy_info['holding_days']['min']}-{strategy_info['holding_days']['max']}天</div>
                    </div>
                </div>
                
                <p style="margin-top: 15px; color: #666;">
                    <strong>评分权重:</strong> 
                    趋势{strategy_info['scoring_weights']['趋势']}% | 
                    动量{strategy_info['scoring_weights']['动量']}% | 
                    成交量{strategy_info['scoring_weights']['成交量']}% | 
                    价格位置{strategy_info['scoring_weights']['价格位置']}%
                </p>
            </div>
            
            <div class="section-title">🚀 重点交易信号 (Top 10)</div>
        """
        
        for i, signal in enumerate(self.signals[:10], 1):
            signal_class = "strong-buy" if signal['score'] >= 80 else "buy"
            plan = signal['trading_plan']
            
            # 价格颜色
            price_class = "price-up" if signal['change'] >= 0 else "price-down"
            
            html += f"""
            <div class="signal {signal_class}">
                <div class="stock-header">
                    <div>
                        <div class="stock-name">{signal['code']} {signal['name']}</div>
                        <div class="stock-code">策略: {signal['strategy_version']} | 信号: {signal['signal']}</div>
                    </div>
                    <div class="score-box">
                        <div class="score-number">{signal['score']}</div>
                        <div style="font-size: 12px;">综合评分</div>
                    </div>
                </div>
                
                <div style="font-size: 20px; margin: 15px 0;">
                    当前价: <span class="{price_class}">¥{signal['price']:.2f}</span> 
                    <span style="font-size: 14px; color: #666;">({signal['change']:+.2f}%)</span>
                </div>
                
                <!-- 评分详情 -->
                <table>
                    <tr>
                        <th>评分维度</th>
                        <th>权重</th>
                        <th>得分</th>
                        <th>评价</th>
                    </tr>
            """
            
            for dim, info in signal['details'].items():
                html += f"""
                    <tr>
                        <td>{dim}</td>
                        <td>{info['weight']}%</td>
                        <td>{info['score']}/{info['weight']}</td>
                        <td>{info['comment']}</td>
                    </tr>
                """
            
            html += "</table>"
            
            # 操盘计划
            if plan['action'] == '买入':
                html += f"""
                <div class="trading-plan">
                    <h4>📋 操盘计划 ({plan['action']})</h4>
                    
                    <div class="plan-grid">
                        <div class="plan-item">
                            <div class="plan-label">买入价位</div>
                            <div class="plan-value">¥{plan['entry_price']:.2f}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">止损价位 (-5%)</div>
                            <div class="plan-value" style="color: #ff4444;">¥{plan['stop_loss']:.2f}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">目标1 (+8%)</div>
                            <div class="plan-value" style="color: #00aa00;">¥{plan['target_1']:.2f}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">目标2 (+15%)</div>
                            <div class="plan-value" style="color: #00aa00;">¥{plan['target_2']:.2f}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">建议仓位</div>
                            <div class="plan-value">{plan['position_size']}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">持股周期</div>
                            <div class="plan-value">{plan['holding_days']}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">预期收益</div>
                            <div class="plan-value" style="color: #00aa00;">{plan['expected_return']}</div>
                        </div>
                        
                        <div class="plan-item">
                            <div class="plan-label">操作建议</div>
                            <div class="plan-value">买入持有</div>
                        </div>
                    </div>
                    
                    <p style="margin-top: 15px; padding: 10px; background: #e8f4ff; border-radius: 3px;">
                        <strong>📍 退出策略:</strong> {plan['exit_strategy']}
                    </p>
                </div>
                """
            else:
                html += f"""
                <div class="trading-plan" style="background: #f5f5f5;">
                    <h4>📋 操盘计划 ({plan['action']})</h4>
                    <p>{plan.get('reason', '信号不足')}</p>
                </div>
                """
            
            html += "</div>"
        
        html += """
            <hr style="margin: 40px 0;">
            
            <div style="background: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                <h4>⚠️ 风险提示</h4>
                <ul>
                    <li>以上信号基于技术分析生成，不构成投资建议</li>
                    <li>股市有风险，投资需谨慎，请根据自身情况决策</li>
                    <li>严格设置止损，单只股票亏损不超过5%</li>
                    <li>分散投资，单只股票仓位不超过20%</li>
                    <li>历史胜率不代表未来收益，请理性投资</li>
                </ul>
            </div>
            
            <p style="text-align: center; color: #666; margin-top: 40px; padding: 20px;">
                <strong>OpenClawAgents 智能量化交易系统</strong><br>
                红中交易信号系统 V3.4 | 南风策略V5.1-保守版<br>
                <span style="font-size: 12px;">本报告由AI自动生成，仅供参考</span>
            </p>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self):
        """发送邮件"""
        try:
            log.step("正在发送完整版邮件报告...")
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f"🎯 红中交易信号V3.4 - {datetime.now().strftime('%Y-%m-%d')} (含完整操盘计划)"
            msg['From'] = EMAIL_CONFIG['sender']
            
            receivers = EMAIL_CONFIG['receivers']
            msg['To'] = ', '.join(receivers)
            
            html_content = self.generate_email_content()
            msg.attach(MIMEText(html_content, 'html', 'utf-8'))
            
            server = smtplib.SMTP(EMAIL_CONFIG['smtp_server'], EMAIL_CONFIG['smtp_port'])
            server.starttls()
            server.login(EMAIL_CONFIG['sender'], EMAIL_CONFIG['password'])
            server.sendmail(EMAIL_CONFIG['sender'], receivers, msg.as_string())
            server.quit()
            
            log.success(f"✅ 完整版邮件已发送至 {len(receivers)} 个邮箱")
            return True
            
        except Exception as e:
            log.error(f"❌ 邮件发送失败: {e}")
            return False

def main():
    """主程序"""
    print("="*70)
    print("🎯 红中信号生成器 V3.4 - 完整版策略报告")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"策略: {STRATEGY_CONFIG['version']}")
    print(f"目标: 胜率{STRATEGY_CONFIG['win_rate_target']}, 月收益{STRATEGY_CONFIG['monthly_return_target']}")
    print()
    
    hongzhong = HongzhongSignalV3()
    
    # 扫描股票
    signals = hongzhong.scan_all_stocks(limit=100)
    
    if not signals:
        print("❌ 未生成有效信号")
        return
    
    # 保存信号到数据库
    hongzhong.save_signals()
    
    # 显示信号
    print(f"\n📊 生成 {len(signals)} 个交易信号:\n")
    for i, s in enumerate(signals[:5], 1):
        plan = s['trading_plan']
        print(f"{i}. {s['signal_emoji']} {s['code']} {s['name']}")
        print(f"   评分: {s['score']} | 信号: {s['signal']}")
        print(f"   操盘: {plan['action']} | 仓位: {plan.get('position_size', 'N/A')} | 持股: {plan.get('holding_days', 'N/A')}")
        print(f"   预期收益: {plan.get('expected_return', 'N/A')}\n")
    
    # 发送邮件
    print("="*70)
    success = hongzhong.send_email()
    
    if success:
        print("\n✅ 完整版报告已发送！")
        print("📧 包含内容:")
        print("   • 策略版本和配置")
        print("   • 详细评分维度")
        print("   • 完整操盘计划")
        print("   • 买入/止损/目标价位")
        print("   • 建议仓位和持股天数")
        print("   • 预期收益率")
    
    print("="*70)

if __name__ == '__main__':
    main()
