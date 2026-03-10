#!/usr/bin/env python3
"""
红中 (Red Dragon) - 决策预警与自动化通信专家
14:45 运行，获取南风Top3，多渠道推送
"""

import json
import logging
import argparse
import asyncio
import aiohttp
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys

# 添加南风路径
sys.path.insert(0, str(Path.home() / "Documents/OpenClawAgents/nanfeng"))

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# 输出文件
TOP3_FILE = DATA_DIR / "top3.json"
ALERT_LOG = DATA_DIR / "alert_log.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

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


class NanfengAPI:
    """调用南风打分逻辑"""
    
    def __init__(self):
        self.db_path = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
    
    def get_top3(self) -> List[Dict]:
        """
        获取南风打分最高的前3名
        返回: [{code, name, score, signals, stop_loss, take_profit}, ...]
        """
        import sqlite3
        
        top_stocks = []
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取所有股票代码
            cursor.execute("SELECT code, name FROM stocks LIMIT 100")  # 先测试100只
            stocks = cursor.fetchall()
            
            scored = []
            for code, name in stocks:
                score, details = self._calculate_score(cursor, code)
                if score >= 7.0:  # 只保留7分以上的
                    scored.append({
                        'code': code,
                        'name': name,
                        'score': score,
                        'signals': details.get('signals', []),
                        'stop_loss': details.get('stop_loss', 0),
                        'take_profit': details.get('take_profit', 0),
                        'price': details.get('price', 0)
                    })
            
            conn.close()
            
            # 按分数排序，取前3
            scored.sort(key=lambda x: x['score'], reverse=True)
            top3 = scored[:3]
            
            logger.info(f"南风评分完成: 从{len(stocks)}只中筛选出{len(scored)}只>=7分，取Top{len(top3)}")
            for s in top3:
                logger.info(f"  🀄 {s['code']}({s['name']}): {s['score']}分")
            
            return top3
            
        except Exception as e:
            logger.error(f"获取Top3失败: {e}")
            return []
    
    def _calculate_score(self, cursor, code: str) -> tuple:
        """计算单只股票得分"""
        score = 0.0
        details = {'signals': [], 'stop_loss': 0, 'take_profit': 0, 'price': 0}
        
        try:
            # 获取最近10天数据
            cursor.execute("""
                SELECT timestamp, open, high, low, close, volume
                FROM kline_data
                WHERE stock_code = ? AND data_type = 'daily'
                ORDER BY timestamp DESC
                LIMIT 10
            """, (code,))
            
            rows = cursor.fetchall()
            if len(rows) < 5:
                return 0, details
            
            closes = [row[4] for row in reversed(rows)]
            current_price = closes[-1]
            details['price'] = current_price
            
            # 1. 均线 (30分)
            ma5 = sum(closes[-5:]) / 5
            ma10 = sum(closes[-10:]) / 10 if len(closes) >= 10 else ma5
            
            if current_price > ma5 > ma10:
                score += 20
                details['signals'].append("均线多头排列")
            elif current_price > ma5:
                score += 10
                details['signals'].append("站上MA5")
            
            # 2. MACD (20分)
            if len(closes) >= 10:
                ema12 = self._ema(closes, 12) or 0
                ema26 = self._ema(closes, 26) or 0
                dif = ema12 - ema26
                if dif > 0:
                    score += 15
                    details['signals'].append("MACD正值")
            
            # 3. RSI (15分)
            rsi = self._rsi(closes)
            if rsi and 50 < rsi < 70:
                score += 15
                details['signals'].append(f"RSI强势({rsi:.0f})")
            
            # 4. 波动率 (10分)
            atr = self._atr(rows)
            if atr:
                details['stop_loss'] = round(current_price - 2 * atr, 2)
                details['take_profit'] = round(current_price + 3 * atr, 2)
                score += 10
            
        except Exception as e:
            logger.debug(f"计算{code}得分出错: {e}")
        
        return round(score, 1), details
    
    def _ema(self, data: list, period: int) -> Optional[float]:
        if len(data) < period:
            return None
        multiplier = 2 / (period + 1)
        ema = sum(data[:period]) / period
        for price in data[period:]:
            ema = (price - ema) * multiplier + ema
        return ema
    
    def _rsi(self, closes: list, period: int = 6) -> Optional[float]:
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
    
    def _atr(self, rows: list) -> Optional[float]:
        if len(rows) < 2:
            return None
        tr_list = []
        for i in range(1, min(len(rows), 6)):
            high, low, prev_close = rows[i][2], rows[i][3], rows[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_list.append(tr)
        return sum(tr_list) / len(tr_list) if tr_list else None


class Notifier:
    """多渠道通知器 - 30s超时，3次重试"""
    
    def __init__(self):
        # 从环境变量读取配置
        self.discord_webhook = ""
        self.feishu_webhook = ""
    
    async def send_discord(self, message: str) -> bool:
        """Discord推送 - 30s超时，3次重试"""
        if not self.discord_webhook:
            logger.warning("Discord webhook未配置，跳过")
            return False
        
        for attempt in range(3):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    payload = {"content": message}
                    async with session.post(self.discord_webhook, json=payload) as resp:
                        if resp.status == 204:
                            logger.info("✅ Discord推送成功")
                            return True
                        else:
                            logger.warning(f"Discord返回状态码: {resp.status}")
            except asyncio.TimeoutError:
                logger.warning(f"Discord超时 (尝试{attempt+1}/3)")
            except Exception as e:
                logger.warning(f"Discord失败 (尝试{attempt+1}/3): {e}")
            
            if attempt < 2:
                await asyncio.sleep(1)
        
        logger.error("❌ Discord推送失败，已重试3次")
        return False
    
    async def send_feishu(self, message: str) -> bool:
        """飞书Webhook推送 - 30s超时，3次重试"""
        if not self.feishu_webhook:
            logger.warning("飞书webhook未配置，跳过")
            return False
        
        for attempt in range(3):
            try:
                timeout = aiohttp.ClientTimeout(total=30)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    payload = {
                        "msg_type": "text",
                        "content": {"text": message}
                    }
                    async with session.post(self.feishu_webhook, json=payload) as resp:
                        result = await resp.json()
                        if result.get('code') == 0:
                            logger.info("✅ 飞书推送成功")
                            return True
                        else:
                            logger.warning(f"飞书返回错误: {result}")
            except asyncio.TimeoutError:
                logger.warning(f"飞书超时 (尝试{attempt+1}/3)")
            except Exception as e:
                logger.warning(f"飞书失败 (尝试{attempt+1}/3): {e}")
            
            if attempt < 2:
                await asyncio.sleep(1)
        
        logger.error("❌ 飞书推送失败，已重试3次")
        return False
    
    async def send_all(self, message: str):
        """并发发送到所有渠道"""
        tasks = [
            self.send_discord(message),
            self.send_feishu(message)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        discord_ok = results[0] if not isinstance(results[0], Exception) else False
        feishu_ok = results[1] if not isinstance(results[1], Exception) else False
        
        return {'discord': discord_ok, 'feishu': feishu_ok}


class Hongzhong:
    """红中核心类"""
    
    def __init__(self):
        self.nanfeng = NanfengAPI()
        self.notifier = Notifier()
    
    def format_message(self, stock: Dict, rank: int) -> str:
        """格式化预警消息"""
        time_str = datetime.now().strftime('%H:%M')
        signals_str = ' | '.join(stock['signals'][:3])
        
        return f"""🔔 [财神爷量化预警] #{rank}

📈 **{stock['name']}** ({stock['code']})
⭐ 综合评分: **{stock['score']}/10**

📊 技术信号:
{signals_str}

💰 价格: ¥{stock['price']}
🛑 止损: ¥{stock['stop_loss']}
🎯 目标: ¥{stock['take_profit']}

⏰ {time_str} | 红中🀄
"""
    
    async def run(self):
        """14:45 执行：获取Top3并推送"""
        logger.info("=" * 50)
        logger.info("🀄 红中启动 - 14:45 预警")
        logger.info("=" * 50)
        
        # 1. 获取南风Top3
        top3 = self.nanfeng.get_top3()
        
        if not top3:
            logger.warning("没有符合条件的股票，本次不推送")
            self._save_result([])
            return
        
        # 2. 保存结果
        self._save_result(top3)
        
        # 3. 推送消息
        for i, stock in enumerate(top3, 1):
            message = self.format_message(stock, i)
            logger.info(f"推送 #{i}: {stock['code']}({stock['name']}) {stock['score']}分")
            
            results = await self.notifier.send_all(message)
            
            for channel, ok in results.items():
                status = "✅" if ok else "❌"
                logger.info(f"  {status} {channel}")
        
        logger.info("=" * 50)
        logger.info(f"🀄 预警完成: 推送 {len(top3)} 只股票")
        logger.info("=" * 50)
    
    def _save_result(self, top3: List[Dict]):
        """保存结果到文件"""
        result = {
            'time': datetime.now().isoformat(),
            'count': len(top3),
            'stocks': top3
        }
        
        with open(TOP3_FILE, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        # 追加到日志
        logs = []
        if ALERT_LOG.exists():
            try:
                with open(ALERT_LOG, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                pass
        
        logs.insert(0, result)
        logs = logs[:50]
        
        with open(ALERT_LOG, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存: {TOP3_FILE}")


def main():
    parser = argparse.ArgumentParser(description='红中 - 14:45预警推送')
    parser.add_argument('--run', action='store_true', help='立即执行一次')
    parser.add_argument('--history', action='store_true', help='查看历史')
    
    args = parser.parse_args()
    
    hongzhong = Hongzhong()
    
    if args.run:
        asyncio.run(hongzhong.run())
    
    elif args.history:
        if ALERT_LOG.exists():
            with open(ALERT_LOG, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            print(f"\n🀄 预警历史 (最近{len(logs)}次):\n")
            for log in logs[:5]:
                time = log['time'][:16] if log['time'] else 'N/A'
                stocks = ', '.join([f"{s['code']}({s['score']}分)" for s in log['stocks']])
                print(f"  {time}: {log['count']}只 - {stocks}")
            print()
        else:
            print("暂无历史记录")
    
    else:
        # 默认执行
        asyncio.run(hongzhong.run())


if __name__ == "__main__":
    main()
