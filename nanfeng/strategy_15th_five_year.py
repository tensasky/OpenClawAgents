#!/usr/bin/env python3
"""
十五五规划板块监控策略 - 15th Five-Year Plan Sector Strategy
监控政策重点板块，筛选龙头股票
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict

# 十五五重点板块配置
FIFTEENTH_FIVE_YEAR_SECTORS = {
    "新质生产力": {
        "priority": 1,
        "stocks": {
            "AI算力": ["sh603019", "sz000977", "sh688256"],  # 中科曙光、浪潮信息、寒武纪
            "6G通信": ["sz000063", "sh600487", "sh688387"],  # 中兴通讯、亨通光电、信科移动
            "商业航天": ["sh600118", "sh600879", "sz002151"],  # 中国卫星、航天电子、北斗星通
        }
    },
    "绿色低碳": {
        "priority": 2,
        "stocks": {
            "储能": ["sz300750", "sz300014", "sz300274"],  # 宁德时代、亿纬锂能、阳光电源
            "氢能": ["sh688339", "sz000723", "sz000338"],  # 亿华通、美锦能源、潍柴动力
            "光伏": ["sh601012", "sh600438", "sh688223"],  # 隆基绿能、通威股份、晶科能源
        }
    },
    "高端制造": {
        "priority": 3,
        "stocks": {
            "半导体设备": ["sz002371", "sh688012", "sh688072"],  # 北方华创、中微公司、拓荆科技
            "工业母机": ["sh601882", "sh688305", "sz300161"],  # 海天精工、科德数控、华中数控
            "人形机器人": ["sz300124", "sz002747", "sh688017"],  # 汇川技术、埃斯顿、绿的谐波
        }
    },
    "数字经济": {
        "priority": 4,
        "stocks": {
            "数据中心": ["sh603881", "sz300738", "sh300383"],  # 数据港、奥飞数据、光环新网
            "数据要素": ["sz300212", "sz000032", "sh600602"],  # 易华录、深桑达、云赛智联
        }
    },
    "生物医药": {
        "priority": 5,
        "stocks": {
            "创新药": ["sh688235", "sh01801", "sh688331"],  # 百济神州、信达生物、荣昌生物
            "医疗器械": ["sz300760", "sh688271", "sz300003"],  # 迈瑞医疗、联影医疗、乐普医疗
        }
    },
    "自主可控": {
        "priority": 6,
        "stocks": {
            "信创": ["sh600536", "sh688111", "sz300598"],  # 中国软件、金山办公、诚迈科技
            "光刻胶": ["sz300346", "sz300655", "sz300236"],  # 南大光电、晶瑞电材、上海新阳
        }
    }
}


class FifteenthFiveYearMonitor:
    """十五五规划板块监控器"""
    
    def __init__(self):
        self.sectors = FIFTEENTH_FIVE_YEAR_SECTORS
        self.data_file = Path(__file__).parent / "15th_five_year_sectors.json"
        
    def save_config(self):
        """保存配置到文件"""
        with open(self.data_file, 'w', encoding='utf-8') as f:
            json.dump(self.sectors, f, ensure_ascii=False, indent=2)
        
    def get_all_stocks(self) -> List[str]:
        """获取所有监控股票"""
        all_stocks = []
        for sector_data in self.sectors.values():
            for sub_sector, stocks in sector_data['stocks'].items():
                all_stocks.extend(stocks)
        return list(set(all_stocks))  # 去重
    
    def get_sector_by_stock(self, stock_code: str) -> Dict:
        """根据股票代码查找所属板块"""
        for sector_name, sector_data in self.sectors.items():
            for sub_sector, stocks in sector_data['stocks'].items():
                if stock_code in stocks:
                    return {
                        'main_sector': sector_name,
                        'sub_sector': sub_sector,
                        'priority': sector_data['priority']
                    }
        return None
    
    def get_priority_stocks(self, max_priority: int = 3) -> List[str]:
        """获取优先级最高的股票"""
        priority_stocks = []
        for sector_name, sector_data in self.sectors.items():
            if sector_data['priority'] <= max_priority:
                for stocks in sector_data['stocks'].values():
                    priority_stocks.extend(stocks)
        return list(set(priority_stocks))
    
    def generate_report(self) -> str:
        """生成板块配置报告"""
        report = "🎯 十五五规划板块监控策略\n"
        report += "=" * 60 + "\n\n"
        
        for sector_name, sector_data in sorted(self.sectors.items(), 
                                                key=lambda x: x[1]['priority']):
            priority = sector_data['priority']
            emoji = "🔥" if priority <= 2 else "⭐" if priority <= 4 else "📌"
            
            report += f"{emoji} {sector_name} (优先级: {priority})\n"
            report += "-" * 60 + "\n"
            
            for sub_sector, stocks in sector_data['stocks'].items():
                report += f"  📊 {sub_sector}:\n"
                for stock in stocks:
                    report += f"    • {stock}\n"
            report += "\n"
        
        total_stocks = len(self.get_all_stocks())
        priority_stocks = len(self.get_priority_stocks(max_priority=3))
        
        report += "=" * 60 + "\n"
        report += f"📈 总计: {total_stocks} 只重点监控股票\n"
        report += f"🔥 高优先级: {priority_stocks} 只 (优先级1-3)\n"
        report += "=" * 60 + "\n"
        
        return report


def main():
    """主程序"""
    monitor = FifteenthFiveYearMonitor()
    
    # 保存配置
    monitor.save_config()
    
    # 打印报告
    print(monitor.generate_report())
    
    # 获取所有股票
    all_stocks = monitor.get_all_stocks()
    print(f"\n✅ 已配置 {len(all_stocks)} 只重点监控股票")
    
    # 获取高优先级股票
    priority_stocks = monitor.get_priority_stocks(max_priority=3)
    print(f"🔥 高优先级股票: {len(priority_stocks)} 只")
    print(f"   {', '.join(priority_stocks[:10])}...")


if __name__ == '__main__':
    main()
