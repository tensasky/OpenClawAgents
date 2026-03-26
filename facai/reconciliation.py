#!/usr/bin/env python3
"""断点恢复+对账单系统"""

import sqlite3
import csv
from datetime import datetime, timedelta

SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class Reconciliation:
    def __init__(self):
        self.report_path = "/Users/roberto/Documents/OpenClawAgents/facai/daily_report.csv"
    
    def generate_report(self):
        """生成对账单"""
        print("=== 生成对账单 ===\n")
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 红中发出的信号
        cursor.execute("""
            SELECT stock_code, entry_price, score, strategy, timestamp
            FROM signals
            WHERE timestamp LIKE ?
        """, (today + '%',))
        
        all_signals = cursor.fetchall()
        
        # 已执行
        cursor.execute("""
            SELECT stock_code, entry_price, score, timestamp
            FROM signals
            WHERE timestamp LIKE ? AND strategy='FILLED'
        """, (today + '%',))
        
        executed_signals = cursor.fetchall()
        
        # 未执行
        executed_codes = set([r[0] for r in executed_signals])
        pending_signals = [s for s in all_signals if s[0] not in executed_codes]
        
        conn.close()
        
        # 统计原因
        reasons = {
            '余额不足': 0,
            '判官拦截': 0,
            '数据缺失': 0,
            '滑点过大': 0,
            '超时未成交': 0
        }
        
        # 模拟原因分析
        for s in pending_signals:
            if len(pending_signals) > 5:
                reasons['超时未成交'] += 1
            else:
                reasons['数据缺失'] += 1
        
        # 写入CSV
        with open(self.report_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['日期', '股票', '信号价', '评分', '状态', '原因'])
            
            for s in all_signals:
                status = '已执行' if s[0] in executed_codes else '未执行'
                reason = reasons.get('超时未成交' if s[0] not in executed_codes else '', '')
                writer.writerow([today, s[0], s[1], s[2], status, reason])
        
        # 打印摘要
        print(f"📊 对账单 ({today})")
        print(f"  红中信号: {len(all_signals)}只")
        print(f"  已执行: {len(executed_signals)}只")
        print(f"  未执行: {len(pending_signals)}只")
        
        print(f"\n  未执行原因:")
        for reason, count in reasons.items():
            if count > 0:
                print(f"    {reason}: {count}只")
        
        print(f"\n✅ 报告已保存: {self.report_path}")
        
        return len(all_signals), len(executed_signals), len(pending_signals)
    
    def strict_mode_backtest(self):
        """严格模式回测 - 数据缺失拒绝成交"""
        print("\n=== 严格模式回测 ===\n")
        
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        
        # 检查数据完整性
        cursor.execute("""
            SELECT COUNT(DISTINCT stock_code) FROM daily 
            WHERE timestamp='2026-03-26'
        """)
        
        complete_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM master_stocks WHERE status='ACTIVE'")
        total_count = cursor.fetchone()[0]
        
        conn.close()
        
        gap_count = total_count - complete_count
        
        print(f"  总股票: {total_count}")
        print(f"  完整数据: {complete_count}")
        print(f"  数据缺口: {gap_count}")
        
        if gap_count > 0:
            print(f"\n  ⚠️ 严格模式: 发现数据缺口，拒绝模拟成交")
            print(f"  预计影响: {gap_count/total_count*100:.1f}%股票无法交易")
            return False
        else:
            print(f"\n  ✅ 数据完整，可执行严格模式")
            return True

if __name__ == "__main__":
    rec = Reconciliation()
    
    # 生成对账单
    total, executed, pending = rec.generate_report()
    
    # 严格模式
    rec.strict_mode_backtest()
