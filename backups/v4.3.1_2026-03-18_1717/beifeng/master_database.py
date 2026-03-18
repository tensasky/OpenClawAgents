#!/usr/bin/env python3
"""
主数据库管理系统 - Master Data Management
建立股票主数据表，每日更新基础信息
"""

import sqlite3
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class MasterDatabase:
    """主数据库管理器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._init_master_tables()
    
    def _init_master_tables(self):
        """初始化主数据表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 股票主数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_stocks (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                market TEXT,           -- 上海/深圳/北京
                sector TEXT,           -- 所属行业
                industry TEXT,         -- 细分行业
                list_date TEXT,        -- 上市日期
                total_shares REAL,     -- 总股本(亿股)
                float_shares REAL,     -- 流通股本(亿股)
                company_name TEXT,     -- 公司全称
                business_scope TEXT,   -- 经营范围
                updated_at TEXT,       -- 更新时间
                data_source TEXT       -- 数据来源
            )
        ''')
        
        # 2. 数据更新日志
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_update_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                update_time TEXT,
                table_name TEXT,
                records_updated INTEGER,
                records_added INTEGER,
                status TEXT,
                message TEXT
            )
        ''')
        
        # 3. 板块主数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_sectors (
                sector_code TEXT PRIMARY KEY,
                sector_name TEXT NOT NULL,
                parent_sector TEXT,
                description TEXT,
                hot_stocks TEXT,       -- JSON格式存储热门股票
                updated_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 主数据表初始化完成")
    
    def fetch_stock_info_from_tencent(self, stock_codes: List[str]) -> Dict[str, Dict]:
        """从腾讯获取股票基础信息"""
        if not stock_codes:
            return {}
        
        codes_str = ','.join(stock_codes)
        url = f"https://qt.gtimg.cn/q={codes_str}"
        
        results = {}
        
        try:
            response = requests.get(url, timeout=30)
            data = response.text
            
            for line in data.strip().split(';'):
                if '~' in line and '="' in line:
                    try:
                        code_part = line.split('="')[0]
                        code = code_part.replace('v_', '').replace('=', '')
                        parts = line.split('~')
                        
                        if len(parts) > 45:
                            results[code] = {
                                'code': code,
                                'name': parts[1],
                                'market': '上海' if code.startswith('sh') else '深圳' if code.startswith('sz') else '北京',
                                'total_shares': float(parts[44]) if parts[44] else 0,  # 总股本
                                'float_shares': float(parts[45]) if parts[45] else 0,  # 流通股本
                                'list_date': parts[50] if len(parts) > 50 else None,
                            }
                    except:
                        continue
                        
        except Exception as e:
            print(f"❌ 获取数据失败: {e}")
        
        return results
    
    def update_master_stocks(self, batch_size: int = 100):
        """更新股票主数据"""
        print("🔄 开始更新股票主数据...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有股票代码
        cursor.execute("SELECT code FROM stocks")
        all_codes = [row[0] for row in cursor.fetchall()]
        
        total = len(all_codes)
        updated = 0
        added = 0
        
        print(f"总股票数: {total}")
        
        # 分批更新
        for i in range(0, total, batch_size):
            batch = all_codes[i:i+batch_size]
            
            # 获取数据
            data = self.fetch_stock_info_from_tencent(batch)
            
            # 更新数据库
            for code, info in data.items():
                cursor.execute('''
                    INSERT INTO master_stocks 
                    (stock_code, stock_name, market, total_shares, float_shares, updated_at, data_source)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(stock_code) DO UPDATE SET
                        stock_name = excluded.stock_name,
                        total_shares = excluded.total_shares,
                        float_shares = excluded.float_shares,
                        updated_at = excluded.updated_at
                ''', (
                    code,
                    info['name'],
                    info['market'],
                    info['total_shares'],
                    info['float_shares'],
                    datetime.now().isoformat(),
                    'tencent'
                ))
                
                # 检查是新增还是更新
                cursor.execute("SELECT changes()")
                changes = cursor.fetchone()[0]
                if changes > 0:
                    updated += 1
            
            conn.commit()
            
            progress = min(100, (i + len(batch)) / total * 100)
            print(f"  进度: {progress:.1f}% | 已更新: {updated}")
        
        # 记录更新日志
        cursor.execute('''
            INSERT INTO master_update_log 
            (update_time, table_name, records_updated, records_added, status, message)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            'master_stocks',
            updated,
            added,
            'success',
            f'Updated {updated} stocks'
        ))
        
        conn.commit()
        conn.close()
        
        print(f"✅ 更新完成! 共更新 {updated} 只股票")
        return updated
    
    def get_stock_info(self, stock_code: str) -> Dict:
        """获取股票详细信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT stock_code, stock_name, market, sector, industry, 
                   total_shares, float_shares, company_name, business_scope
            FROM master_stocks
            WHERE stock_code = ?
        ''', (stock_code,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'code': row[0],
                'name': row[1],
                'market': row[2],
                'sector': row[3],
                'industry': row[4],
                'total_shares': row[5],
                'float_shares': row[6],
                'company_name': row[7],
                'business_scope': row[8]
            }
        return None
    
    def verify_stock_names(self, sample_size: int = 10):
        """验证股票名称准确性"""
        print("🔍 验证股票名称准确性...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 随机抽样检查
        cursor.execute('''
            SELECT stock_code, stock_name 
            FROM master_stocks 
            ORDER BY RANDOM() 
            LIMIT ?
        ''', (sample_size,))
        
        samples = cursor.fetchall()
        conn.close()
        
        print(f"\n随机抽样检查 ({sample_size}只):")
        print("-" * 60)
        
        mismatches = []
        
        for code, db_name in samples:
            # 从腾讯实时获取
            url = f"https://qt.gtimg.cn/q={code}"
            try:
                response = requests.get(url, timeout=10)
                if '~' in response.text:
                    parts = response.text.split('~')
                    if len(parts) > 1:
                        tencent_name = parts[1]
                        match = "✅" if db_name == tencent_name else "❌"
                        print(f"{match} {code}: 数据库[{db_name}] vs 腾讯[{tencent_name}]")
                        
                        if db_name != tencent_name:
                            mismatches.append((code, db_name, tencent_name))
            except:
                print(f"⚠️  {code}: 检查失败")
        
        if mismatches:
            print(f"\n❌ 发现 {len(mismatches)} 条不匹配记录:")
            for code, db_name, tencent_name in mismatches:
                print(f"  {code}: {db_name} → 应为: {tencent_name}")
        else:
            print("\n✅ 所有抽样股票名称正确!")
        
        return len(mismatches) == 0

def main():
    """主程序 - 每日更新"""
    print("="*70)
    print("🗄️  主数据库管理系统 - 每日更新")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    master = MasterDatabase()
    
    # 1. 更新股票主数据
    updated = master.update_master_stocks(batch_size=100)
    
    # 2. 验证数据准确性
    print("\n" + "="*70)
    is_valid = master.verify_stock_names(sample_size=20)
    
    # 3. 显示统计
    print("\n" + "="*70)
    print("📊 主数据库统计:")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM master_stocks")
    total = cursor.fetchone()[0]
    print(f"  股票总数: {total}")
    
    cursor.execute("SELECT COUNT(DISTINCT market) FROM master_stocks")
    markets = cursor.fetchone()[0]
    print(f"  市场数量: {markets}")
    
    cursor.execute("SELECT MAX(updated_at) FROM master_stocks")
    last_update = cursor.fetchone()[0]
    print(f"  最后更新: {last_update}")
    
    conn.close()
    
    print("\n" + "="*70)
    if is_valid:
        print("✅ 主数据库更新完成，数据验证通过!")
    else:
        print("⚠️  主数据库更新完成，但有部分数据需要修正")
    print("="*70)

if __name__ == '__main__':
    main()
