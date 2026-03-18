#!/usr/bin/env python3
"""
系统架构检查 - 全面诊断数据流
"""

import sqlite3
from pathlib import Path
from datetime import datetime

log.info("="*70)
log.info("🔍 系统架构全面检查")
log.info("="*70)

# 检查点1: 数据库路径一致性
log.info("\n1️⃣ 数据库路径检查")
log.info("-" * 70)

old_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"
new_db = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

log.info(f"旧数据库 (stocks.db): {'✅ 存在' if old_db.exists() else '❌ 不存在'}")
log.info(f"新数据库 (stocks_real.db): {'✅ 存在' if new_db.exists() else '❌ 不存在'}")

if old_db.exists():
    old_size = old_db.stat().st_size / 1024 / 1024
    log.info(f"  大小: {old_size:.1f} MB")

if new_db.exists():
    new_size = new_db.stat().st_size / 1024 / 1024
    log.info(f"  大小: {new_size:.1f} MB")

# 检查点2: 表结构一致性
log.info("\n2️⃣ 表结构检查")
log.info("-" * 70)

if new_db.exists():
    conn = sqlite3.connect(new_db)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cursor.fetchall()]
    
    log.info(f"新数据库表: {tables}")
    
    if 'daily' in tables:
        log.info("  ✅ daily表存在")
    else:
        log.info("  ❌ daily表不存在")
    
    if 'kline_data' in tables:
        log.info("  ⚠️  kline_data表仍存在（旧表）")
    
    conn.close()

# 检查点3: 代码中使用的是哪个数据库
log.info("\n3️⃣ 代码数据库引用检查")
log.info("-" * 70)

import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/ "utils"))
from agent_logger import get_logger

log = get_logger("System")

result = subprocess.run(
    ['grep', '-r', 'stocks.db', '--include=*.py', '.'],
    capture_output=True, text=True, cwd=Path.home() / "Documents/OpenClawAgents"
)

if result.stdout:
    lines = result.stdout.strip().split('\n')
    log.info(f"发现 {len(lines)} 处引用旧数据库:")
    for line in lines[:5]:
        log.info(f"  {line}")
    if len(lines) > 5:
        log.info(f"  ... 还有 {len(lines)-5} 处")
else:
    log.info("  ✅ 未发现旧数据库引用")

# 检查点4: 今日数据完整性
log.info("\n4️⃣ 今日数据完整性检查")
log.info("-" * 70)

if new_db.exists():
    conn = sqlite3.connect(new_db)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 检查日线
    cursor.execute(f"SELECT COUNT(*) FROM daily WHERE date(timestamp) = '{today}'")
    daily_count = cursor.fetchone()[0]
    log.info(f"  日线数据: {daily_count} 条")
    
    # 检查分钟
    cursor.execute(f"SELECT COUNT(*) FROM minute WHERE date(timestamp) = '{today}'")
    minute_count = cursor.fetchone()[0]
    log.info(f"  分钟数据: {minute_count} 条")
    
    # 检查是否有重复数据
    cursor.execute(f"""
        SELECT stock_code, COUNT(*) as cnt
        FROM daily
        WHERE date(timestamp) = '{today}'
        GROUP BY stock_code
        HAVING cnt > 1
    """)
    duplicates = cursor.fetchall()
    if duplicates:
        log.info(f"  ⚠️  发现 {len(duplicates)} 只股票有重复数据")
    else:
        log.info(f"  ✅ 无重复数据")
    
    conn.close()

# 检查点5: 实时数据聚合（分钟->日线）
log.info("\n5️⃣ 实时数据聚合检查")
log.info("-" * 70)

if new_db.exists():
    conn = sqlite3.connect(new_db)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    # 随机选一只股票检查分钟数据聚合
    cursor.execute(f"""
        SELECT stock_code, 
               MIN(open) as min_open, MAX(close) as max_close,
               SUM(volume) as total_volume
        FROM minute
        WHERE date(timestamp) = '{today}'
        GROUP BY stock_code
        LIMIT 1
    """)
    
    result = cursor.fetchone()
    if result:
        code, min_open, max_close, total_vol = result
        log.info(f"  示例 {code}:")
        log.info(f"    分钟数据最低开盘: ¥{min_open:.2f}")
        log.info(f"    分钟数据最高收盘: ¥{max_close:.2f}")
        log.info(f"    分钟成交量总和: {total_vol}")
        
        # 对比日线
        cursor.execute(f"""
            SELECT open, close, volume
            FROM daily
            WHERE stock_code = '{code}' AND date(timestamp) = '{today}'
        """)
        daily = cursor.fetchone()
        if daily:
            d_open, d_close, d_vol = daily
            log.info(f"    日线开盘: ¥{d_open:.2f}")
            log.info(f"    日线收盘: ¥{d_close:.2f}")
            log.info(f"    日线成交: {d_vol}")
            
            if abs(d_close - max_close) > 0.01:
                log.info(f"    ❌ 收盘价格不一致!")
    else:
        log.info("  ⚠️  无分钟数据")
    
    conn.close()

log.info("\n" + "="*70)
log.info("检查完成")
log.info("="*70)
EOF
