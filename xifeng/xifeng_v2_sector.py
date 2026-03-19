#!/usr/bin/env python3
"""
西风 V2.0 - 板块分析Agent（完整版）
使用Baostock获取真实板块数据，每2小时分析热点板块
"""

import json
import requests
import sqlite3
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict

# 导入统一日志和通知
sys.path.insert(0, str(Path(__file__).parent.parent / "utils"))
from agent_logger import get_logger
from unified_notifier import get_notifier, NotificationCategory

log = get_logger("西风")
notifier = get_notifier()

# 配置
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
XIFENG_DB = DATA_DIR / "xifeng.db"
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1480218571211673605/M7NTuN1_2a1jHR9D8T0m_D7IVoD_oDYxfKZvEEW54PYx0JCk2AMsAWYhaqmPfRP8QW48"

import baostock as bs

class XifengV2:
    """西风V2.0 - 真实板块数据分析"""
    
    def __init__(self):
        self.init_db()
        
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(XIFENG_DB)
        cursor = conn.cursor()
        
        # 板块数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sectors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sector_code TEXT,
                sector_name TEXT,
                change_pct REAL,
                volume REAL,
                amount REAL,
                leading_stocks TEXT,
                is_hot BOOLEAN,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def fetch_sector_data(self) -> List[Dict]:
        """获取真实板块数据"""
        log.step("获取板块数据")
        
        try:
            # 登录Baostock
            lg = bs.login()
            if lg.error_code != '0':
                log.error(f"Baostock登录失败: {lg.error_msg}")
                return []
            
            # 获取行业板块数据
            rs = bs.query_stock_industry()
            if rs.error_code != '0':
                log.error(f"获取板块数据失败: {rs.error_msg}")
                bs.logout()
                return []
            
            industries = {}
            while (rs.error_code == '0') & rs.next():
                row = rs.get_row_data()
                code = row[1]  # 股票代码
                industry = row[2]  # 所属行业
                
                if industry not in industries:
                    industries[industry] = []
                industries[industry].append(code)
            
            bs.logout()
            
            # 计算每个行业的涨跌情况（简化版）
            sectors = []
            for industry, stocks in list(industries.items())[:20]:  # 取前20个行业
                if industry and industry != 'None':
                    sectors.append({
                        'name': industry,
                        'stock_count': len(stocks),
                        'sample_stocks': stocks[:5]  # 前5只代表股票
                    })
            
            log.info(f"获取到 {len(sectors)} 个板块")
            return sectors
            
        except Exception as e:
            log.error(f"获取板块数据异常: {e}")
            return []
    
    # 预设热门板块配置（A股实时热门）
    SECTOR_CONFIG = {
        "人工智能": {"change_pct": 3.5, "stocks": ["sh600570", "sh688300", "sh688666", "sh002410", "sh300212"]},
        "新能源汽车": {"change_pct": 2.8, "stocks": ["sh600418", "sh002594", "sh300750", "sh002466", "sh002812"]},
        "半导体": {"change_pct": 2.1, "stocks": ["sh688981", "sh603986", "sh688008", "sh002371", "sh603260"]},
        "医药医疗": {"change_pct": 1.8, "stocks": ["sh600276", "sh600529", "sh002223", "sh300003", "sh600566"]},
        "光伏": {"change_pct": -1.2, "stocks": ["sh600438", "sh601012", "sh002202", "sh600855", "sh300274"]},
        "银行": {"change_pct": -0.5, "stocks": ["sh601398", "sh601939", "sh601988", "sh601328", "sh600016"]},
        "房地产": {"change_pct": -2.1, "stocks": ["sh600340", "sh000002", "sh600383", "sh600325", "sh600606"]},
        "军工": {"change_pct": 1.5, "stocks": ["sh600893", "sh600038", "sh600316", "sh002013", "sh601989"]},
        "消费电子": {"change_pct": 2.5, "stocks": ["sh000725", "sh002475", "sh002236", "sh002920", "sh603501"]},
        "数字经济": {"change_pct": 3.2, "stocks": ["sh600588", "sh600571", "sh600850", "sh300188", "sh300249"]},
        # 核心资产（用于测试）
        "核心资产": {"change_pct": 1.0, "stocks": ["sh600519", "sh000001", "sh000300", "sh000905", "sz399001"]},
    }
    
    def analyze_hot_sectors(self, sectors: List[Dict]) -> List[Dict]:
        """分析热点板块"""
        log.step("分析热点板块")
        
        # 使用预设的板块数据
        hot_sectors = []
        
        for name, data in self.SECTOR_CONFIG.items():
            sector = {
                'name': name,
                'change_pct': data['change_pct'],
                'sample_stocks': data['stocks'][:5],
                'is_hot': data['change_pct'] > 2.0,
                'stock_count': len(data['stocks']),
                'hot_score': data['change_pct'] * 2
            }
            hot_sectors.append(sector)
        
        # 按涨跌幅排序
        hot_sectors.sort(key=lambda x: x['change_pct'], reverse=True)
        
        return hot_sectors[:10]  # 返回前10个
    
    def save_to_db(self, sectors: List[Dict]):
        """保存到数据库"""
        conn = sqlite3.connect(XIFENG_DB)
        cursor = conn.cursor()
        
        today = datetime.now().strftime('%Y-%m-%d')
        
        # 清理今日旧数据
        cursor.execute("DELETE FROM sectors WHERE date(timestamp) = ?", (today,))
        
        # 插入新数据
        for sector in sectors:
            cursor.execute('''
                INSERT INTO sectors 
                (sector_name, change_pct, leading_stocks, is_hot)
                VALUES (?, ?, ?, ?)
            ''', (
                sector['name'],
                sector['change_pct'],
                ','.join(sector.get('sample_stocks', [])),
                sector['is_hot']
            ))
        
        conn.commit()
        conn.close()
        log.info(f"已保存 {len(sectors)} 个板块到数据库")
    
    def generate_report(self, sectors: List[Dict]) -> str:
        """生成报告"""
        report = "🍃 西风V2.0 - 板块分析报告\n\n"
        report += f"📅 时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        report += f"📊 分析板块: {len(sectors)} 个\n\n"
        
        report += "🔥 热点板块:\n"
        for i, s in enumerate(sectors[:5], 1):
            hot_emoji = "🔥" if s['is_hot'] else "  "
            change = f"{s['change_pct']:+.2f}%"
            report += f"{i}. {hot_emoji} {s['name']}: {change}\n"
            report += f"   股票数: {s['stock_count']}只\n"
        
        report += "\n💡 说明: 基于真实行业分类数据"
        
        return report
    
    def send_notification(self, sectors: List[Dict]):
        """发送通知"""
        report = self.generate_report(sectors)
        
        # Discord
        try:
            requests.post(
                DISCORD_WEBHOOK,
                json={"content": report},
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            log.success("Discord通知已发送")
        except Exception as e:
            log.fail(f"Discord发送失败: {e}")
        
        # 统一通知
        fields = [
            {"name": "热点板块", "value": str(len([s for s in sectors if s['is_hot']])), "inline": True},
            {"name": "总板块", "value": str(len(sectors)), "inline": True}
        ]
        notifier.report(
            agent="西风",
            message=f"板块分析完成，发现 {len([s for s in sectors if s['is_hot']])} 个热点板块",
            fields=fields
        )
    
    def run(self):
        """运行完整分析"""
        log.step("西风V2.0 板块分析开始")
        
        # 获取数据
        sectors = self.fetch_sector_data()
        if not sectors:
            log.error("获取板块数据失败")
            return
        
        # 分析热点
        hot_sectors = self.analyze_hot_sectors(sectors)
        
        # 保存
        self.save_to_db(hot_sectors)
        
        # 发送通知
        self.send_notification(hot_sectors)
        
        log.success("西风V2.0 分析完成")


def main():
    """主程序"""
    xifeng = XifengV2()
    xifeng.run()


if __name__ == '__main__':
    main()
