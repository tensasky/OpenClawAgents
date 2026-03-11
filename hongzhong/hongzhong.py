#!/usr/bin/env python3
"""
红中 (Red Dragon) V2 - 决策预警与自动化通信专家
集成南风V5.1精选策略，14:45运行，推送Top3

改进:
1. 使用南风V5.1精选策略 (每天最多5只，分数>=8.5)
2. 市场环境检查 (大盘无趋势时提醒)
3. 热点板块标记
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

# 导入股票名称查询
from stock_names import get_stock_name, batch_get_stock_names

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
logger = logging.getLogger("红中V2")


class NanfengV51API:
    """调用南风V5.1精选策略"""
    
    def __init__(self):
        self.db_path = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
        # 动态导入V5.1
        try:
            from nanfeng_v5_1 import NanFengV5_1
            self.v51 = NanFengV5_1()
            self.use_v51 = True
            logger.info("✅ 成功加载南风V5.1")
        except Exception as e:
            logger.error(f"加载V5.1失败: {e}，将使用备用逻辑")
            self.use_v51 = False
    
    def get_top_signals(self, max_signals: int = 3) -> List[Dict]:
        """
        获取南风V5.1精选信号
        返回: [{code, score, price, stop_loss, take_profit, signals, warnings, is_hot, sector}, ...]
        """
        if not self.use_v51:
            return self._fallback_get_signals(max_signals)
        
        try:
            # 检查市场环境
            market_ok, market_msg = self.v51.check_market_environment()
            logger.info(f"市场环境: {market_msg}")
            
            # 扫描信号 (扫描300只，精选Top 5，然后取前3)
            signals = self.v51.scan_signals(max_stocks=300)
            
            # 取前N个
            top_signals = signals[:max_signals]
            
            # 转换为标准格式，并查询股票名称
            result = []
            for s in top_signals:
                # 获取股票中文名
                stock_name = get_stock_name(s.stock_code)
                
                result.append({
                    'code': s.stock_code,
                    'name': stock_name,
                    'score': s.total_score,
                    'trend_score': s.trend_score,
                    'momentum_score': s.momentum_score,
                    'volume_score': s.volume_score,
                    'quality_score': s.quality_score,
                    'price': round(s.current_price, 2),
                    'stop_loss': round(s.stop_loss, 2),
                    'take_profit_1': round(s.take_profit_1, 2),
                    'take_profit_2': round(s.take_profit_2, 2),
                    'signals': s.signals,
                    'warnings': s.warnings,
                    'is_hot_sector': s.is_hot_sector,
                    'sector': s.sector,
                    'adx': round(s.adx, 1),
                    'rsi': round(s.rsi, 0),
                    'ma20_slope': round(s.ma20_slope * 100, 2),
                    'relative_strength': round(s.relative_strength * 100, 0),
                    'confidence': s.confidence,
                    'position_size': s.position_size,
                    'market_ok': market_ok,
                    'market_msg': market_msg
                })
            
            logger.info(f"南风V5.1精选完成: 从300只中精选出{len(signals)}只，取Top{len(result)}")
            for r in result:
                hot_tag = "🔥" if r['is_hot_sector'] else ""
                logger.info(f"  🀄 {r['code']}: {r['score']:.1f}分 {hot_tag}")
            
            return result
            
        except Exception as e:
            logger.error(f"V5.1扫描失败: {e}")
            return self._fallback_get_signals(max_signals)
    
    def _fallback_get_signals(self, max_signals: int = 3) -> List[Dict]:
        """备用逻辑 - 简单SQL查询"""
        logger.warning("使用备用逻辑获取信号")
        
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 获取最近有数据的股票
            cursor.execute("""
                SELECT DISTINCT stock_code 
                FROM kline_data 
                WHERE data_type = 'daily'
                ORDER BY stock_code
                LIMIT 100
            """)
            
            stocks = [row[0] for row in cursor.fetchall()]
            conn.close()
            
            # 简单评分（仅作备用）
            scored = []
            for code in stocks[:50]:
                scored.append({
                    'code': code,
                    'score': 7.0,
                    'price': 0.0,
                    'stop_loss': 0.0,
                    'take_profit_1': 0.0,
                    'take_profit_2': 0.0,
                    'signals': ['备用模式'],
                    'warnings': ['V5.1未加载'],
                    'is_hot_sector': False,
                    'sector': '',
                    'adx': 0,
                    'rsi': 0,
                    'confidence': 0.5,
                    'position_size': 0.1,
                    'market_ok': True,
                    'market_msg': '备用模式'
                })
            
            scored.sort(key=lambda x: x['score'], reverse=True)
            return scored[:max_signals]
            
        except Exception as e:
            logger.error(f"备用逻辑也失败: {e}")
            return []


class Notifier:
    """多渠道通知器 - 30s超时，3次重试"""
    
    def __init__(self):
        # 从环境变量或配置文件读取
        self.discord_webhook = self._load_config('discord_webhook', '')
        self.feishu_webhook = self._load_config('feishu_webhook', '')
    
    def _load_config(self, key: str, default: str) -> str:
        """从配置文件加载"""
        config_file = Path.home() / ".openclaw/agents/hongzhong/config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    return config.get(key, default)
            except:
                pass
        return default
    
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


class HongzhongV2:
    """红中V2核心类"""
    
    def __init__(self):
        self.nanfeng = NanfengV51API()
        self.notifier = Notifier()
    
    def format_message(self, stock: Dict, rank: int, total: int) -> str:
        """格式化预警消息 - 包含详细得分构成和股票名称"""
        time_str = datetime.now().strftime('%H:%M')
        signals_str = ' | '.join(stock['signals'][:4])
        warnings_str = ' | '.join(stock['warnings'][:2]) if stock['warnings'] else '无'
        
        hot_tag = "🔥热点 " if stock['is_hot_sector'] else ""
        name_tag = f"({stock['name']}) " if stock.get('name') else ""
        market_warning = ""
        if not stock.get('market_ok', True):
            market_warning = "⚠️ 市场环境一般，谨慎操作\n"
        
        # 计算得分构成
        trend_weighted = stock.get('trend_score', 0) * 0.4
        momentum_weighted = stock.get('momentum_score', 0) * 0.3
        volume_weighted = stock.get('volume_score', 0) * 0.2
        quality_weighted = stock.get('quality_score', 0) * 0.1
        
        return f"""🚨 [财神爷量化预警 V5.1] #{rank}/{total}

