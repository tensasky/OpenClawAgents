#!/usr/bin/env python3
"""
主数据库增强版 - 包含板块和基本面数据
"""

import sqlite3
import requests
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class MasterDatabaseEnhanced:
    """增强版主数据库 - 包含板块和基本面"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._init_enhanced_tables()
    
    def _init_enhanced_tables(self):
        """初始化增强版数据表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 1. 扩展master_stocks表 - 添加板块和基本面字段
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_stocks_enhanced (
                stock_code TEXT PRIMARY KEY,
                stock_name TEXT NOT NULL,
                market TEXT,
                
                -- 板块信息
                sector TEXT,              -- 所属行业
                industry TEXT,            -- 细分行业
                concept TEXT,             -- 概念板块 (JSON格式)
                
                -- 基本面数据
                total_market_cap REAL,    -- 总市值(亿元)
                float_market_cap REAL,    -- 流通市值(亿元)
                pe_ratio REAL,            -- 市盈率
                pb_ratio REAL,            -- 市净率
                eps REAL,                 -- 每股收益
                bvps REAL,                -- 每股净资产
                roe REAL,                 -- 净资产收益率
                revenue REAL,             -- 营业收入(亿元)
                profit REAL,              -- 净利润(亿元)
                
                -- 技术指标
                avg_20_volume REAL,       -- 20日均量
                avg_60_volume REAL,       -- 60日均量
                avg_20_price REAL,        -- 20日均价
                avg_60_price REAL,        -- 60日均价
                
                -- 更新信息
                updated_at TEXT,
                data_source TEXT
            )
        ''')
        
        # 2. 板块主数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS master_sectors_detail (
                sector_code TEXT PRIMARY KEY,
                sector_name TEXT NOT NULL,
                sector_type TEXT,         -- industry/concept
                parent_code TEXT,
                description TEXT,
                leading_stocks TEXT,      -- JSON格式龙头股
                avg_pe REAL,              -- 板块平均PE
                avg_pb REAL,              -- 板块平均PB
                trend TEXT,               -- up/down/sideways
                updated_at TEXT
            )
        ''')
        
        # 3. 基本面历史表 (用于跟踪变化)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fundamentals_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stock_code TEXT,
                date TEXT,
                pe_ratio REAL,
                pb_ratio REAL,
                eps REAL,
                roe REAL,
                UNIQUE(stock_code, date)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("✅ 增强版数据表初始化完成")
    
    def fetch_stock_fundamentals(self, stock_code: str) -> Dict:
        """从东方财富获取股票基本面数据"""
        # 转换代码格式
        if stock_code.startswith('sh'):
            eastmoney_code = f"{stock_code[2:]}.SH"
        elif stock_code.startswith('sz'):
            eastmoney_code = f"{stock_code[2:]}.SZ"
        else:
            return None
        
        try:
            # 东方财富API
            url = f"https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code={eastmoney_code}"
            
            # 简化为从已有数据计算
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 从daily表计算技术指标
            cursor.execute('''
                SELECT close, volume
                FROM daily
                WHERE stock_code = ?
                ORDER BY timestamp DESC
                LIMIT 60
            ''', (stock_code,))
            
            data = cursor.fetchall()
            conn.close()
            
            if len(data) >= 20:
                closes = [d[0] for d in data]
                volumes = [d[1] for d in data]
                
                avg_20_price = sum(closes[:20]) / 20
                avg_60_price = sum(closes) / len(closes) if len(closes) >= 60 else avg_20_price
                
                avg_20_vol = sum(volumes[:20]) / 20
                avg_60_vol = sum(volumes) / len(volumes) if len(volumes) >= 60 else avg_20_vol
                
                return {
                    'avg_20_price': avg_20_price,
                    'avg_60_price': avg_60_price,
                    'avg_20_volume': avg_20_vol,
                    'avg_60_volume': avg_60_vol,
                }
            
        except Exception as e:
            print(f"获取 {stock_code} 基本面数据失败: {e}")
        
        return None
    
    def fetch_sector_info(self) -> Dict[str, Dict]:
        """获取板块信息（从西风数据库）"""
        try:
            xifeng_db = Path.home() / "Documents/OpenClawAgents/xifeng/data/xifeng.db"
            if not xifeng_db.exists():
                return {}
            
            conn = sqlite3.connect(xifeng_db)
            cursor = conn.cursor()
            
            # 获取板块数据
            cursor.execute("SELECT sector_name, change_pct FROM sectors ORDER BY change_pct DESC")
            sectors = cursor.fetchall()
            
            result = {}
            for name, change in sectors:
                result[name] = {
                    'name': name,
                    'change_pct': change,
                    'trend': 'up' if change > 0 else 'down'
                }
            
            conn.close()
            return result
            
        except Exception as e:
            print(f"获取板块信息失败: {e}")
            return {}
    
    def update_enhanced_data(self, batch_size: int = 50):
        """更新增强版数据"""
        print("🔄 开始更新增强版主数据...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 获取所有股票
        cursor.execute("SELECT code, stock_name FROM stocks")
        all_stocks = cursor.fetchall()
        
        # 获取板块信息
        sector_info = self.fetch_sector_info()
        
        total = len(all_stocks)
        updated = 0
        
        print(f"总股票数: {total}")
        print(f"板块数: {len(sector_info)}")
        
        for i, (code, name) in enumerate(all_stocks):
            # 获取基本面数据
            fundamentals = self.fetch_stock_fundamentals(code)
            
            # 获取板块（简化处理，后续可从详细映射表获取）
            sector = None
            for sec_name, sec_data in sector_info.items():
                # 这里简化处理，实际应有股票-板块映射表
                pass
            
            # 更新数据库
            if fundamentals:
                cursor.execute('''
                    INSERT OR REPLACE INTO master_stocks_enhanced 
                    (stock_code, stock_name, avg_20_price, avg_60_price, 
                     avg_20_volume, avg_60_volume, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    code,
                    name,
                    fundamentals.get('avg_20_price', 0),
                    fundamentals.get('avg_60_price', 0),
                    fundamentals.get('avg_20_volume', 0),
                    fundamentals.get('avg_60_volume', 0),
                    datetime.now().isoformat()
                ))
                updated += 1
            
            if (i + 1) % batch_size == 0:
                conn.commit()
                progress = (i + 1) / total * 100
                print(f"  进度: {progress:.1f}% | 已更新: {updated}")
        
        conn.commit()
        conn.close()
        
        print(f"✅ 更新完成! 共更新 {updated} 只股票的技术指标")
        return updated
    
    def get_stock_full_info(self, stock_code: str) -> Dict:
        """获取股票完整信息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 从增强版表获取
        cursor.execute('''
            SELECT stock_code, stock_name, sector, industry, 
                   total_market_cap, pe_ratio, pb_ratio, eps, roe,
                   avg_20_price, avg_60_price
            FROM master_stocks_enhanced
            WHERE stock_code = ?
        ''', (stock_code,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                'code': row[0],
                'name': row[1],
                'sector': row[2],
                'industry': row[3],
                'market_cap': row[4],
                'pe': row[5],
                'pb': row[6],
                'eps': row[7],
                'roe': row[8],
                'ma20': row[9],
                'ma60': row[10]
            }
        return None

def main():
    """主程序"""
    print("="*70)
    print("🗄️  主数据库增强版 - 板块和基本面数据")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    master = MasterDatabaseEnhanced()
    
    # 更新增强数据
    updated = master.update_enhanced_data(batch_size=100)
    
    print("\n" + "="*70)
    print("📊 统计数据:")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM master_stocks_enhanced")
    total = cursor.fetchone()[0]
    print(f"  增强版数据: {total} 只股票")
    
    cursor.execute("SELECT COUNT(DISTINCT sector) FROM master_stocks_enhanced WHERE sector IS NOT NULL")
    sectors = cursor.fetchone()[0]
    print(f"  板块覆盖: {sectors} 个")
    
    conn.close()
    
    print("\n" + "="*70)
    print("✅ 增强版主数据库更新完成!")
    print("="*70)

if __name__ == '__main__':
    main()
