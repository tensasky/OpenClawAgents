#!/usr/bin/env python3
"""
北风 - 数据库物理隔离迁移脚本
将分钟数据和日线数据分离到不同数据库
"""

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# 路径配置
DATA_DIR = Path.home() / "Documents/OpenClawAgents/beifeng/data"
OLD_DB = DATA_DIR / "stocks.db"
REAL_DB = DATA_DIR / "stocks_real.db"  # 真实历史数据
VIRTUAL_DB = DATA_DIR / "stocks_virtual.db"  # 实时虚拟数据

def create_database(db_path: Path, schema: str):
    """创建新数据库"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(schema)
    conn.commit()
    conn.close()
    print(f"✅ 创建数据库: {db_path}")

def migrate_data():
    """迁移数据"""
    print("="*70)
    print("🌪️ 北风数据库物理隔离迁移")
    print("="*70)
    
    # 1. 备份原数据库
    backup_path = DATA_DIR / f"stocks_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    shutil.copy(OLD_DB, backup_path)
    print(f"\n1️⃣ 备份原数据库: {backup_path}")
    
    # 2. 创建真实数据数据库（历史日线+分钟）
    print("\n2️⃣ 创建真实数据数据库...")
    real_schema = """
    CREATE TABLE IF NOT EXISTS daily (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        amount REAL,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code, timestamp)
    );
    
    CREATE INDEX IF NOT EXISTS idx_daily_lookup ON daily(stock_code, timestamp);
    CREATE INDEX IF NOT EXISTS idx_daily_time ON daily(timestamp);
    
    CREATE TABLE IF NOT EXISTS minute (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        amount REAL,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code, timestamp)
    );
    
    CREATE INDEX IF NOT EXISTS idx_minute_lookup ON minute(stock_code, timestamp);
    CREATE INDEX IF NOT EXISTS idx_minute_time ON minute(timestamp);
    """
    create_database(REAL_DB, real_schema)
    
    # 3. 创建虚拟数据数据库（实时虚拟日线）
    print("\n3️⃣ 创建虚拟数据数据库...")
    virtual_schema = """
    CREATE TABLE IF NOT EXISTS daily_virtual (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_code TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        amount REAL,
        aggregation_count INTEGER,  -- 用于记录聚合了多少分钟
        source TEXT DEFAULT 'virtual',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(stock_code, timestamp)
    );
    
    CREATE INDEX IF NOT EXISTS idx_virtual_lookup ON daily_virtual(stock_code, timestamp);
    CREATE INDEX IF NOT EXISTS idx_virtual_time ON daily_virtual(timestamp);
    
    -- 创建触发器自动更新updated_at
    CREATE TRIGGER IF NOT EXISTS update_virtual_timestamp 
    AFTER UPDATE ON daily_virtual
    BEGIN
        UPDATE daily_virtual SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
    END;
    """
    create_database(VIRTUAL_DB, virtual_schema)
    
    # 4. 迁移历史日线数据
    print("\n4️⃣ 迁移历史日线数据...")
    conn_old = sqlite3.connect(OLD_DB)
    conn_real = sqlite3.connect(REAL_DB)
    
    daily_data = conn_old.execute("""
        SELECT stock_code, timestamp, open, high, low, close, volume, amount, source
        FROM kline_data WHERE data_type = 'daily'
    """).fetchall()
    
    conn_real.executemany("""
        INSERT OR REPLACE INTO daily 
        (stock_code, timestamp, open, high, low, close, volume, amount, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, daily_data)
    conn_real.commit()
    print(f"   迁移 {len(daily_data)} 条日线记录")
    
    # 5. 迁移历史分钟数据
    print("\n5️⃣ 迁移历史分钟数据...")
    minute_data = conn_old.execute("""
        SELECT stock_code, timestamp, open, high, low, close, volume, amount, source
        FROM kline_data WHERE data_type = '1min'
    """).fetchall()
    
    conn_real.executemany("""
        INSERT OR REPLACE INTO minute 
        (stock_code, timestamp, open, high, low, close, volume, amount, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, minute_data)
    conn_real.commit()
    print(f"   迁移 {len(minute_data)} 条分钟记录")
    
    conn_old.close()
    conn_real.close()
    
    # 6. 验证迁移
    print("\n6️⃣ 验证迁移...")
    conn_real = sqlite3.connect(REAL_DB)
    conn_virtual = sqlite3.connect(VIRTUAL_DB)
    
    daily_count = conn_real.execute("SELECT COUNT(*) FROM daily").fetchone()[0]
    minute_count = conn_real.execute("SELECT COUNT(*) FROM minute").fetchone()[0]
    virtual_count = conn_virtual.execute("SELECT COUNT(*) FROM daily_virtual").fetchone()[0]
    
    conn_real.close()
    conn_virtual.close()
    
    print(f"   真实日线: {daily_count} 条")
    print(f"   分钟数据: {minute_count} 条")
    print(f"   虚拟日线: {virtual_count} 条 (新建)")
    
    print("\n" + "="*70)
    print("✅ 物理隔离迁移完成！")
    print("="*70)
    print(f"\n新数据库结构:")
    print(f"  📁 {REAL_DB.name}")
    print(f"     ├── daily (真实日线)")
    print(f"     └── minute (分钟数据)")
    print(f"  📁 {VIRTUAL_DB.name}")
    print(f"     └── daily_virtual (实时虚拟日线)")
    print(f"\n原数据库备份: {backup_path.name}")
    print("="*70)

if __name__ == '__main__':
    migrate_data()
