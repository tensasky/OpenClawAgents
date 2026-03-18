#!/usr/bin/env python3
"""
全面代码审核 - 所有Agent健康检查
财神爷主导，确保每个Agent正常
"""

import os
import re
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/ "utils"))
from agent_logger import get_logger

log = get_logger("System")


class AgentAuditor:
    """Agent审核器"""
    
    def __init__(self):
        self.base_path = Path.home() / "Documents/OpenClawAgents"
        self.issues = []
        self.critical_issues = []
        
    def audit_all(self):
        """审核所有Agent"""
        log.info("="*80)
        log.info("🔍 全面Agent审核 - 财神爷主导")
        log.info("="*80)
        log.info(f"审核时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. 北风审核
        self.audit_beifeng()
        
        # 2. 南风审核
        self.audit_nanfeng()
        
        # 3. 红中审核
        self.audit_hongzhong()
        
        # 4. 西风审核
        self.audit_xifeng()
        
        # 5. 发财审核
        self.audit_facai()
        
        # 6. 白板审核
        self.audit_baiban()
        
        # 7. 财神爷自审
        self.audit_caishen()
        
        # 输出总结
        self.print_summary()
    
    def audit_beifeng(self):
        """审核北风 - 数据准确性"""
        log.info("\n" + "="*80)
        log.info("🌪️ 北风审核 - 数据采集")
        log.info("="*80)
        
        # 检查数据库路径
        old_db = self.base_path / "beifeng/data/stocks.db"
        new_db = self.base_path / "beifeng/data/stocks_real.db"
        
        if old_db.exists():
            self.critical_issues.append("北风: 旧数据库stocks.db仍存在，可能还在使用")
            log.info("❌ 旧数据库仍存在")
        
        # 检查代码引用
        result = subprocess.run(
            ['grep', '-r', 'stocks.db', '--include=*.py', 'beifeng/'],
            capture_output=True, text=True, cwd=self.base_path
        )
        if result.stdout:
            count = len(result.stdout.strip().split('\n'))
            self.critical_issues.append(f"北风: {count}处代码引用旧数据库")
            log.info(f"❌ {count}处引用旧数据库")
        else:
            log.info("✅ 无旧数据库引用")
        
        # 检查数据一致性
        if new_db.exists():
            conn = sqlite3.connect(new_db)
            cursor = conn.cursor()
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            # 检查日线和分钟差异
            cursor.execute(f"""
                SELECT d.stock_code, d.close as daily_close,
                       (SELECT close FROM minute m 
                        WHERE m.stock_code = d.stock_code 
                        AND date(m.timestamp) = '{today}'
                        ORDER BY m.timestamp DESC LIMIT 1) as minute_close
                FROM daily d
                WHERE date(d.timestamp) = '{today}'
                LIMIT 5
            """)
            
            mismatches = []
            for row in cursor.fetchall():
                code, d_close, m_close = row
                if m_close and abs(d_close - m_close) > 0.5:
                    mismatches.append(f"{code}: 日线{d_close} vs 分钟{m_close}")
            
            if mismatches:
                self.critical_issues.append(f"北风: {len(mismatches)}只股票日线分钟不一致")
                log.info(f"❌ {len(mismatches)}只股票数据不一致")
                for m in mismatches[:3]:
                    log.info(f"   {m}")
            else:
                log.info("✅ 日线分钟数据一致")
            
            conn.close()
        
        # 检查是否有实时聚合逻辑
        realtime_aggregator = self.base_path / "beifeng/realtime_aggregator.py"
        if realtime_aggregator.exists():
            content = realtime_aggregator.read_text()
            if 'stocks.db' in content:
                self.critical_issues.append("北风: realtime_aggregator使用旧数据库")
                log.info("❌ realtime_aggregator使用旧数据库")
            else:
                log.info("✅ realtime_aggregator数据库路径正确")
    
    def audit_nanfeng(self):
        """审核南风 - 策略计算"""
        log.info("\n" + "="*80)
        log.info("🌬️ 南风审核 - 量化策略")
        log.info("="*80)
        
        # 检查数据库路径
        nanfeng_files = ['nanfeng_v5_1.py', 'nanfeng_production.py']
        for f in nanfeng_files:
            file_path = self.base_path / "nanfeng" / f
            if file_path.exists():
                content = file_path.read_text()
                if 'stocks.db' in content:
                    self.critical_issues.append(f"南风: {f}使用旧数据库")
                    log.info(f"❌ {f}使用旧数据库")
                else:
                    log.info(f"✅ {f}数据库路径正确")
        
        # 检查策略配置
        config_files = [
            'strategy_config_v52.py',
            'strategy_config_v53.py',
            'strategy_config_v54_conservative.py'
        ]
        
        for f in config_files:
            file_path = self.base_path / "nanfeng" / f
            if file_path.exists():
                log.info(f"✅ {f}存在")
    
    def audit_hongzhong(self):
        """审核红中 - 信号推送"""
        log.info("\n" + "="*80)
        log.info("🀄 红中审核 - 决策预警")
        log.info("="*80)
        
        # 检查是否使用模拟数据
        hongzhong_v3 = self.base_path / "hongzhong/hongzhong_v3.py"
        if hongzhong_v3.exists():
            content = hongzhong_v3.read_text()
            
            # 检查是否有硬编码价格
            if "'entry_price': 10.27" in content or "'entry_price': 25.50" in content:
                self.critical_issues.append("红中: 使用硬编码模拟价格")
                log.info("❌ 使用硬编码模拟价格")
            else:
                log.info("✅ 无硬编码价格")
            
            # 检查是否从数据库获取
            if "get_stock_name" in content:
                log.info("✅ 使用股票名称管理器")
            else:
                self.issues.append("红中: 未使用股票名称管理器")
                log.info("⚠️  未使用股票名称管理器")
        
        # 检查定时任务
        cron_files = [
            'cron_report_30min.sh',
            'cron_close_report.sh'
        ]
        for f in cron_files:
            if (self.base_path / "hongzhong" / f).exists():
                log.info(f"✅ {f}存在")
    
    def audit_xifeng(self):
        """审核西风 - 板块分析"""
        log.info("\n" + "="*80)
        log.info("🍃 西风审核 - 舆情分析")
        log.info("="*80)
        
        # 检查板块数据更新
        hot_spots = self.base_path / "xifeng/data/hot_spots.json"
        if hot_spots.exists():
            mtime = datetime.fromtimestamp(hot_spots.stat().st_mtime)
            hours_ago = (datetime.now() - mtime).total_seconds() / 3600
            
            if hours_ago > 24:
                self.issues.append(f"西风: 热点数据{hours_ago:.1f}小时未更新")
                log.info(f"⚠️  热点数据{hours_ago:.1f}小时未更新")
            else:
                log.info(f"✅ 热点数据{hours_ago:.1f}小时前更新")
        else:
            self.issues.append("西风: 无热点数据文件")
            log.info("❌ 无热点数据文件")
    
    def audit_facai(self):
        """审核发财 - 模拟交易"""
        log.info("\n" + "="*80)
        log.info("💰 发财审核 - 模拟交易")
        log.info("="*80)
        
        # 检查V2.0是否存在
        facai_v2 = self.base_path / "facai/facai_v2.py"
        if facai_v2.exists():
            log.info("✅ facai_v2.py存在")
            
            # 检查数据库配置
            content = facai_v2.read_text()
            if 'portfolio_v2.db' in content:
                log.info("✅ 使用V2数据库")
            else:
                self.issues.append("发财: 未使用V2数据库")
                log.info("⚠️  未使用V2数据库")
        else:
            self.critical_issues.append("发财: V2.0不存在")
            log.info("❌ facai_v2.py不存在")
    
    def audit_baiban(self):
        """审核白板 - 策略进化"""
        log.info("\n" + "="*80)
        log.info("🀆 白板审核 - 策略进化")
        log.info("="*80)
        
        # 检查回测系统
        backtest = self.base_path / "baiban/backtest_5strategies_v2.py"
        if backtest.exists():
            log.info("✅ 回测系统存在")
        else:
            self.issues.append("白板: 回测系统不存在")
            log.info("⚠️  回测系统不存在")
    
    def audit_caishen(self):
        """财神爷自审"""
        log.info("\n" + "="*80)
        log.info("💰 财神爷自审 - 监督协调")
        log.info("="*80)
        
        # 检查每小时报告
        hourly_report = Path.home() / ".openclaw/workspace/scripts/caishen_hourly_report_v5.py"
        if hourly_report.exists():
            log.info("✅ 每小时报告系统存在")
        else:
            self.issues.append("财神爷: 每小时报告不存在")
            log.info("⚠️  每小时报告不存在")
    
    def print_summary(self):
        """输出总结"""
        log.info("\n" + "="*80)
        log.info("📊 审核总结")
        log.info("="*80)
        
        log.info(f"\n🔴 严重问题: {len(self.critical_issues)} 个")
        for issue in self.critical_issues:
            log.info(f"  ❌ {issue}")
        
        log.info(f"\n🟡 一般问题: {len(self.issues)} 个")
        for issue in self.issues[:10]:
            log.info(f"  ⚠️  {issue}")
        if len(self.issues) > 10:
            log.info(f"  ... 还有 {len(self.issues)-10} 个")
        
        log.info("\n" + "="*80)
        if self.critical_issues:
            log.info("🚨 存在严重问题，必须立即修复！")
        elif self.issues:
            log.info("⚠️  存在一般问题，建议修复")
        else:
            log.info("✅ 所有Agent正常")
        log.info("="*80)


if __name__ == '__main__':
    auditor = AgentAuditor()
    auditor.audit_all()
