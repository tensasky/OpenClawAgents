#!/usr/bin/env python3
"""策略数据库"""

import sqlite3
import json
from datetime import datetime

DB = BASE_DIR / "strategy/strategy.db"

def init_db():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS strategies (
            strategy_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            strategy_type TEXT NOT NULL,
            params_json TEXT NOT NULL,
            last_optimized TIMESTAMP,
            status TEXT DEFAULT 'DRAFT'
        )
    """)
    
    strategies = [
        {'id': '南风_趋势跟踪_01', 'name': '趋势跟踪', 'type': '趋势跟踪', 'status': 'ACTIVE'},
        {'id': '南风_均值回归_01', 'name': '均值回归', 'type': '均值回归', 'status': 'DRAFT'},
        {'id': '南风_突破_01', 'name': '突破策略', 'type': '突破', 'status': 'DRAFT'}
    ]
    
    params = {
        'filters': {'min_ma20_slope': 0.002, 'min_rsi': 40, 'max_rsi': 75},
        'weights': {'bullish': 30, 'ma20_slope': 20, 'rsi': 20},
        'thresholds': {'min_score': 30, 'max_signals': 10}
    }
    
    for s in strategies:
        cursor.execute("""
            INSERT OR REPLACE INTO strategies VALUES (?, ?, ?, ?, ?, ?)
        """, (s['id'], s['name'], s['type'], json.dumps(params), datetime.now().strftime('%Y-%m-%d %H:%M:%S'), s['status']))
    
    conn.commit()
    conn.close()
    print("✅ 策略数据库已初始化")

def get_active():
    conn = sqlite3.connect(DB)
    cursor = conn.cursor()
    cursor.execute("SELECT strategy_id, name, params_json FROM strategies WHERE status='ACTIVE'")
    row = cursor.fetchone()
    conn.close()
    return row

if __name__ == "__main__":
    init_db()
    print("\n=== 策略 ===")
    for s in get_active():
        print(f"  {s[0]}: {s[1]}")