📈 **{stock['code']}** {name_tag}{hot_tag}
⭐ 综合评分: **{stock['score']:.1f}/10** | 置信度: {stock['confidence']:.0%}

📊 得分构成:
  ├─ 趋势: {trend_weighted:.1f}分 (40% × {stock.get('trend_score', 0):.0f})
  ├─ 动量: {momentum_weighted:.1f}分 (30% × {stock.get('momentum_score', 0):.0f})
  ├─ 成交量: {volume_weighted:.1f}分 (20% × {stock.get('volume_score', 0):.0f})
  └─ 质量: {quality_weighted:.1f}分 (10% × {stock.get('quality_score', 0):.0f})

✅ 买入信号:
{signals_str}

⚠️ 风险提示:
{warnings_str}

💰 价格: ¥{stock['price']}
🛑 止损: ¥{stock['stop_loss']} ({(stock['price']-stock['stop_loss'])/stock['price']:.1%})
🎯 目标1: ¥{stock['take_profit_1']} (+4%)
🎯 目标2: ¥{stock['take_profit_2']} (+8%)

📈 技术指标:
  ADX: {stock['adx']} | RSI: {stock['rsi']} | MA20斜率: {stock.get('ma20_slope', 0)}%
  相对强度: 前{stock.get('relative_strength', 0):.0f}%
