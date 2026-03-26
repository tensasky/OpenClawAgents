#!/usr/bin/env python3
"""Python Manager - 常驻进程调度器"""

import time
import subprocess
import sys
import os
from datetime import datetime, datetime
import signal

# 添加路径
sys.path.insert(0, '/Users/roberto/Documents/OpenClawAgents/logs')

class ProcessManager:
    def __init__(self):
        self.running = True
        self.agents = {
            'caishen': {'script': '/Users/roberto/Documents/OpenClawAgents/manager/caishen_manager.py', 'interval': 300},
            'beifeng': {'script': '/Users/roberto/Documents/OpenClawAgents/beifeng/beifeng.py', 'interval': 300},
            'dongfeng': {'script': '/Users/roberto/Documents/OpenClawAgents/dongfeng/dongfeng_v2.py', 'interval': 600},
            'hongzhong': {'script': '/Users/roberto/Documents/OpenClawAgents/logs/quick_scan.py', 'interval': 300},
            'facai': {'script': '/Users/roberto/Documents/OpenClawAgents/facai/trading_loop.py', 'interval': 600},
        }
        
        self.last_run = {name: 0 for name in self.agents}
        
        # 信号处理
        signal.signal(signal.SIGINT, self.stop)
        signal.signal(signal.SIGTERM, self.stop)
    
    def stop(self, signum, frame):
        print("\n🛑 收到停止信号...")
        self.running = False
    
    def should_run(self, name):
        """检查是否应该运行"""
        now = time.time()
        interval = self.agents[name]['interval']
        
        if now - self.last_run[name] >= interval:
            return True
        return False
    
    def run_agent(self, name):
        """运行Agent"""
        script = self.agents[name]['script']
        
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🚀 启动 {name}")
        
        try:
            # 根据是否带参数决定
            if 'quick_scan' in script:
                result = subprocess.run(
                    ['python3', script],
                    capture_output=True,
                    text=True,
                    timeout=180
                )
            else:
                result = subprocess.run(
                    ['python3', script],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
            
            if result.returncode == 0:
                print(f"✅ {name} 完成")
            else:
                print(f"❌ {name} 失败: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {name} 超时")
        except Exception as e:
            print(f"❌ {name} 异常: {e}")
        
        self.last_run[name] = time.time()
    
    def check_health(self):
        """健康检查"""
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 健康检查")
        
        # 检查必要进程
        import sqlite3
        
        conn = sqlite3.connect('/Users/roberto/Documents/OpenClawAgents/beifeng/data/stocks_real.db')
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM minute WHERE timestamp LIKE '2026-03-27%'")
        minute_count = cursor.fetchone()[0]
        conn.close()
        
        print(f"  分钟数据: {minute_count}条")
        
        return minute_count > 0
    
    def run(self):
        """主循环"""
        print("="*60)
        print("⚡ Process Manager - 常驻调度器")
        print("="*60)
        print(f"启动时间: {datetime.now()}")
        print(f"监控Agent: {len(self.agents)}个")
        print("="*60)
        
        while self.running:
            try:
                now = datetime.now()
                
                # 交易时段 (09:30-15:00)
                if 9 <= now.hour < 15:
                    # 检查并运行需要执行的Agent
                    for name in self.agents:
                        if self.should_run(name):
                            self.run_agent(name)
                else:
                    # 非交易时段，降低频率
                    if now.hour == 9 and now.minute < 30:
                        pass
                    else:
                        print(f"\n⏰ {now.strftime('%H:%M')} 非交易时段，休眠中...")
                
                # 健康检查 (每小时)
                if now.minute == 0:
                    self.check_health()
                
                time.sleep(30)  # 每30秒检查一次
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ 异常: {e}")
                time.sleep(10)
        
        print("\n🛑 Manager已停止")

if __name__ == "__main__":
    ProcessManager().run()
