#!/usr/bin/env python3
"""
北风 - 补充近30天分钟级数据
只抓核心100只，避免数据量过大
"""

import json
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
BATCH_SIZE = 2  # 分钟数据量大，每批2只
DELAY = 3  # 延迟3秒

def load_core_stocks():
    """加载核心100只股票"""
    with open(WORKSPACE / "data" / "core100_stocks.json") as f:
        return json.load(f)

def fetch_minute_batch(stock_codes):
    """抓取一批股票的分钟数据"""
    codes_str = " ".join(stock_codes)
    # 使用 minute 类型
    cmd = f"cd {WORKSPACE} && python3 beifeng.py {codes_str} --type minute"
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=600
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout after 600s"
    except Exception as e:
        return False, str(e)

def main():
    print("🌪️ 北风分钟数据补全启动")
    print("=" * 60)
    
    stocks = load_core_stocks()
    stock_codes = [s['code'] for s in stocks]
    total = len(stock_codes)
    
    print(f"📊 目标: {total} 只核心股票")
    print(f"📈 数据: 近30天分钟线")
    print(f"⏱️  预计: {total * 2} 分钟")
    print("=" * 60)
    
    success_count = 0
    fail_count = 0
    
    for i in range(0, total, BATCH_SIZE):
        batch = stock_codes[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        
        print(f"\n[{batch_num}/{total_batches}] {', '.join(batch)}")
        
        success, output = fetch_minute_batch(batch)
        
        if success:
            success_count += len(batch)
            print(f"  ✅ 成功")
        else:
            fail_count += len(batch)
            print(f"  ❌ 失败")
            # 记录失败
            with open(WORKSPACE / "logs" / "minute_failed.log", 'a') as f:
                f.write(f"{datetime.now()}: {batch}\n")
        
        if i + BATCH_SIZE < total:
            time.sleep(DELAY)
    
    print("\n" + "=" * 60)
    print(f"✅ 完成!")
    print(f"  成功: {success_count}/{total}")
    print(f"  失败: {fail_count}")

if __name__ == '__main__':
    main()