💼 建议仓位: {stock['position_size']:.0%}
{market_warning}
⏰ {time_str} | 红中🀄 | 南风V5.1
"""
    
    async def run(self):
        """14:45 执行：获取精选信号并推送"""
        logger.info("=" * 60)
        logger.info("🀄 红中V2启动 - 14:45 预警 (集成南风V5.1)")
        logger.info("=" * 60)
        
        # 1. 获取V5.1精选信号
        signals = self.nanfeng.get_top_signals(max_signals=3)
        
        if not signals:
            logger.warning("没有符合条件的股票，本次不推送")
            # 推送空仓提醒
            await self._send_empty_alert()
            self._save_result([])
            return
        
        # 2. 保存结果
        self._save_result(signals)
        
        # 3. 推送消息
        for i, stock in enumerate(signals, 1):
            message = self.format_message(stock, i, len(signals))
            hot_tag = "🔥" if stock['is_hot_sector'] else ""
            logger.info(f"推送 #{i}: {stock['code']} {stock['score']:.1f}分 {hot_tag}")
            
            results = await self.notifier.send_all(message)
            
            for channel, ok in results.items():
                status = "✅" if ok else "❌"
                logger.info(f"  {status} {channel}")
        
        logger.info("=" * 60)
        logger.info(f"🀄 预警完成: 推送 {len(signals)} 只股票")
        logger.info("=" * 60)
    
    async def _send_empty_alert(self):
        """发送空仓提醒"""
        time_str = datetime.now().strftime('%H:%M')
        message = f"""📊 [财神爷量化预警 V5.1]

今日暂无符合条件的精选信号

可能原因:
• 市场环境不佳 (ADX<30 或大盘下跌)
• 无股票达到8.5分门槛
• 建议观望，等待更好时机

⏰ {time_str} | 红中🀄 | 南风V5.1
"""
        await self.notifier.send_all(message)
    
    def _save_result(self, signals: List[Dict]):
        """保存结果到文件"""
        result = {
            'time': datetime.now().isoformat(),
            'version': 'V5.1',
            'count': len(signals),
            'signals': signals
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
        logs = logs[:100]  # 保留最近100条
        
        with open(ALERT_LOG, 'w', encoding='utf-8') as f:
            json.dump(logs, f, ensure_ascii=False, indent=2)
        
        logger.info(f"结果已保存: {TOP3_FILE}")


def main():
    parser = argparse.ArgumentParser(description='红中V2 - 14:45预警推送 (南风V5.1)')
    parser.add_argument('--run', action='store_true', help='立即执行一次')
    parser.add_argument('--history', action='store_true', help='查看历史')
    parser.add_argument('--test', action='store_true', help='测试模式(不发送通知)')
    
    args = parser.parse_args()
    
    hongzhong = HongzhongV2()
    
    if args.test:
        # 测试模式：只获取信号，不发送通知
        logger.info("🧪 测试模式 - 只获取信号")
        signals = hongzhong.nanfeng.get_top_signals(max_signals=3)
        print(f"\n获取到 {len(signals)} 个信号:")
        for s in signals:
            hot_tag = "🔥" if s['is_hot_sector'] else ""
            print(f"  {s['code']}: {s['score']:.1f}分 {hot_tag}")
            print(f"    信号: {', '.join(s['signals'][:3])}")
            print(f"    警告: {', '.join(s['warnings'][:2])}")
    
    elif args.history:
        if ALERT_LOG.exists():
            with open(ALERT_LOG, 'r', encoding='utf-8') as f:
                logs = json.load(f)
            print(f"\n🀄 预警历史 (最近{len(logs)}次):\n")
            for log in logs[:10]:
                time = log['time'][:16] if log['time'] else 'N/A'
                version = log.get('version', 'V1')
                signals = ', '.join([f"{s['code']}({s['score']:.1f}分)" for s in log['signals']])
                print(f"  {time} [{version}]: {log['count']}只 - {signals}")
            print()
        else:
            print("暂无历史记录")
    
    elif args.run:
        asyncio.run(hongzhong.run())
    
    else:
        # 默认执行
        asyncio.run(hongzhong.run())


if __name__ == "__main__":
    main()
