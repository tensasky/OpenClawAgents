#!/usr/bin/env python3
"""
北风 - 批量初始化所有 A 股数据
"""

import json
import subprocess
import sys
from pathlib import Path
import time
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")


WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
BATCH_SIZE = 5  # 每批处理5只，避免请求过快

def load_stocks():
    """加载股票列表"""
    with open(WORKSPACE / "data" / "all_stocks.json") as f:
        return json.load(f)

def fetch_batch(stock_codes):
    """抓取一批股票"""
    codes_str = " ".join(stock_codes)
    cmd = f"cd {WORKSPACE} && python3 beifeng.py {codes_str} --type daily"
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=180
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout"
    except Exception as e:
        return False, str(e)

def main():
    stocks = load_stocks()
    total = len(stocks)
    
    log.info(f"🌪️ 北风批量初始化")
    log.info(f"📊 共 {total} 只股票")
    log.info("=" * 50)
    
    # 提取股票代码
    stock_codes = [s['code'] for s in stocks]
    
    # 分批处理
    success_count = 0
    fail_count = 0
    failed_stocks = []
    
    for i in range(0, total, BATCH_SIZE):
        batch = stock_codes[i:i+BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        
        log.info(f"\n[{batch_num}/{total_batches}] 处理: {', '.join(batch)}")
        
        success, output = fetch_batch(batch)
        
        if success:
            log.info(f"  ✅ 成功")
            success_count += len(batch)
        else:
            log.info(f"  ❌ 失败")
            fail_count += len(batch)
            failed_stocks.extend(batch)
        
        # 短暂休息，避免请求过快
        time.sleep(1)
    
    log.info("\n" + "=" * 50)
    log.info(f"✅ 成功: {success_count} 只")
    log.info(f"❌ 失败: {fail_count} 只")
    
    if failed_stocks:
        log.info(f"\n失败的股票:")
        for code in failed_stocks:
            log.info(f"  - {code}")
        
        # 保存失败列表供后续重试
        with open(WORKSPACE / "data" / "failed_stocks.txt", "w") as f:
            f.write("\n".join(failed_stocks))
        log.info(f"\n已保存到 failed_stocks.txt，可后续重试")

if __name__ == '__main__':
    main()
