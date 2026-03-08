#!/usr/bin/env python3
"""
北风 - 监控守护进程
功能：
1. 监控数据新鲜度
2. 自动触发补数
3. 数据源故障切换
4. 异常告警
"""

import os
import sys
import json
import time
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import subprocess

# 配置
WORKSPACE = Path.home() / ".openclaw/agents/beifeng"
DATA_DIR = WORKSPACE / "data"
LOG_DIR = WORKSPACE / "logs"
STATE_FILE = WORKSPACE / ".monitor_state.json"
ALERT_COOLDOWN = 3600  # 告警冷却时间（秒）
FRESHNESS_THRESHOLD = 10  # 数据新鲜度阈值（分钟）

# 日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "monitor.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("北风监控")


class DataFreshnessChecker:
    """数据新鲜度检查器"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def check_all(self) -> Dict[str, Dict]:
        """检查所有股票的数据新鲜度"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        cursor = conn.execute("""
            SELECT stock_code, 
                   MAX(timestamp) as latest_time,
                   COUNT(*) as total_records
            FROM kline_data 
            GROUP BY stock_code
        """)
        
        results = {}
        now = datetime.now()
        
        for row in cursor.fetchall():
            code = row['stock_code']
            latest = datetime.fromisoformat(row['latest_time'])
            age_minutes = (now - latest).total_seconds() / 60
            
            results[code] = {
                'latest_time': latest,
                'age_minutes': age_minutes,
                'is_fresh': age_minutes < FRESHNESS_THRESHOLD,
                'total_records': row['total_records']
            }
        
        conn.close()
        return results
    
    def get_stale_stocks(self) -> List[str]:
        """获取数据过期的股票列表"""
        all_stocks = self.check_all()
        stale = [
            code for code, info in all_stocks.items()
            if not info['is_fresh']
        ]
        return stale


class AutoHealer:
    """自动修复器"""
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        self.db_path = workspace / "data" / "stocks.db"
    
    def heal(self, stale_stocks: List[str]):
        """执行自动修复"""
        if not stale_stocks:
            logger.info("✅ 所有数据新鲜，无需修复")
            return True
        
        logger.warning(f"🔄 发现 {len(stale_stocks)} 只股票数据过期，开始修复")
        
        # 分批修复，避免一次请求太多
        batch_size = 10
        for i in range(0, len(stale_stocks), batch_size):
            batch = stale_stocks[i:i+batch_size]
            self._update_batch(batch)
            time.sleep(1)  # 避免请求过快
        
        return True
    
    def _update_batch(self, stocks: List[str]):
        """更新一批股票"""
        stock_str = " ".join(stocks)
        cmd = f"cd {self.workspace} && python3 beifeng.py {stock_str} --type daily"
        
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"✅ 修复成功: {', '.join(stocks)}")
            else:
                logger.error(f"❌ 修复失败: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            logger.error(f"⏱️ 修复超时: {', '.join(stocks)}")
        except Exception as e:
            logger.error(f"💥 修复异常: {e}")


class AlertManager:
    """告警管理器"""
    
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.state = self._load_state()
    
    def _load_state(self) -> Dict:
        """加载状态"""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except:
                pass
        return {'last_alert': 0, 'alert_count': 0}
    
    def _save_state(self):
        """保存状态"""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f)
    
    def should_alert(self) -> bool:
        """检查是否应该发送告警（冷却时间）"""
        now = time.time()
        if now - self.state['last_alert'] > ALERT_COOLDOWN:
            self.state['last_alert'] = now
            self.state['alert_count'] += 1
            self._save_state()
            return True
        return False
    
    def send_alert(self, message: str):
        """发送告警"""
        if not self.should_alert():
            return
        
        logger.warning(f"🚨 告警: {message}")
        
        # 记录到日志
        alert_log = LOG_DIR / "alerts.log"
        with open(alert_log, 'a') as f:
            f.write(f"[{datetime.now()}] {message}\n")
        
        # 发送 Discord 通知
        try:
            from discord_notify import send_alert
            send_alert(message)
        except Exception as e:
            logger.error(f"Discord 通知失败: {e}")


class BeiFengMonitor:
    """北风监控主类"""
    
    def __init__(self):
        self.workspace = WORKSPACE
        self.db_path = DATA_DIR / "stocks.db"
        self.checker = DataFreshnessChecker(str(self.db_path))
        self.healer = AutoHealer(self.workspace)
        self.alerter = AlertManager(STATE_FILE)
    
    def run(self):
        """执行一次监控检查"""
        logger.info("=" * 50)
        logger.info("🔍 北风监控检查启动")
        
        # 1. 检查数据库
        if not self.db_path.exists():
            logger.error("❌ 数据库不存在！")
            self.alerter.send_alert("数据库文件丢失")
            return False
        
        # 2. 检查数据新鲜度
        freshness = self.checker.check_all()
        total = len(freshness)
        fresh_count = sum(1 for info in freshness.values() if info['is_fresh'])
        stale_count = total - fresh_count
        
        logger.info(f"📊 数据状态: 总共 {total} 只, 新鲜 {fresh_count} 只, 过期 {stale_count} 只")
        
        # 3. 获取过期股票
        stale_stocks = self.checker.get_stale_stocks()
        
        # 4. 自动修复
        if stale_stocks:
            logger.info(f"🔄 开始自动修复 {len(stale_stocks)} 只股票...")
            self.healer.heal(stale_stocks)
            
            # 再次检查
            time.sleep(2)
            still_stale = self.checker.get_stale_stocks()
            if still_stale:
                self.alerter.send_alert(f"自动修复后仍有 {len(still_stale)} 只股票数据过期")
        
        # 5. 检查错误日志
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM error_log WHERE timestamp > datetime('now', '-1 hour')"
        )
        error_count = cursor.fetchone()[0]
        conn.close()
        
        if error_count > 10:
            self.alerter.send_alert(f"过去1小时错误数: {error_count}")
        
        # 每4小时发送一次进度报告
        if datetime.now().hour % 4 == 0 and datetime.now().minute < 10:
            try:
                from discord_notify import send_progress_report
                cursor = conn.execute("SELECT COUNT(DISTINCT stock_code) as stocks, COUNT(*) as records FROM kline_data")
                row = cursor.fetchone()
                cursor = conn.execute("SELECT MAX(timestamp) as latest FROM kline_data")
                latest = cursor.fetchone()[0]
                send_progress_report(row['stocks'], row['records'], latest)
                logger.info("📤 已发送进度报告到 Discord")
            except Exception as e:
                logger.error(f"进度报告发送失败: {e}")
        
        logger.info("✅ 监控检查完成")
        return True


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description='北风监控守护')
    parser.add_argument('--daemon', action='store_true', help='守护模式（循环运行）')
    parser.add_argument('--interval', type=int, default=300, help='检查间隔（秒）')
    
    args = parser.parse_args()
    
    monitor = BeiFengMonitor()
    
    if args.daemon:
        logger.info(f"🤖 守护模式启动，间隔 {args.interval} 秒")
        while True:
            try:
                monitor.run()
            except Exception as e:
                logger.error(f"💥 监控异常: {e}")
            time.sleep(args.interval)
    else:
        monitor.run()


if __name__ == '__main__':
    main()
