#!/usr/bin/env python3
"""数据库维护 - VACUUM + 清理"""

import sqlite3
import os
from datetime import datetime

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

def get_db_size(db_path):
    """获取数据库大小"""
    if os.path.exists(db_path):
        return os.path.getsize(db_path) / 1024 / 1024  # MB
    return 0

def vacuum_db(db_path, name):
    """ VACUUM数据库 """
    print(f"\n=== {name} 维护 ===")
    
    size_before = get_db_size(db_path)
    print(f"  维护前: {size_before:.1f} MB")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. 分析表
    cursor.execute("ANALYZE")
    
    # 2. VACUUM
    cursor.execute("VACUUM")
    
    # 3. 清理日志表
    try:
        # 清理fetch_log (保留7天)
        cursor.execute("""
            DELETE FROM fetch_log 
            WHERE start_time < datetime('now', '-7 days')
        """)
        deleted = cursor.rowcount
        print(f"  清理fetch_log: {deleted}条")
    except:
        pass
    
    # 4. 清理过期信号 (保留30天)
    try:
        cursor.execute(f"DELETE FROM signals WHERE timestamp < datetime('now', '-30 days')")
        deleted = cursor.rowcount
        print(f"  清理signals: {deleted}条")
    except:
        pass
    
    conn.commit()
    conn.close()
    
    size_after = get_db_size(db_path)
    print(f"  维护后: {size_after:.1f} MB")
    print(f"  节省: {size_before - size_after:.1f} MB")

def main():
    print("="*50)
    print("🧹 数据库维护")
    print("="*50)
    
    # stocks_real.db
    vacuum_db(STOCKS_DB, "stocks_real.db")
    
    # signals_v3.db
    vacuum_db(SIGNALS_DB, "signals_v3.db")
    
    print("\n✅ 维护完成")

if __name__ == "__main__":
    main()
