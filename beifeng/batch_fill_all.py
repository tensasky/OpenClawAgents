#!/usr/bin/env python3
"""
北风 - 全量A股数据补全
后台运行，逐步补全所有股票
"""

import json
import subprocess
import time
import sqlite3
from datetime import datetime
from pathlib import Path

WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"
BATCH_SIZE = 3  # 每批3只，避免请求过快
DELAY_BETWEEN_BATCHES = 5  # 批次间隔5秒

def get_pending_stocks():
    """获取待补全的股票列表"""
    
    # 读取所有股票
    with open(WORKSPACE / "data" / "all_stocks.json") as f:
        all_stocks = json.load(f)
    
    # 查询已完成的股票
    conn = sqlite3.connect(WORKSPACE / "data" / "stocks_real.db")
    cursor = conn.execute(
        "SELECT DISTINCT stock_code FROM kline_data GROUP BY stock_code HAVING COUNT(*) >= 100"
    )
    completed = {row[0] for row in cursor.fetchall()}
    conn.close()
    
    # 筛选未完成的
    pending = [s for s in all_stocks if s['code'] not in completed]
    return pending

def fetch_batch(stock_codes):
    """抓取一批股票"""
    codes_str = " ".join(stock_codes)
    cmd = f"cd {WORKSPACE} && python3 beifeng.py {codes_str} --type daily"
    
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=300
        )
        return result.returncode == 0, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout after 300s"
    except Exception as e:
        return False, str(e)

def log_progress(current, total, success, failed):
    """记录进度"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    progress = (current / total) * 100 if total > 0 else 0
    msg = f"[{timestamp}] 进度: {current}/{total} ({progress:.1f}%) | 成功: {success} | 失败: {failed}"
    
    log_file = WORKSPACE / "logs" / "batch_progress.log"
    with open(log_file, 'a') as f:
        f.write(msg + "\n")
    
    print(msg)

def main():
    log.info("🌪️ 北风全量A股数据补全启动")
    log.info("=" * 60)
    
    # 获取待补全股票
    pending = get_pending_stocks()
    total = len(pending)
    
    if total == 0:
        log.info("✅ 所有股票数据已完整！")
        return
    
    log.info(f"📊 待补全股票: {total} 只")
    log.info(f"⏱️  预计时间: {total * 2 // 60} 小时")
    log.info("=" * 60)
    
    # 提取代码
    stock_codes = [s['code'] for s in pending]
    
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
            success_count += len(batch)
            log.info(f"  ✅ 成功")
        else:
            fail_count += len(batch)
            failed_stocks.extend(batch)
            log.info(f"  ❌ 失败")
            # 保存失败记录
            with open(WORKSPACE / "logs" / "failed_batches.log", 'a') as f:
                f.write(f"{datetime.now()}: {batch} - {output[:200]}\n")
        
        # 记录进度
        log_progress(batch_num, total_batches, success_count, fail_count)
        
        # 休息避免请求过快
        if i + BATCH_SIZE < total:
            time.sleep(DELAY_BETWEEN_BATCHES)
    
    log.info("\n" + "=" * 60)
    log.info(f"✅ 补全完成!")
    log.info(f"  成功: {success_count}/{total}")
    log.info(f"  失败: {fail_count}")
    
    if failed_stocks:
        log.info(f"\n失败的股票 ({len(failed_stocks)} 只):")
        for code in failed_stocks[:20]:
            log.info(f"  - {code}")
        if len(failed_stocks) > 20:
            log.info(f"  ... 还有 {len(failed_stocks) - 20} 只")
        
        # 保存失败列表
        with open(WORKSPACE / "data" / "failed_stocks_retry.json", 'w') as f:
            json.dump(failed_stocks, f)
    
    # 发送Discord通知
    try:
        from discord_notify import send_discord_message
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("北风")

        content = f"""
🌪️ **北风全量补全完成**

✅ **结果统计**
• 总股票: {total} 只
• 成功: {success_count} 只
• 失败: {fail_count} 只
• 完成率: {((success_count/total)*100):.1f}%

⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        send_discord_message(content, "🌪️ 北风全量补全完成", 0x00ff00)
    except Exception as e:
        log.info(f"Discord通知失败: {e}")

if __name__ == '__main__':
    main()
