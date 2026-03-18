#!/usr/bin/env python3
"""
红中信号生成器 V3.5 - 多策略版
为每个策略分别生成信号，分开显示
"""

import sqlite3
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from pathlib import Path
import sys
import importlib.util

sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger

log = get_logger("红中V3.5")

# 数据库路径
BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
HONGZHONG_DB = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"

# 邮件配置
EMAIL_CONFIG = {
    "sender": "3823810468@qq.com",
    "password": "tmwhuqnthrpbcgec",
    "smtp_server": "smtp.qq.com",
    "smtp_port": 587
}

# 信号等级
SIGNAL_LEVELS = {
    "强烈买入": {"emoji": "🚀", "score_min": 80},
    "买入": {"emoji": "📈", "score_min": 70},
    "积极关注": {"emoji": "👀", "score_min": 65}
}


def load_strategy_module():
    """加载策略模块"""
    spec = importlib.util.spec_from_file_location("nanfeng_v5_1", 
        str(Path(__file__).parent.parent / "nanfeng/nanfeng_v5_1.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def get_multi_strategy_signals():
    """获取多策略信号"""
    module = load_strategy_module()
    NanFengV5_1 = module.NanFengV5_1
    STRATEGIES = module.STRATEGIES
    
    all_signals = {}
    
    # 为每个策略生成信号
    for strategy_name in STRATEGIES.keys():
        log.info(f"📊 分析策略: {strategy_name}")
        
        # 创建策略实例
        strategy = NanFengV5_1(strategy_name=strategy_name)
        
        # 扫描股票
        signals = strategy.scan_signals(max_stocks=500)
        
        log.info(f"  {strategy_name}: 获取到{len(signals)}个信号")
        
        # 按信号等级分类
        level_signals = {"强烈买入": [], "买入": [], "积极关注": []}
        
        for s in signals:
            score = s.total_score
            
            # 判断信号等级
            if score >= 80:
                level = "强烈买入"
            elif score >= 70:
                level = "买入"
            else:
                continue
            
            # 格式化信号
            level_signals[level].append({
                'code': s.stock_code,
                'name': s.stock_name,
                'score': score,
                'strategy': strategy_name
            })
        
        all_signals[strategy_name] = level_signals
    
    return all_signals


def save_signals(all_signals):
    """保存信号到数据库"""
    conn = sqlite3.connect(str(HONGZHONG_DB))
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    saved = 0
    
    for strategy_name, level_signals in all_signals.items():
        for level, signals in level_signals.items():
            for s in signals:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO signals 
                        (timestamp, stock_code, stock_name, strategy, version,
                         entry_price, stop_loss, target_1, target_2, score, sent_discord)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                    """, (
                        today,
                        s['code'],
                        s['name'],
                        level,
                        f"南风V5.5-{strategy_name}",
                        0, 0, 0, 0,
                        s['score']
                    ))
                    saved += 1
                except Exception as e:
                    pass
    
    conn.commit()
    conn.close()
    log.success(f"保存了 {saved} 个信号")
    return saved


def format_multi_strategy_report(all_signals):
    """格式化多策略报告"""
    lines = ["=" * 60]
    lines.append(f"🎯 多策略信号报告 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 60)
    
    total_signals = 0
    
    for strategy_name, level_signals in all_signals.items():
        lines.append(f"\n📊 {strategy_name}")
        lines.append("-" * 40)
        
        for level in ["强烈买入", "买入", "积极关注"]:
            signals = level_signals.get(level, [])
            if signals:
                emoji = SIGNAL_LEVELS[level]["emoji"]
                lines.append(f"\n  {emoji} {level} ({len(signals)}只)")
                
                for s in signals[:5]:
                    lines.append(f"    • {s['code']} {s['name']} 评分:{s['score']:.0f}")
                
                total_signals += len(signals)
    
    lines.append(f"\n{'=' * 60}")
    lines.append(f"📈 总计: {total_signals} 个信号")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def send_notification(report):
    """发送通知"""
    # Discord
    try:
        from unified_notifier import notify_report
        notify_report("红中", report)
    except Exception as e:
        log.error(f"通知失败: {e}")


def run():
    """运行多策略信号生成"""
    print("=" * 60)
    print("🎯 红中信号生成器 V3.5 - 多策略版")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取多策略信号
    all_signals = get_multi_strategy_signals()
    
    if not all_signals:
        print("❌ 未生成有效信号")
        return
    
    # 显示报告
    report = format_multi_strategy_report(all_signals)
    print(report)
    
    # 保存到数据库
    save_signals(all_signals)
    
    # 发送通知
    send_notification(report)
    
    print("\n✅ 多策略信号生成完成!")


if __name__ == '__main__':
    run()
