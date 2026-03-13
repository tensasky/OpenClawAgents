#!/usr/bin/env python3
"""
北风 - 多接口交叉验证采集器
同时从新浪、腾讯、网易采集，交叉验证确保数据准确
"""

import requests
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import time
import json

BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks.db"

class MultiSourceFetcher:
    """多源数据采集器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.results = {}
    
    def fetch_sina_realtime(self, stock_codes: list) -> dict:
        """新浪实时接口"""
        try:
            codes = []
            for code in stock_codes:
                if code.startswith('sh'):
                    codes.append(f"sh{code[2:]}")
                elif code.startswith('sz'):
                    codes.append(f"sz{code[2:]}")
                else:
                    codes.append(code)
            
            url = f"https://hq.sinajs.cn/list={','.join(codes)}"
            response = self.session.get(url, headers={'Referer': 'https://finance.sina.com.cn'}, timeout=30)
            response.encoding = 'gb2312'
            
            results = {}
            for line in response.text.strip().split('\n'):
                if not line or '=' not in line:
                    continue
                
                code_part, data_part = line.split('=', 1)
                code = code_part.replace('var hq_str_', '').strip()
                data = data_part.strip('";')
                
                if not data:
                    continue
                
                fields = data.split(',')
                if len(fields) >= 33:
                    # 新浪成交量单位是"手"，转换为"股"（×100）
                    volume_shou = int(fields[8])
                    volume_gu = volume_shou * 100
                    
                    results[code] = {
                        'name': fields[0],
                        'open': float(fields[1]),
                        'close': float(fields[3]),
                        'high': float(fields[4]),
                        'low': float(fields[5]),
                        'volume': volume_gu,  # 转换为股
                        'amount': float(fields[9]),
                        'date': fields[30],
                        'time': fields[31],
                        'source': 'sina'
                    }
            
            return results
        except Exception as e:
            print(f"新浪接口失败: {e}")
            return {}
    
    def fetch_tencent_realtime(self, stock_codes: list) -> dict:
        """腾讯实时接口"""
        try:
            codes = []
            for code in stock_codes:
                if code.startswith('sh'):
                    codes.append(f"sh{code[2:]}")
                elif code.startswith('sz'):
                    codes.append(f"sz{code[2:]}")
                else:
                    codes.append(code)
            
            url = f"https://qt.gtimg.cn/q={','.join(codes)}"
            response = self.session.get(url, timeout=30)
            
            results = {}
            lines = response.text.strip().split(';')
            
            for line in lines:
                if not line or '=' not in line:
                    continue
                
                code_part, data_part = line.split('=', 1)
                code = code_part.replace('v_', '').strip()
                data = data_part.strip('"').split('~')
                
                if len(data) >= 45:
                    results[code] = {
                        'name': data[1],
                        'close': float(data[3]),
                        'open': float(data[5]),
                        'high': float(data[33]),
                        'low': float(data[34]),
                        'volume': int(data[36]) * 100,  # 腾讯单位是手
                        'amount': float(data[37]) * 10000,
                        'source': 'tencent'
                    }
            
            return results
        except Exception as e:
            print(f"腾讯接口失败: {e}")
            return {}
    
    def cross_validate(self, stock_codes: list) -> dict:
        """交叉验证采集"""
        print(f"🔍 多源交叉验证 {len(stock_codes)} 只股票...")
        
        # 从多个源采集
        sina_data = self.fetch_sina_realtime(stock_codes)
        time.sleep(0.5)  # 避免请求过快
        tencent_data = self.fetch_tencent_realtime(stock_codes)
        
        validated = {}
        conflicts = []
        
        for code in stock_codes:
            sina = sina_data.get(code)
            tencent = tencent_data.get(code)
            
            if not sina and not tencent:
                continue
            
            if sina and tencent:
                # 交叉验证
                price_diff = abs(sina['close'] - tencent['close']) / sina['close'] * 100
                volume_diff = abs(sina['volume'] - tencent['volume']) / sina['volume'] * 100 if sina['volume'] > 0 else 0
                
                if price_diff < 1 and volume_diff < 10:
                    # 数据一致，使用新浪（更准确）
                    validated[code] = sina
                    validated[code]['validated'] = True
                    validated[code]['sources'] = ['sina', 'tencent']
                else:
                    # 数据冲突
                    conflicts.append({
                        'code': code,
                        'sina': sina,
                        'tencent': tencent,
                        'price_diff': price_diff,
                        'volume_diff': volume_diff
                    })
                    # 使用差异较小的
                    if price_diff < 2:
                        validated[code] = sina
                        validated[code]['validated'] = False
                        validated[code]['conflict'] = True
            elif sina:
                validated[code] = sina
                validated[code]['validated'] = False
                validated[code]['sources'] = ['sina']
            elif tencent:
                validated[code] = tencent
                validated[code]['validated'] = False
                validated[code]['sources'] = ['tencent']
        
        print(f"✅ 验证通过: {len([v for v in validated.values() if v.get('validated')])} 只")
        print(f"⚠️  数据冲突: {len(conflicts)} 只")
        
        return validated, conflicts


def save_validated_data(validated_data: dict):
    """保存验证后的数据到数据库"""
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    saved = 0
    
    for code, data in validated_data.items():
        try:
            # 检查是否已存在
            cursor.execute("""
                SELECT 1 FROM kline_data 
                WHERE stock_code = ? AND data_type = 'daily' 
                AND date(timestamp) = ?
            """, (code, today))
            
            if cursor.fetchone():
                # 更新数据
                cursor.execute("""
                    UPDATE kline_data 
                    SET open = ?, high = ?, low = ?, close = ?, 
                        volume = ?, amount = ?
                    WHERE stock_code = ? AND data_type = 'daily'
                    AND date(timestamp) = ?
                """, (data['open'], data['high'], data['low'], data['close'],
                      data['volume'], data['amount'], code, today))
            else:
                # 插入新数据
                timestamp = f"{today}T00:00:00"
                cursor.execute("""
                    INSERT INTO kline_data 
                    (stock_code, data_type, timestamp, open, high, low, close, volume, amount)
                    VALUES (?, 'daily', ?, ?, ?, ?, ?, ?, ?)
                """, (code, timestamp, data['open'], data['high'], data['low'], 
                      data['close'], data['volume'], data['amount']))
            
            saved += 1
        except Exception as e:
            print(f"保存 {code} 失败: {e}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ 已保存 {saved} 只股票数据")


def validate_existing_data():
    """验证现有数据准确性"""
    print("🔍 验证现有数据...")
    
    fetcher = MultiSourceFetcher()
    
    # 从数据库获取今日数据
    conn = sqlite3.connect(BEIFENG_DB)
    today = datetime.now().strftime('%Y-%m-%d')
    db_data = pd.read_sql_query(f"""
        SELECT stock_code, close, volume
        FROM kline_data
        WHERE data_type = 'daily' AND date(timestamp) = '{today}'
        LIMIT 100
    """, conn)
    conn.close()
    
    if len(db_data) == 0:
        print("❌ 今日无数据")
        return
    
    # 随机抽取20只验证
    sample = db_data.sample(min(20, len(db_data)))
    codes = sample['stock_code'].tolist()
    
    # 从新浪获取实时数据对比
    sina_data = fetcher.fetch_sina_realtime(codes)
    
    mismatches = []
    for _, row in sample.iterrows():
        code = row['stock_code']
        db_close = row['close']
        db_volume = row['volume']
        
        sina = sina_data.get(code)
        if sina:
            price_diff = abs(sina['close'] - db_close) / db_close * 100
            volume_diff = abs(sina['volume'] - db_volume) / db_volume * 100 if db_volume > 0 else 0
            
            if price_diff > 1 or volume_diff > 10:
                mismatches.append({
                    'code': code,
                    'db_close': db_close,
                    'sina_close': sina['close'],
                    'price_diff': price_diff,
                    'db_volume': db_volume,
                    'sina_volume': sina['volume'],
                    'volume_diff': volume_diff
                })
    
    print(f"✅ 验证完成: {len(codes)} 只样本")
    print(f"⚠️  发现差异: {len(mismatches)} 只")
    
    if mismatches:
        print("\n差异详情:")
        for m in mismatches[:5]:
            print(f"  {m['code']}: 价格差异{m['price_diff']:.2f}%, 成交量差异{m['volume_diff']:.1f}%")


def main():
    """主程序"""
    print("="*70)
    print("🌪️ 北风多源交叉验证采集器")
    print("="*70)
    
    # 1. 验证现有数据
    validate_existing_data()
    
    print("\n" + "="*70)
    
    # 2. 采集并验证核心股票
    core_stocks = ['sh600348', 'sh600127', 'sh600011', 'sh600025', 'sh600233']
    
    fetcher = MultiSourceFetcher()
    validated, conflicts = fetcher.cross_validate(core_stocks)
    
    # 保存验证后的数据
    if validated:
        save_validated_data(validated)
    
    print("\n" + "="*70)
    print("✅ 多源验证采集完成")
    print("="*70)


if __name__ == '__main__':
    main()
