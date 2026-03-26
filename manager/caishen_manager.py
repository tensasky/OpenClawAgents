#!/usr/bin/env python3
"""财神爷 Manager - 三层调度架构"""

from datetime import datetime
import sqlite3
import sys
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')

STOCKS_DB = "/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db"
SIGNALS_DB = "/Users/roberto/Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

class CaishenManager:
    def __init__(self):
        self.mode = "NORMAL"
    
    def layer1(self):
        """第一层: 环境感知"""
        print("="*50)
        print("📡 第一层: 环境感知")
        print("="*50)
        
        conn = sqlite3.connect(STOCKS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT close FROM daily WHERE stock_code='sh000300' AND timestamp < '2026-03-26' ORDER BY timestamp DESC LIMIT 20")
        prices = [r[0] for r in cursor.fetchall()]
        conn.close()
        
        if len(prices) >= 20:
            ma20 = sum(prices[:20]) / 20
            current = prices[0]
            is_bull = current > ma20
            self.mode = "DEFENSE" if not is_bull else "NORMAL"
            
            print(f"沪深300: {current:.2f} vs MA20:{ma20:.2f}")
            print(f"模式: {'🐻 防御' if self.mode=='DEFENSE' else '🐂 正常'}")
        
        return self.mode
    
    def layer2(self):
        """第二层: 实时流水线"""
        print("\n" + "="*50)
        print("⚡ 第二层: 实时流水线")
        print("="*50)
        
        steps = [
            ("北风", "抓取"),
            ("东风", "筛选"),
            ("红中", "评分"),
            ("判官", "验证"),
            ("发财", "交易")
        ]
        
        for agent, action in steps:
            print(f"  {agent}: {action}")
        
        return {"status": "OK"}
    
    def layer3(self):
        """第三层: 闭环反馈"""
        print("\n" + "="*50)
        print("🔄 第三层: 闭环反馈")
        print("="*50)
        
        conn = sqlite3.connect(SIGNALS_DB)
        cursor = conn.cursor()
        cursor.execute("SELECT strategy, COUNT(*) FROM signals WHERE timestamp >= date('now') GROUP BY strategy")
        
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}只")
        
        conn.close()
        
        return {"audit": "OK"}
    
    def run(self):
        now = datetime.now()
        
        print("="*50)
        print("💰 财神爷 Manager")
        print(f"时间: {now.strftime('%H:%M')}")
        print("="*50)
        
        if 9 <= now.hour < 9.5:
            self.layer1()
        elif 9.5 <= now.hour < 15:
            self.layer2()
        else:
            self.layer3()

if __name__ == "__main__":
    CaishenManager().run()
