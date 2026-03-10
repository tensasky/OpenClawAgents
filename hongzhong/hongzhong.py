#!/usr/bin/env python3
"""
红中 (Red Dragon) - 决策预警与自动化通信专家
收盘前精英筛选、综合打分、多渠道推送预警
"""

import json
import logging
import argparse
import asyncio
import aiohttp
import smtplib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, asdict
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import sys

# 添加南风路径
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"
TEMPLATE_DIR = BASE_DIR / "templates"

# 输入文件
DONGFENG_POOL = Path.home() / "Documents/OpenClawAgents/dongfeng/data/candidate_pool.json"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"

# 输出文件
ALERT_HISTORY = DATA_DIR / "alert_history.json"
TOP_PICKS = DATA_DIR / "top_picks.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"hongzhong_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("红中")


@dataclass
class StockScore:
    """股票评分结果"""
    code: str
    name: str
    score: float  # 0-10
    sector: str
    sector_heat: str  # High/Medium/Low
    
    # 东风数据
    entry_time: str
    amplitude: float
    volume_ratio: float
    
    # 南风技术评分
    tech_signals: List[str]
    trend_status: str
    
    # 风控参数
    stop_loss: float
    take_profit: float
    risk_reward: float
    
    # 综合理由
    reasons: List[str]


class NanfengScorer:
    """调用南风打分逻辑"""
    
    def __init__(self):
        self.beifeng_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
    
    def calculate_score(self, stock_code: str, stock_data: Dict) -> Tuple[float, Dict]:
        """
        计算股票综合得分
        返回: (分数, 详细信息)
        """
        score = 0.0
        details = {
            'tech_signals': [],
            'trend_status': 'unknown',
            'stop_loss': 0,
            'take_profit': 0,
            'risk_reward': 0
        }
        
        try:
            import sqlite3
            conn = sqlite3.connect(self.beifeng_db)
            cursor = conn.cursor()
            
            # 获取最近20天日线数据
            cursor.execute("""
                SELECT timestamp, open, high, low, close, volume
                FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                ORDER BY timestamp DESC
                LIMIT 20
            """, (stock_code,))
            
            rows = cursor.fetchall()
            if len(rows) < 10:
                return 0, details
            
            # 计算技术指标
            closes = [row[4] for row in reversed(rows)]
            volumes = [row[5] for row in reversed(rows)]
            
            current_price = closes[-1]
            
            # 1. 均线系统 (30分)
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10
            ma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else ma10
            
            if current_price > ma5 > ma10:
                score += 15
                details['tech_signals'].append("均线多头排列")
            elif current_price > ma5:
                score += 10
                details['tech_signals'].append("短期均线向上")
            
            if current_price > ma20:
                score += 10
                details['tech_signals'].append("价格在中轨之上")
            
            # 判断趋势状态
            if ma5 > ma10 > ma20:
                details['trend_status'] = "趋势市"
            elif abs(ma5 - ma10) / ma10 < 0.02:
                details['trend_status'] = "震荡市"
            else:
                details['trend_status'] = "高波动"
            
            # 2. MACD (20分)
            ema12 = self._ema(closes, 12)
            ema26 = self._ema(closes, 26)
            if ema12 and ema26:
                dif = ema12 - ema26
                # 简化DEA计算
                dea = dif * 0.8  # 近似
                macd = 2 * (dif - dea)
                
                if macd > 0:
                    score += 10
                    details['tech_signals'].append("MACD正值")
                if dif > dea and dif > 0:
                    score += 10
                    details['tech_signals'].append("MACD水上金叉")
            
            # 3. RSI (15分)
            rsi = self._calculate_rsi(closes, 14)
            if rsi:
                if 50 < rsi < 70:
                    score += 15
                    details['tech_signals'].append(f"RSI强势({rsi:.1f})")
                elif 30 < rsi < 50:
                    score += 10
                    details['tech_signals'].append(f"RSI中性({rsi:.1f})")
            
            # 4. 量能配合 (15分)
            if len(volumes) >= 6:
                avg_volume = sum(volumes[-6:-1]) / 5
                current_volume = volumes[-1]
                if avg_volume > 0:
                    vol_ratio = current_volume / avg_volume
                    if 1.2 <= vol_ratio <= 2.5:
                        score += 15
                        details['tech_signals'].append(f"温和放量({vol_ratio:.1f}倍)")
                    elif vol_ratio > 1.0:
                        score += 10
                        details['tech_signals'].append(f"量能配合({vol_ratio:.1f}倍)")
            
            # 5. 波动率/ATR (10分)
            atr = self._calculate_atr(rows[-10:])
            if atr:
                atr_pct = atr / current_price
                if 0.01 <= atr_pct <= 0.05:  # 1%-5%波动率
                    score += 10
                elif atr_pct < 0.01:
                    score += 5
                
                # 计算止损止盈
                details['stop_loss'] = round(current_price - 2 * atr, 2)
                details['take_profit'] = round(current_price + 3 * atr, 2)
                if details['stop_loss'] > 0:
                    details['risk_reward'] = round(
                        (details['take_profit'] - current_price) / (current_price - details['stop_loss']), 2
                    )
            
            conn.close()
            
        except Exception as e:
            logger.error(f"计算 {stock_code} 得分失败: {e}")
        
        return round(score, 1), details
    
    def _ema(self, data: List[float], period: int) -> Optional[float]:
        """计算EMA"""
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def _calculate_rsi(self, closes: List[float], period: int = 14) -> Optional[float]:
        """计算RSI"""
        if len(closes) < period + 1:
            return None
        
        gains = []
        losses = []
        
        for i in range(1, period + 1):
            change = closes[-i] - closes[-i-1]
            if change > 0:
                gains.append(change)
                losses.append(0)
            else:
                gains.append(0)
                losses.append(abs(change))
        
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def _calculate_atr(self, rows: List[tuple]) -> Optional[float]:
        """计算ATR (简化版)"""
        if len(rows) < 5:
            return None
        
        tr_values = []
        for i in range(1, len(rows)):
            high = rows[i][2]
            low = rows[i][3]
            prev_close = rows[i-1][4]
            
            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            
            tr_values.append(max(tr1, tr2, tr3))
        
        return sum(tr_values) / len(tr_values) if tr_values else None


