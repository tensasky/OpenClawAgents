#!/usr/bin/env python3
"""
全A股批量采集 - 健壮性版本
使用ResilientFetcher确保高可用性
"""

import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/beifeng')

from resilient_fetcher import ResilientFetcher, FetchTask
from datetime import datetime
import sqlite3
from pathlib import Path

DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

def get_all_stocks():
    """获取所有股票代码"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT code FROM stocks ORDER BY code")
    stocks = [row[0] for row in cursor.fetchall()]
    conn.close()
    return stocks

def batch_fetch_all():
    """批量采集所有股票（健壮性版本）"""
    print("="*70)
    print("🚀 全A股批量采集 - 健壮性版本")
    print("="*70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # 初始化健壮性采集器
    fetcher = ResilientFetcher()
    
    # 获取股票列表
    stocks = get_all_stocks()
    total = len(stocks)
    
    print(f"📊 总股票数: {total}")
    print(f"并发限制: {fetcher.scheduler.max_concurrent}")
    print(f"断路器保护: 腾讯/新浪/备用")
    print(f"重试机制: 指数退避，最大3次")
    print("="*70)
    
    success_count = 0
    failed_count = 0
    cached_count = 0
    
    # 分批提交任务
    batch_size = 100
    batches = (total + batch_size - 1) // batch_size
    
    for i in range(0, total, batch_size):
        batch_num = i // batch_size + 1
        batch = stocks[i:i+batch_size]
        
        print(f"\n📦 批次 {batch_num}/{batches} ({len(batch)}只股票)")
        
        # 提交批次任务
        for stock in batch:
            result = fetcher.fetch_stock(stock, priority=2)
            
            if result:
                if result.get('source') == 'cache':
                    cached_count += 1
                else:
                    success_count += 1
            else:
                failed_count += 1
        
        # 显示进度
        progress = min(100, (batch_num / batches) * 100)
        print(f"  进度: {progress:.1f}% | 成功:{success_count} 缓存:{cached_count} 失败:{failed_count}")
        
        # 处理重试队列
        fetcher.process_retry_queue()
    
    # 最终统计
    print("\n" + "="*70)
    print("✅ 采集完成！")
    print("="*70)
    
    stats = fetcher.get_stats()
    print(f"\n📊 最终结果:")
    print(f"  直接成功: {stats['success']} 只")
    print(f"  缓存数据: {stats['cached']} 只")
    print(f"  彻底失败: {stats['failed']} 只")
    print(f"  加入重试: {stats['retried']} 只")
    print(f"  重试队列: {stats['retry_queue']['pending']} 只待处理")
    
    # 成功率
    success_rate = (success_count + cached_count) / total * 100 if total > 0 else 0
    print(f"\n  成功率: {success_rate:.1f}%")
    
    print("\n💡 说明:")
    print("  • 失败的任务已自动加入重试队列")
    print("  • 5分钟后会自动重试（指数退避）")
    print("  • 断路器会在数据源恢复后自动闭合")
    print("="*70)

if __name__ == '__main__':
    batch_fetch_all()
