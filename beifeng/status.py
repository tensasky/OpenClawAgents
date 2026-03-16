#!/usr/bin/env python3
"""
北风 - 状态查看工具
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("北风")


WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
DB_PATH = WORKSPACE / "data" / "stocks_real.db"

def show_status():
    """显示北风状态"""
    log.info("🌪️ 北风状态报告")
    log.info("=" * 50)
    
    if not DB_PATH.exists():
        log.info("❌ 数据库不存在")
        return
    
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    
    # 1. 股票数量
    cursor = conn.execute("SELECT COUNT(DISTINCT stock_code) FROM kline_data")
    stock_count = cursor.fetchone()[0]
    log.info(f"📊 监控股票: {stock_count} 只")
    
    # 2. 数据总量
    cursor = conn.execute("SELECT COUNT(*) FROM kline_data")
    total_records = cursor.fetchone()[0]
    log.info(f"📈 总记录数: {total_records:,} 条")
    
    # 3. 最新数据时间
    cursor = conn.execute("SELECT MAX(timestamp) FROM kline_data")
    latest = cursor.fetchone()[0]
    log.info(f"🕐 最新数据: {latest}")
    
    # 4. 数据新鲜度
    if latest:
        latest_dt = datetime.fromisoformat(latest)
        age = datetime.now() - latest_dt
        log.info(f"⏱️  数据年龄: {age.days} 天 {age.seconds//3600} 小时")
        
        # 判断是否正常（股市工作日15:00收盘）
        if age.days <= 3:
            log.info("✅ 数据状态: 正常")
        else:
            log.info("⚠️  数据状态: 可能过期")
    
    # 5. 今日抓取统计
    cursor = conn.execute("""
        SELECT status, COUNT(*) as count 
        FROM fetch_log 
        WHERE date(created_at) = date('now')
        GROUP BY status
    """)
    log.info("\n📋 今日抓取:")
    for row in cursor.fetchall():
        status_icon = "✅" if row['status'] == 'SUCCESS' else "❌" if row['status'] == 'FAILED' else "⚠️"
        log.info(f"  {status_icon} {row['status']}: {row['count']} 次")
    
    # 6. 最近错误
    cursor = conn.execute("""
        SELECT stock_code, reason, timestamp 
        FROM error_log 
        ORDER BY timestamp DESC 
        LIMIT 3
    """)
    errors = cursor.fetchall()
    if errors:
        log.info("\n🚨 最近错误:")
        for row in errors:
            log.info(f"  - {row['stock_code']}: {row['reason'][:50]}... ({row['timestamp']})")
    
    conn.close()
    log.info("\n" + "=" * 50)
    log.info(f"💡 提示: 运行 'python3 monitor.py' 手动检查")

if __name__ == '__main__':
    show_status()