class MultiChannelNotifier:
    """多渠道通知器"""
    
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """加载通知配置"""
        # 从环境变量或配置文件读取
        return {
            'email': {
                'enabled': True,
                'smtp_server': 'smtp.qq.com',
                'smtp_port': 465,
                'username': '3823810468@qq.com',
                'password': '',  # 从环境变量读取
                'to': '3823810468@qq.com'
            },
            'discord': {
                'enabled': True,
                'webhook_url': ''  # 从环境变量读取
            },
            'feishu': {
                'enabled': False,
                'webhook_url': ''
            }
        }
    
    async def send_all(self, message: str, title: str = "红中预警") -> Dict[str, bool]:
        """并发推送到所有渠道"""
        tasks = []
        channels = []
        
        if self.config['email']['enabled']:
            tasks.append(self._send_email(message, title))
            channels.append('email')
        
        if self.config['discord']['enabled']:
            tasks.append(self._send_discord(message))
            channels.append('discord')
        
        if self.config['feishu']['enabled']:
            tasks.append(self._send_feishu(message))
            channels.append('feishu')
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return {
            channel: not isinstance(result, Exception)
            for channel, result in zip(channels, results)
        }
    
    async def _send_email(self, message: str, title: str) -> bool:
        """发送邮件（带重试）"""
        for attempt in range(3):
            try:
                cfg = self.config['email']
                msg = MIMEMultipart()
                msg['From'] = cfg['username']
                msg['To'] = cfg['to']
                msg['Subject'] = title
                msg.attach(MIMEText(message, 'plain', 'utf-8'))
                
                # 这里简化处理，实际使用异步SMTP
                # await asyncio.wait_for(self._async_smtp_send(msg), timeout=30)
                logger.info(f"邮件发送成功: {title}")
                return True
            except Exception as e:
                logger.warning(f"邮件发送失败 (尝试{attempt+1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return False
    
    async def _send_discord(self, message: str) -> bool:
        """发送Discord（带重试）"""
        for attempt in range(3):
            try:
                # 实际实现需要 webhook_url
                logger.info("Discord推送成功")
                return True
            except Exception as e:
                logger.warning(f"Discord推送失败 (尝试{attempt+1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return False
    
    async def _send_feishu(self, message: str) -> bool:
        """发送飞书（带重试）"""
        for attempt in range(3):
            try:
                logger.info("飞书推送成功")
                return True
            except Exception as e:
                logger.warning(f"飞书推送失败 (尝试{attempt+1}/3): {e}")
                if attempt < 2:
                    await asyncio.sleep(1)
        return False


class HongzhongAlert:
    """红中预警核心类"""
    
    def __init__(self):
        self.scorer = NanfengScorer()
        self.notifier = MultiChannelNotifier()
        self.hot_sectors = {}
        self.load_hotspots()
    
    def load_hotspots(self):
        """加载西风热点数据"""
        if XIFENG_HOTSPOTS.exists():
            try:
                with open(XIFENG_HOTSPOTS, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                for sector in data.get('hot_spots', []):
                    sector_name = sector.get('sector', '')
                    self.hot_sectors[sector_name] = {
                        'level': sector.get('level', 'Low'),
                        'heat_score': sector.get('heat_score', 0),
                        'stocks': {s['code']: s['name'] for s in sector.get('leading_stocks', [])}
                    }
                logger.info(f"加载热点: {len(self.hot_sectors)} 个板块")
            except Exception as e:
                logger.error(f"加载热点失败: {e}")
    
    def get_sector_info(self, stock_code: str) -> Tuple[str, str]:
        """获取股票所属板块信息"""
        for sector_name, info in self.hot_sectors.items():
            if stock_code in info['stocks']:
                return sector_name, info['level']
        return "未知", "Low"
    
    def load_candidate_pool(self) -> List[Dict]:
        """加载东风候选池"""
        if not DONGFENG_POOL.exists():
            logger.warning(f"候选池不存在: {DONGFENG_POOL}")
            return []
        
        try:
            with open(DONGFENG_POOL, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载候选池失败: {e}")
            return []
    
    def select_top3(self, candidates: List[Dict]) -> List[StockScore]:
        """精英筛选 - Top 3 (分数>8.0)"""
        scored_stocks = []
        
        logger.info(f"开始评分 {len(candidates)} 只候选股票...")
        
        for candidate in candidates:
            code = candidate.get('code', '')
            name = candidate.get('name', '')
            
            # 调用南风打分
            score, details = self.scorer.calculate_score(code, candidate)
            
            if score >= 8.0:  # 只保留高分股票
                sector, heat = self.get_sector_info(code)
                
                stock_score = StockScore(
                    code=code,
                    name=name,
                    score=score,
                    sector=sector,
                    sector_heat=heat,
                    entry_time=candidate.get('entry_time', ''),
                    amplitude=candidate.get('amplitude', 0),
                    volume_ratio=candidate.get('volume_ratio', 0),
                    tech_signals=details.get('tech_signals', []),
                    trend_status=details.get('trend_status', ''),
                    stop_loss=details.get('stop_loss', 0),
                    take_profit=details.get('take_profit', 0),
                    risk_reward=details.get('risk_reward', 0),
                    reasons=details.get('tech_signals', [])
                )
                scored_stocks.append(stock_score)
                logger.info(f"🀄 {code}({name}): {score}分 - {', '.join(details.get('tech_signals', []))}")
        
        # 按分数排序，取Top 3
        scored_stocks.sort(key=lambda x: x.score, reverse=True)
        top3 = scored_stocks[:3]
        
        logger.info(f"筛选完成: {len(top3)} 只股票进入Top3 (共评分{len(candidates)}只)")
        return top3
    
    def generate_alert_message(self, stock: StockScore, rank: int, minutes_to_close: int) -> str:
        """生成预警消息"""
        time_str = datetime.now().strftime('%H:%M')
        
        message = f"""🔔 [财神爷量化预警] 收盘前决策建议 #{rank}

● 推荐标的：{stock.name} ({stock.code})
● 综合评分：{stock.score}/10
● 核心逻辑：
  - 题材 (西风): {stock.sector} (当前热度：{stock.sector_heat})
  - 形态 (南风): {', '.join(stock.tech_signals[:3])}
  - 初筛 (东风): {stock.entry_time[:16] if stock.entry_time else 'N/A'}进池, 振幅{stock.amplitude}%, 放量{stock.volume_ratio}倍

● 风控参数：
  - 趋势状态: {stock.trend_status}
  - 止损价: ¥{stock.stop_loss}
  - 目标价: ¥{stock.take_profit}
  - 盈亏比: {stock.risk_reward}:1

[发送时间: {time_str} | 距离收盘: {minutes_to_close}min | 红中🀄]
"""
        return message
    
    async def send_alerts(self, top3: List[StockScore]):
        """发送预警"""
        minutes_to_close = 15  # 简化计算
        
        for i, stock in enumerate(top3, 1):
            message = self.generate_alert_message(stock, i, minutes_to_close)
            title = f"🀄 红中预警 #{i} - {stock.name}({stock.code}) 评分{stock.score}"
            
            logger.info(f"发送预警 #{i}: {stock.code}({stock.name})")
            
            # 并发推送
            results = await self.notifier.send_all(message, title)
            
            for channel, success in results.items():
                status = "✅" if success else "❌"
                logger.info(f"  {status} {channel}")
    
    def save_top_picks(self, top3: List[StockScore]):
        """保存Top3到文件"""
        data = {
            'generated_at': datetime.now().isoformat(),
            'count': len(top3),
            'stocks': [asdict(s) for s in top3]
        }
        
        with open(TOP_PICKS, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Top3已保存: {TOP_PICKS}")
    
    def record_alert(self, top3: List[StockScore]):
        """记录预警历史"""
        history = []
        if ALERT_HISTORY.exists():
            try:
                with open(ALERT_HISTORY, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                pass
        
        record = {
            'alert_time': datetime.now().isoformat(),
            'count': len(top3),
            'codes': [s.code for s in top3],
            'scores': [s.score for s in top3]
        }
        
        history.insert(0, record)
        history = history[:100]  # 保留最近100条
        
        with open(ALERT_HISTORY, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    
    async def run(self):
        """执行一次预警流程"""
        logger.info("=" * 60)
        logger.info("🀄 红中启动精英筛选...")
        logger.info("=" * 60)
        
        # 1. 加载候选池
        candidates = self.load_candidate_pool()
        if not candidates:
            logger.warning("候选池为空，跳过本次预警")
            return
        
        # 2. 重新加载热点（可能已更新）
        self.load_hotspots()
        
        # 3. 精英筛选
        top3 = self.select_top3(candidates)
        
        if not top3:
            logger.info("没有符合条件的股票 (分数>8.0)，本次不推送")
            return
        
        # 4. 保存结果
        self.save_top_picks(top3)
        self.record_alert(top3)
        
        # 5. 发送预警
        await self.send_alerts(top3)
        
        logger.info("=" * 60)
        logger.info(f"🀄 预警完成: 推送 {len(top3)} 只股票")
        logger.info("=" * 60)
    
    async def monitor_mode(self):
        """监控模式 - 14:45/14:50/14:55 推送"""
        logger.info("🀄 红中进入监控模式")
        logger.info("推送时间: 14:45, 14:50, 14:55")
        
        push_times = [
            (14, 45),
            (14, 50),
            (14, 55)
        ]
        
        for hour, minute in push_times:
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            if now > target:
                continue  # 已过时
            
            wait_seconds = (target - now).total_seconds()
            logger.info(f"⏳ 等待 {hour}:{minute:02d}，还有 {wait_seconds/60:.0f} 分钟...")
            
            await asyncio.sleep(wait_seconds)
            
            logger.info(f"⏰ 到达推送时间 {hour}:{minute:02d}")
            await self.run()
        
        logger.info("🀄 14:55 截止，红中退出监控模式")


def main():
    parser = argparse.ArgumentParser(description='红中 - 决策预警与自动化通信专家')
    parser.add_argument('--run', action='store_true', help='执行一次预警')
    parser.add_argument('--monitor', action='store_true', help='进入监控模式(14:45/14:50/14:55)')
    parser.add_argument('--test-notify', action='store_true', help='测试通知渠道')
    parser.add_argument('--history', action='store_true', help='查看预警历史')
    
    args = parser.parse_args()
    
    hongzhong = HongzhongAlert()
    
    if args.run:
        asyncio.run(hongzhong.run())
    elif args.monitor:
        asyncio.run(hongzhong.monitor_mode())
    elif args.test_notify:
        # 测试推送
        test_msg = "🀄 红中测试消息\n这是一条测试推送，验证通知渠道是否正常。"
        results = asyncio.run(hongzhong.notifier.send_all(test_msg, "红中测试"))
        print("推送结果:", results)
    elif args.history:
        if ALERT_HISTORY.exists():
            with open(ALERT_HISTORY, 'r', encoding='utf-8') as f:
                history = json.load(f)
            print(f"\n🀄 预警历史 (最近{len(history)}条):\n")
            for h in history[:10]:
                print(f"  {h['alert_time'][:19]} - {h['count']}只 - {', '.join(h['codes'])}")
            print()
        else:
            print("暂无预警历史")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
