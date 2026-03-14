#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("西风")

"""
西风 - 股票-板块关联数据
A股核心股票与板块映射
"""

# 板块关键词映射
SECTOR_KEYWORDS = {
    "人工智能": ["人工智能", "AI", "大模型", "ChatGPT", "算力", "算法", "智能", "GPT", "机器学习"],
    "新能源": ["新能源", "光伏", "风电", "储能", "锂电", "电池", "太阳能", "清洁能源"],
    "机器人": ["机器人", "人形机器人", "工业机器人", "自动化", "减速器", "伺服"],
    "半导体": ["半导体", "芯片", "集成电路", "晶圆", "光刻", "封装", "测试", "EDA"],
    "医药": ["医药", "生物", "疫苗", "创新药", "医疗器械", "CXO", "CRO", "医保"],
    "房地产": ["房地产", "地产", "楼市", "房价", "房企", "拿地", "竣工", "销售"],
    "金融": ["银行", "保险", "券商", "证券", "金融", "信贷", "利率", "降准", "降息"],
    "汽车": ["汽车", "新能源车", "电动车", "智能驾驶", "自动驾驶", "造车", "销量"],
    "消费": ["消费", "白酒", "食品饮料", "零售", "家电", "免税", "旅游", "餐饮"],
    "中字头": ["中字头", "央企", "国企", "国资", "改革", "重组", "合并"],
    "低空经济": ["低空经济", "飞行汽车", "eVTOL", "无人机", "通航", "航空"],
    "有色": ["有色", "金属", "铜", "铝", "锂", "镍", "钴", "稀土", "黄金", "白银"]
}

# 板块核心股票映射
SECTOR_LEADING_STOCKS = {
    "人工智能": [
        {"code": "300033", "name": "同花顺", "weight": 10},
        {"code": "002230", "name": "科大讯飞", "weight": 9},
        {"code": "603019", "name": "中科曙光", "weight": 8},
        {"code": "000938", "name": "中芯国际", "weight": 8},
        {"code": "300474", "name": "景嘉微", "weight": 7},
    ],
    "新能源": [
        {"code": "300750", "name": "宁德时代", "weight": 10},
        {"code": "002594", "name": "比亚迪", "weight": 9},
        {"code": "601012", "name": "隆基绿能", "weight": 8},
        {"code": "300014", "name": "亿纬锂能", "weight": 7},
        {"code": "002459", "name": "晶澳科技", "weight": 7},
    ],
    "机器人": [
        {"code": "002050", "name": "三花智控", "weight": 9},
        {"code": "002747", "name": "埃斯顿", "weight": 8},
        {"code": "603486", "name": "科沃斯", "weight": 7},
        {"code": "300124", "name": "汇川技术", "weight": 8},
        {"code": "002031", "name": "巨轮智能", "weight": 6},
    ],
    "半导体": [
        {"code": "688981", "name": "中芯国际", "weight": 10},
        {"code": "603501", "name": "韦尔股份", "weight": 8},
        {"code": "002371", "name": "北方华创", "weight": 8},
        {"code": "688012", "name": "中微公司", "weight": 7},
        {"code": "300782", "name": "卓胜微", "weight": 7},
    ],
    "医药": [
        {"code": "600276", "name": "恒瑞医药", "weight": 10},
        {"code": "300760", "name": "迈瑞医疗", "weight": 9},
        {"code": "603259", "name": "药明康德", "weight": 8},
        {"code": "300122", "name": "智飞生物", "weight": 7},
        {"code": "000538", "name": "云南白药", "weight": 7},
    ],
    "房地产": [
        {"code": "000002", "name": "万科A", "weight": 10},
        {"code": "600048", "name": "保利发展", "weight": 9},
        {"code": "001979", "name": "招商蛇口", "weight": 8},
        {"code": "600606", "name": "绿地控股", "weight": 7},
        {"code": "000069", "name": "华侨城A", "weight": 6},
    ],
    "金融": [
        {"code": "600036", "name": "招商银行", "weight": 10},
        {"code": "601318", "name": "中国平安", "weight": 9},
        {"code": "601398", "name": "工商银行", "weight": 8},
        {"code": "600030", "name": "中信证券", "weight": 8},
        {"code": "601688", "name": "华泰证券", "weight": 7},
    ],
    "汽车": [
        {"code": "002594", "name": "比亚迪", "weight": 10},
        {"code": "601127", "name": "赛力斯", "weight": 8},
        {"code": "000625", "name": "长安汽车", "weight": 7},
        {"code": "600104", "name": "上汽集团", "weight": 7},
        {"code": "601633", "name": "长城汽车", "weight": 7},
    ],
    "消费": [
        {"code": "600519", "name": "贵州茅台", "weight": 10},
        {"code": "000858", "name": "五粮液", "weight": 9},
        {"code": "603288", "name": "海天味业", "weight": 8},
        {"code": "600887", "name": "伊利股份", "weight": 8},
        {"code": "601888", "name": "中国中免", "weight": 7},
    ],
    "中字头": [
        {"code": "601988", "name": "中国银行", "weight": 9},
        {"code": "601728", "name": "中国电信", "weight": 8},
        {"code": "600028", "name": "中国石化", "weight": 8},
        {"code": "601390", "name": "中国中铁", "weight": 7},
        {"code": "601668", "name": "中国建筑", "weight": 7},
    ],
    "低空经济": [
        {"code": "002050", "name": "三花智控", "weight": 8},
        {"code": "002151", "name": "北斗星通", "weight": 7},
        {"code": "300900", "name": "广联航空", "weight": 7},
        {"code": "002097", "name": "山河智能", "weight": 6},
        {"code": "300185", "name": "通裕重工", "weight": 6},
    ],
    "有色": [
        {"code": "601899", "name": "紫金矿业", "weight": 10},
        {"code": "603993", "name": "洛阳钼业", "weight": 8},
        {"code": "600362", "name": "江西铜业", "weight": 7},
        {"code": "002460", "name": "赣锋锂业", "weight": 8},
        {"code": "600111", "name": "北方稀土", "weight": 7},
    ],
}


def get_leading_stocks(sector: str, top_n: int = 3) -> list:
    """获取板块龙头股"""
    stocks = SECTOR_LEADING_STOCKS.get(sector, [])
    # 按权重排序
    sorted_stocks = sorted(stocks, key=lambda x: x['weight'], reverse=True)
    return sorted_stocks[:top_n]


def get_stock_sector(stock_code: str) -> str:
    """根据股票代码获取所属板块"""
    for sector, stocks in SECTOR_LEADING_STOCKS.items():
        for stock in stocks:
            if stock['code'] == stock_code:
                return sector
    return "其他"


if __name__ == '__main__':
    log.info("板块龙头股数据")
    log.info("=" * 60)
    
    for sector in ["人工智能", "新能源", "机器人", "半导体"]:
        stocks = get_leading_stocks(sector, 3)
        log.info(f"\n{sector}:")
        for s in stocks:
            log.info(f"  {s['code']} {s['name']} (权重{s['weight']})")
