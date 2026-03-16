#!/usr/bin/env python3
"""
股票板块映射数据更新
从西风、东财等获取板块关联数据
"""

import sqlite3
import requests
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class StockSectorMapper:
    """股票板块映射器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._init_tables()
    
    def _init_tables(self):
        """初始化板块映射表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 股票-板块映射表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stock_sector_map (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                sector_name TEXT,
                sector_type TEXT,  -- industry/concept/region
                is_primary INTEGER, -- 1=主要板块
                updated_at TEXT
            )
        ''')
        
        # 创建索引
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_stock_sector 
            ON stock_sector_map(stock_code, sector_name)
        ''')
        
        conn.commit()
        conn.close()
    
    def build_sector_mapping_from_xifeng(self):
        """从西风数据库构建板块映射"""
        print("🔄 从西风数据库构建板块映射...")
        
        xifeng_db = Path.home() / "Documents/OpenClawAgents/xifeng/data/xifeng.db"
        if not xifeng_db.exists():
            print("❌ 西风数据库不存在")
            return 0
        
        conn_src = sqlite3.connect(xifeng_db)
        cursor_src = conn_src.cursor()
        
        conn_dst = sqlite3.connect(self.db_path)
        cursor_dst = conn_dst.cursor()
        
        # 获取西风中的板块和龙头股
        cursor_src.execute("""
            SELECT sector_name, leading_stocks 
            FROM sectors 
            WHERE leading_stocks IS NOT NULL
        """)
        
        sectors = cursor_src.fetchall()
        inserted = 0
        
        for sector_name, stocks_json in sectors:
            try:
                # 解析JSON
                stocks = json.loads(stocks_json) if stocks_json else []
                
                # 将板块和股票关联
                for stock_info in stocks:
                    if isinstance(stock_info, dict):
                        code = stock_info.get('code', '')
                        if code:
                            # 标准化代码格式
                            if '.' in code:
                                code = code.replace('.', '')
                            
                            cursor_dst.execute('''
                                INSERT OR REPLACE INTO stock_sector_map
                                (stock_code, sector_name, sector_type, is_primary, updated_at)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (
                                code,
                                sector_name,
                                'hot_sector',  # 热点板块
                                1,
                                datetime.now().isoformat()
                            ))
                            inserted += 1
            except Exception as e:
                print(f"  处理 {sector_name} 失败: {e}")
        
        conn_dst.commit()
        conn_src.close()
        conn_dst.close()
        
        print(f"✅ 从西风导入 {inserted} 条板块映射")
        return inserted
    
    def get_stock_sectors(self, stock_code: str) -> List[str]:
        """获取股票所属板块"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT sector_name FROM stock_sector_map
            WHERE stock_code = ?
            ORDER BY is_primary DESC
        ''', (stock_code,))
        
        sectors = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return sectors
    
    def update_master_with_sectors(self):
        """更新master_stocks表中的板块信息"""
        print("🔄 更新master_stocks表中的板块信息...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有有板块映射的股票
        cursor.execute('''
            SELECT DISTINCT stock_code FROM stock_sector_map
        ''')
        
        stocks = cursor.fetchall()
        updated = 0
        
        for (stock_code,) in stocks:
            # 获取主要板块
            sectors = self.get_stock_sectors(stock_code)
            if sectors:
                primary_sector = sectors[0]
                all_sectors = json.dumps(sectors, ensure_ascii=False)
                
                # 更新master_stocks
                cursor.execute('''
                    UPDATE master_stocks
                    SET sector = ?, industry = ?
                    WHERE stock_code = ?
                ''', (primary_sector, all_sectors, stock_code))
                
                if cursor.rowcount > 0:
                    updated += 1
        
        conn.commit()
        conn.close()
        
        print(f"✅ 更新了 {updated} 只股票的板块信息")
        return updated

def main():
    """主程序"""
    print("="*70)
    print("🔗 股票板块映射数据更新")
    print("="*70)
    
    mapper = StockSectorMapper()
    
    # 1. 从西风构建映射
    inserted = mapper.build_sector_mapping_from_xifeng()
    
    # 2. 更新master_stocks
    if inserted > 0:
        updated = mapper.update_master_with_sectors()
    
    print("\n" + "="*70)
    print("✅ 板块映射更新完成!")
    print("="*70)

if __name__ == '__main__':
    main()
