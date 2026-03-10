#!/usr/bin/env python3
"""
daily_report.py - 每日8点三Agent工作汇报
汇报北风、西风、南风的工作状态
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, '/Users/roberto/.openclaw/agents/beifeng')

BEIFENG_DB = Path("/Users/roberto/.openclaw/agents/beifeng/data/stocks_v2.db")
XIFENG_DATA = Path("/Users/roberto/Documents/OpenClawAgents/xifeng/data/hot_spots.json")
REPORT_FILE = Path("/Users/roberto/Documents/OpenClawAgents/logs/daily_report.txt")

def check_beifeng():
    """检查北风状态"""
    conn = sqlite3.connect(BEIFENG_DB)
    cursor = conn.cursor()
    
    # 数据统计
    cursor.execute("SELECT data_type, COUNT(*), COUNT(DISTINCT stock_code) FROM kline_data GROUP BY data_type")
    stats = {row[0]: {'records': row[1], 'stocks': row[2]} for row in cursor.fetchall()}
    
    # 最新数据日期
    cursor.execute("SELECT MAX(timestamp) FROM kline_data WHERE data_type='daily'")
    latest_daily = cursor.fetchone()[0]
    
    cursor.execute("SELECT MAX(timestamp) FROM kline_data WHERE data_type='1min'")
    latest_minute = cursor.fetchone()[0]
    
    conn.close()
    
    daily_count = stats.get('daily', {}).get('stocks', 0)
    minute_count = stats.get('1min', {}).get('stocks', 0)
    
    return {
        'daily_coverage': f"{daily_count}/5815 ({daily_count/5815*100:.1f}%)",
        'minute_coverage': f"{minute_count}/5815 ({minute_count/5815*100:.1f}%)",
        'latest_daily': latest_daily,
        'latest_minute': latest_minute,
        'status': '✅ 正常' if daily_count > 5000 else '⚠️ 需补全'
    }

def check_xifeng():
    """检查西风状态"""
    try:
        with open(XIFENG_DATA, 'r') as f:
            data = json.load(f)
        
        generated = data.get('generated_at', '未知')
        total_sectors = data.get('total_sectors', 0)
        hot_spots = data.get('hot_spots', [])
        
        # 检查是否今日更新
        gen_time = datetime.fromisoformat(generated.replace('Z', '+00:00'))
        is_today = gen_time.date() == datetime.now().date()
        
        return {
            'last_update': generated,
            'total_sectors': total_sectors,
            'hot_spots_count': len(hot_spots),
            'top_sector': hot_spots[0]['sector'] if hot_spots else '无',
            'status': '✅ 今日已更新' if is_today else '⚠️ 今日未更新'
        }
    except Exception as e:
        return {'status': f'❌ 错误: {e}'}

def check_nanfeng():
    """检查南风状态"""
    signals_dir = Path("/Users/roberto/Documents/OpenClawAgents/nanfeng/signals")
    
    if not signals_dir.exists():
        return {'status': '⚠️ 无信号目录'}
    
    # 查找今日信号文件
    today_str = datetime.now().strftime('%Y%m%d')
    signal_files = list(signals_dir.glob(f'signals_{today_str}*.json'))
    
    if signal_files:
        latest = max(signal_files, key=lambda x: x.stat().st_mtime)
        try:
            with open(latest, 'r') as f:
                data = json.load(f)
            return {
                'today_signals': data.get('total_signals', 0),
                'high_confidence': len(data.get('high_confidence', [])),
                'latest_file': latest.name,
                'status': '✅ 今日已扫描'
            }
        except:
            return {'status': '⚠️ 信号文件读取失败'}
    
    return {'status': '⏸️ 今日未扫描'}

def generate_report():
    """生成汇报"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    beifeng = check_beifeng()
    xifeng = check_xifeng()
    nanfeng = check_nanfeng()
    
    report = f"""
{'='*60}
🌪️ 三Agent每日工作汇报 - {now}
{'='*60}

【北风 - 股票数据采集】
  状态: {beifeng['status']}
  日线覆盖: {beifeng['daily_coverage']}
  分钟覆盖: {beifeng['minute_coverage']}
  最新日线: {beifeng['latest_daily']}
  最新分钟: {beifeng['latest_minute']}

【西风 - 舆情分析】
  状态: {xifeng['status']}
  最后更新: {xifeng.get('last_update', 'N/A')}
  热点板块: {xifeng.get('hot_spots_count', 0)}个
  最热板块: {xifeng.get('top_sector', 'N/A')}

【南风 - 量化交易】
  状态: {nanfeng['status']}
  今日信号: {nanfeng.get('today_signals', 0)}个
  高置信度: {nanfeng.get('high_confidence', 0)}个

{'='*60}
"""
    
    # 保存到文件
    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, 'w') as f:
        f.write(report)
    
    return report

if __name__ == '__main__':
    report = generate_report()
    print(report)
