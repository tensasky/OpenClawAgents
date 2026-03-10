#!/usr/bin/env python3
"""
东风 - 股票初筛与池管理 Agent (实时交易版)
交易时段 13:30-14:15 实时监控，每15分钟扫描
"""

import json
import logging
import argparse
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import sqlite3
import sys

# 配置路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# 数据源路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
XIFENG_HOTSPOTS = Path.home() / "Documents/OpenClawAgents/xifeng/data/hot_spots.json"

# 输出文件
CANDIDATE_POOL = DATA_DIR / "candidate_pool.json"
STANDBY_POOL = DATA_DIR / "standby_pool.json"
SCAN_LOG = DATA_DIR / "scan_history.json"

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"dongfeng_{datetime.now().strftime('%Y%m%d')}.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("dongfeng")


class DongfengScanner:
    """东风扫描器 - 实时交易时段监控"""
    
    def __init__(self):
        self.beifeng_conn = None
        self.hot_sectors: Dict[str, Dict] = {}  # 热点板块
        self.hot_stocks: Set[str] = set()  # 热点股票代码集合
        self.candidate_pool: List[Dict] = []
        self.standby_pool: List[Dict] = []
        self.load_pools()
        self.load_hot_spots()
    
    def load_hot_spots(self):
        """加载西风的热点数据"""
        if not XIFENG_HOTSPOTS.exists():
            logger.warning(f"热点文件不存在: {XIFENG_HOTSPOTS}")
            return
        
        try:
            with open(XIFENG_HOTSPOTS, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 只关注 High/Medium 热度的板块
            for sector in data.get('hot_spots', []):
                level = sector.get('level', 'Low')
                if level in ['High', 'Medium']:
                    sector_name = sector.get('sector', '')
                    self.hot_sectors[sector_name] = {
                        'level': level,
                        'heat_score': sector.get('heat_score', 0),
                        'stocks': []
                    }
                    # 收集热点股票
                    for stock in sector.get('leading_stocks', []):
                        code = stock.get('code', '')
                        if code:
                            self.hot_stocks.add(code)
                            self.hot_sectors[sector_name]['stocks'].append({
                                'code': code,
                                'name': stock.get('name', ''),
                                'weight': stock.get('weight', 0)
                            })
            
            logger.info(f"加载热点: {len(self.hot_sectors)} 个板块, {len(self.hot_stocks)} 只股票")
        except Exception as e:
            logger.error(f"加载热点数据失败: {e}")
    
    def load_pools(self):
        """加载股票池数据"""
        if CANDIDATE_POOL.exists():
            try:
                with open(CANDIDATE_POOL, 'r', encoding='utf-8') as f:
                    self.candidate_pool = json.load(f)
                logger.info(f"加载候选池: {len(self.candidate_pool)} 只股票")
            except Exception as e:
                logger.error(f"加载候选池失败: {e}")
                self.candidate_pool = []
        
        if STANDBY_POOL.exists():
            try:
                with open(STANDBY_POOL, 'r', encoding='utf-8') as f:
                    self.standby_pool = json.load(f)
                logger.info(f"加载备用池: {len(self.standby_pool)} 只股票")
            except Exception as e:
                logger.error(f"加载备用池失败: {e}")
                self.standby_pool = []
    
    def save_pools(self):
        """保存股票池数据"""
        try:
            with open(CANDIDATE_POOL, 'w', encoding='utf-8') as f:
                json.dump(self.candidate_pool, f, ensure_ascii=False, indent=2)
            
            with open(STANDBY_POOL, 'w', encoding='utf-8') as f:
                json.dump(self.standby_pool, f, ensure_ascii=False, indent=2)
            
            logger.info(f"保存股票池: 候选{len(self.candidate_pool)}, 备用{len(self.standby_pool)}")
        except Exception as e:
            logger.error(f"保存股票池失败: {e}")
    
    def connect_beifeng(self) -> bool:
        """连接北风数据库"""
        if not BEIFENG_DB.exists():
            logger.error(f"北风数据库不存在: {BEIFENG_DB}")
            return False
        try:
            self.beifeng_conn = sqlite3.connect(BEIFENG_DB)
            return True
        except Exception as e:
            logger.error(f"连接北风数据库失败: {e}")
            return False
    
    def get_stock_info(self, stock_code: str) -> Optional[Dict]:
        """获取股票基本信息"""
        if not self.beifeng_conn:
            return None
        
        cursor = self.beifeng_conn.cursor()
        cursor.execute("SELECT code, name, market FROM stocks WHERE code = ?", (stock_code,))
        row = cursor.fetchone()
        
        if row:
            return {'code': row[0], 'name': row[1], 'market': row[2]}
        return None
    
    def get_today_kline(self, stock_code: str) -> Optional[Dict]:
        """获取今日分时/日线数据"""
        if not self.beifeng_conn:
            return None
        
        cursor = self.beifeng_conn.cursor()
        
        # 获取今日数据
        today = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            AND date(timestamp) = date(?)
            ORDER BY timestamp DESC
            LIMIT 1
        """, (stock_code, today))
        
        row = cursor.fetchone()
        if row:
            return {
                'timestamp': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
                'amount': row[6]
            }
        
        # 如果没有日线，尝试获取最新的分钟线聚合
        cursor.execute("""
            SELECT timestamp, open, high, low, close, volume, amount
            FROM kline_data
            WHERE stock_code = ? AND data_type = 'minute'
            AND date(timestamp) = date(?)
            ORDER BY timestamp DESC
            LIMIT 1
        """, (stock_code, today))
        
        row = cursor.fetchone()
        if row:
            return {
                'timestamp': row[0],
                'open': row[1],
                'high': row[2],
                'low': row[3],
                'close': row[4],
                'volume': row[5],
                'amount': row[6]
            }
        
        return None
    
    def get_yesterday_close(self, stock_code: str) -> Optional[float]:
        """获取昨日收盘价"""
        if not self.beifeng_conn:
            return None
        
        cursor = self.beifeng_conn.cursor()
        cursor.execute("""
            SELECT close FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            ORDER BY timestamp DESC
            LIMIT 1 OFFSET 1
        """, (stock_code,))
        
        row = cursor.fetchone()
        return row[0] if row else None
    
    def get_5day_avg_volume(self, stock_code: str) -> Optional[float]:
        """获取前5日平均成交量"""
        if not self.beifeng_conn:
            return None
        
        cursor = self.beifeng_conn.cursor()
        cursor.execute("""
            SELECT volume FROM kline_data
            WHERE stock_code = ? AND data_type = 'daily'
            ORDER BY timestamp DESC
            LIMIT 5 OFFSET 1
        """, (stock_code,))
        
        rows = cursor.fetchall()
        if len(rows) >= 5:
            return sum(row[0] for row in rows) / 5
        return None
    
    def calculate_amplitude(self, today: Dict, yesterday_close: float) -> Optional[float]:
        """计算振幅 (最高-最低)/昨收 * 100"""
        if yesterday_close == 0:
            return None
        amplitude = (today['high'] - today['low']) / yesterday_close * 100
        return round(amplitude, 2)
    
    def calculate_volume_ratio(self, today_volume: float, avg_volume: float) -> Optional[float]:
        """计算成交量比率"""
        if avg_volume == 0:
            return None
        ratio = today_volume / avg_volume
        return round(ratio, 2)
    
    def is_hot_sector_stock(self, stock_code: str) -> Tuple[bool, str]:
        """检查股票是否属于热点板块"""
        for sector_name, sector_info in self.hot_sectors.items():
            for stock in sector_info['stocks']:
                if stock['code'] == stock_code:
                    return True, sector_name
        return False, ""
    
    def scan_stock(self, stock_code: str) -> Optional[Dict]:
        """扫描单只股票"""
        # 获取今日数据
        today = self.get_today_kline(stock_code)
        if not today:
            return None
        
        # 获取昨日收盘价
        yesterday_close = self.get_yesterday_close(stock_code)
        if not yesterday_close:
            return None
        
        # 计算振幅
        amplitude = self.calculate_amplitude(today, yesterday_close)
        if amplitude is None or amplitude < 3.0:
            return None
        
        # 获取5日均量
        avg_volume = self.get_5day_avg_volume(stock_code)
        if not avg_volume:
            return None
        
        # 计算成交量比率
        volume_ratio = self.calculate_volume_ratio(today['volume'], avg_volume)
        if volume_ratio is None or not (1.2 <= volume_ratio <= 2.5):
            return None
        
        # 获取股票信息
        info = self.get_stock_info(stock_code)
        if not info:
            return None
        
        # 检查是否热点板块
        is_hot, sector = self.is_hot_sector_stock(stock_code)
        
        return {
            'code': stock_code,
            'name': info['name'],
            'amplitude': amplitude,
            'volume_ratio': volume_ratio,
            'price': today['close'],
            'change_pct': round((today['close'] - yesterday_close) / yesterday_close * 100, 2),
            'volume': today['volume'],
            'amount': today['amount'],
            'is_hot_sector': is_hot,
            'sector': sector,
            'scan_time': datetime.now().isoformat()
        }
    
    def scan_all(self, use_hot_spots_only: bool = True) -> List[Dict]:
        """扫描所有股票"""
        if not self.connect_beifeng():
            return []
        
        candidates = []
        
        if use_hot_spots_only and self.hot_stocks:
            # 只扫描热点股票
            logger.info(f"扫描热点股票: {len(self.hot_stocks)} 只")
            for code in self.hot_stocks:
                result = self.scan_stock(code)
                if result:
                    candidates.append(result)
        else:
            # 扫描全部股票
            cursor = self.beifeng_conn.cursor()
            cursor.execute("SELECT code FROM stocks")
            all_codes = [row[0] for row in cursor.fetchall()]
            
            logger.info(f"扫描全部股票: {len(all_codes)} 只")
            for i, code in enumerate(all_codes):
                if i % 100 == 0:
                    logger.info(f"进度: {i}/{len(all_codes)}")
                result = self.scan_stock(code)
                if result:
                    candidates.append(result)
        
        # 按热度排序：热点板块优先，然后按振幅排序
        candidates.sort(key=lambda x: (not x['is_hot_sector'], -x['amplitude']))
        
        logger.info(f"扫描完成: 发现 {len(candidates)} 只候选股票")
        return candidates
    
    def update_pools(self, new_candidates: List[Dict]):
        """更新股票池"""
        new_codes = {c['code'] for c in new_candidates}
        current_codes = {c['code'] for c in self.candidate_pool}
        
        # 1. 新进入候选池的股票
        entered = []
        for candidate in new_candidates:
            if candidate['code'] not in current_codes:
                candidate['entry_time'] = datetime.now().isoformat()
                candidate['entry_reason'] = self._generate_entry_reason(candidate)
                self.candidate_pool.append(candidate)
                entered.append(candidate)
                logger.info(f"🌸 新进入候选池: {candidate['code']}({candidate['name']}) - {candidate['entry_reason']}")
        
        # 2. 应移出候选池的股票
        exited = []
        remaining = []
        for current in self.candidate_pool:
            if current['code'] not in new_codes:
                # 移出到备用池
                exit_info = self._generate_exit_info(current)
                self.standby_pool.insert(0, exit_info)  # 新退出的放前面
                exited.append(exit_info)
                logger.info(f"🍂 移出候选池: {current['code']}({current['name']}) - {exit_info['exit_reason']}")
            else:
                # 更新最新数据
                for new_c in new_candidates:
                    if new_c['code'] == current['code']:
                        current.update({
                            'price': new_c['price'],
                            'amplitude': new_c['amplitude'],
                            'volume_ratio': new_c['volume_ratio'],
                            'change_pct': new_c['change_pct'],
                            'last_update': datetime.now().isoformat()
                        })
                        remaining.append(current)
                        break
        
        self.candidate_pool = remaining
        
        # 限制备用池大小
        if len(self.standby_pool) > 200:
            self.standby_pool = self.standby_pool[:200]
        
        return entered, exited
    
    def _generate_entry_reason(self, candidate: Dict) -> str:
        """生成进入理由"""
        reasons = []
        if candidate['is_hot_sector']:
            reasons.append(f"{candidate['sector']}热点")
        reasons.append(f"振幅{candidate['amplitude']}%")
        reasons.append(f"放量{candidate['volume_ratio']}倍")
        return "+".join(reasons)
    
    def _generate_exit_info(self, candidate: Dict) -> Dict:
        """生成退出信息"""
        entry_time = datetime.fromisoformat(candidate.get('entry_time', datetime.now().isoformat()))
        exit_time = datetime.now()
        days_in_pool = (exit_time - entry_time).days
        
        # 判断退出原因
        current_price = candidate.get('price', 0)
        entry_price = candidate.get('price', current_price)
        
        # 重新扫描获取最新状态
        latest = self.scan_stock(candidate['code'])
        
        if latest:
            if latest['amplitude'] < 3.0:
                reason = f"振幅收窄({latest['amplitude']}%)"
            elif latest['volume_ratio'] < 1.2:
                reason = f"量能枯竭({latest['volume_ratio']}倍)"
            elif latest['volume_ratio'] > 2.5:
                reason = f"放量异常({latest['volume_ratio']}倍)"
            else:
                reason = "指标衰减"
        else:
            reason = "数据缺失"
        
        return {
            'code': candidate['code'],
            'name': candidate['name'],
            'entry_time': candidate.get('entry_time', ''),
            'exit_time': exit_time.isoformat(),
            'exit_reason': reason,
            'days_in_pool': days_in_pool,
            'entry_price': entry_price,
            'exit_price': current_price,
            'max_amplitude': candidate.get('amplitude', 0),
            'sector': candidate.get('sector', '')
        }
    
    def record_scan(self, entered: List[Dict], exited: List[Dict], total_candidates: int):
        """记录扫描历史"""
        scan_record = {
            'scan_time': datetime.now().isoformat(),
            'total_candidates': total_candidates,
            'new_entered': len(entered),
            'new_exited': len(exited),
            'current_pool_size': len(self.candidate_pool),
            'current_standby_size': len(self.standby_pool),
            'hot_sectors': list(self.hot_sectors.keys()),
            'entered_codes': [e['code'] for e in entered],
            'exited_codes': [e['code'] for e in exited]
        }
        
        # 追加到日志
        history = []
        if SCAN_LOG.exists():
            try:
                with open(SCAN_LOG, 'r', encoding='utf-8') as f:
                    history = json.load(f)
            except:
                pass
        
        history.insert(0, scan_record)
        history = history[:100]  # 保留最近100条
        
        with open(SCAN_LOG, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        
        logger.info(f"记录扫描历史: 新增{len(entered)}, 退出{len(exited)}")
    
    def run_scan(self, use_hot_spots_only: bool = True):
        """执行一次扫描"""
        logger.info("=" * 60)
        logger.info("🌸 东风开始扫描...")
        logger.info(f"热点板块: {list(self.hot_sectors.keys())}")
        logger.info("=" * 60)
        
        # 重新加载热点数据
        self.load_hot_spots()
        
        # 扫描股票
        candidates = self.scan_all(use_hot_spots_only)
        
        # 更新股票池
        entered, exited = self.update_pools(candidates)
        
        # 保存
        self.save_pools()
        
        # 记录
        self.record_scan(entered, exited, len(candidates))
        
        logger.info("=" * 60)
        logger.info(f"🌸 扫描完成: 候选池 {len(self.candidate_pool)} 只, 备用池 {len(self.standby_pool)} 只")
        logger.info(f"   本次新增: {len(entered)} 只, 退出: {len(exited)} 只")
        logger.info("=" * 60)
        
        return entered, exited
    
    def monitor_mode(self, interval_minutes: int = 15):
        """监控模式 - 持续运行"""
        logger.info("🌸 东风进入监控模式")
        logger.info(f"监控时段: 交易日 13:30-14:15")
        logger.info(f"轮询间隔: {interval_minutes} 分钟")
        
        while True:
            now = datetime.now()
            
            # 检查是否在监控时段 (13:30-14:15)
            start_time = now.replace(hour=13, minute=30, second=0, microsecond=0)
            end_time = now.replace(hour=14, minute=15, second=0, microsecond=0)
            
            if start_time <= now <= end_time:
                logger.info(f"⏰ 监控时段内，执行扫描...")
                self.run_scan(use_hot_spots_only=True)
                
                # 等待下一次扫描
                logger.info(f"⏳ 等待 {interval_minutes} 分钟后下次扫描...")
                time.sleep(interval_minutes * 60)
            else:
                # 非监控时段，计算下次开始时间
                if now < start_time:
                    wait_seconds = (start_time - now).total_seconds()
                    logger.info(f"⏳ 等待监控时段开始，还有 {wait_seconds/60:.0f} 分钟...")
                    time.sleep(min(wait_seconds, 60))  # 最多等60秒检查一次
                else:
                    # 今天已结束，等待明天
                    tomorrow = now + timedelta(days=1)
                    tomorrow_start = tomorrow.replace(hour=13, minute=30, second=0, microsecond=0)
                    wait_seconds = (tomorrow_start - now).total_seconds()
                    logger.info(f"⏳ 今日监控结束，等待明天 13:30...")
                    time.sleep(min(wait_seconds, 300))  # 最多等5分钟检查一次
    
    def close(self):
        """关闭连接"""
        if self.beifeng_conn:
            self.beifeng_conn.close()


def main():
    parser = argparse.ArgumentParser(description='东风 - 股票初筛与池管理')
    parser.add_argument('--scan', action='store_true', help='执行一次扫描')
    parser.add_argument('--monitor', action='store_true', help='进入监控模式(13:30-14:15)')
    parser.add_argument('--all', action='store_true', help='扫描全部股票(非仅热点)')
    parser.add_argument('--list', action='store_true', help='显示候选池')
    parser.add_argument('--standby', action='store_true', help='显示备用池')
    parser.add_argument('--interval', type=int, default=15, help='监控间隔(分钟)')
    
    args = parser.parse_args()
    
    scanner = DongfengScanner()
    
    try:
        if args.scan:
            scanner.run_scan(use_hot_spots_only=not args.all)
        
        elif args.monitor:
            scanner.monitor_mode(interval_minutes=args.interval)
        
        elif args.list:
            pool = scanner.candidate_pool
            print(f"\n🌸 候选池 ({len(pool)} 只):\n")
            print(f"{'代码':<10} {'名称':<10} {'价格':<8} {'振幅':<8} {'放量':<8} {'热点':<10} {'进入时间':<20}")
            print("-" * 90)
            for s in pool[:20]:  # 显示前20只
                hot = s.get('sector', '否') if s.get('is_hot_sector') else '否'
                entry = s.get('entry_time', '')[:19] if s.get('entry_time') else ''
                print(f"{s['code']:<10} {s['name']:<10} {s['price']:<8.2f} {s['amplitude']:<8}% {s['volume_ratio']:<8} {hot:<10} {entry:<20}")
            if len(pool) > 20:
                print(f"... 还有 {len(pool)-20} 只")
            print()
        
        elif args.standby:
            pool = scanner.standby_pool
            print(f"\n🍂 备用池 (最近 {min(len(pool), 20)} 只):\n")
            print(f"{'代码':<10} {'名称':<10} {'退出时间':<20} {'原因':<20} {'天数':<6}")
            print("-" * 70)
            for s in pool[:20]:
                exit_time = s.get('exit_time', '')[:19] if s.get('exit_time') else ''
                print(f"{s['code']:<10} {s['name']:<10} {exit_time:<20} {s.get('exit_reason', ''):<20} {s.get('days_in_pool', 0):<6}")
            print()
        
        else:
            parser.print_help()
    
    except KeyboardInterrupt:
        logger.info("🌸 东风停止")
    finally:
        scanner.close()


if __name__ == "__main__":
    main()
