#!/usr/bin/env python3
"""
北风 - 核心100只股票（立即执行）
"""

import json
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw/agents/beifeng"

def get_top100_stocks():
    """核心100只：指数+蓝筹+热门"""
    
    stocks = [
        # 主要指数
        {'code': 'sh000001', 'name': '上证指数', 'market': 'SH'},
        {'code': 'sh000016', 'name': '上证50', 'market': 'SH'},
        {'code': 'sh000300', 'name': '沪深300', 'market': 'SH'},
        {'code': 'sh000905', 'name': '中证500', 'market': 'SH'},
        {'code': 'sh000688', 'name': '科创50', 'market': 'SH'},
        {'code': 'sz399001', 'name': '深证成指', 'market': 'SZ'},
        {'code': 'sz399006', 'name': '创业板指', 'market': 'SZ'},
        
        # 上海蓝筹
        {'code': 'sh600000', 'name': '浦发银行', 'market': 'SH'},
        {'code': 'sh600004', 'name': '白云机场', 'market': 'SH'},
        {'code': 'sh600009', 'name': '上海机场', 'market': 'SH'},
        {'code': 'sh600016', 'name': '民生银行', 'market': 'SH'},
        {'code': 'sh600028', 'name': '中国石化', 'market': 'SH'},
        {'code': 'sh600030', 'name': '中信证券', 'market': 'SH'},
        {'code': 'sh600031', 'name': '三一重工', 'market': 'SH'},
        {'code': 'sh600036', 'name': '招商银行', 'market': 'SH'},
        {'code': 'sh600048', 'name': '保利发展', 'market': 'SH'},
        {'code': 'sh600050', 'name': '中国联通', 'market': 'SH'},
        {'code': 'sh600104', 'name': '上汽集团', 'market': 'SH'},
        {'code': 'sh600276', 'name': '恒瑞医药', 'market': 'SH'},
        {'code': 'sh600309', 'name': '万华化学', 'market': 'SH'},
        {'code': 'sh600519', 'name': '贵州茅台', 'market': 'SH'},
        {'code': 'sh600585', 'name': '海螺水泥', 'market': 'SH'},
        {'code': 'sh600690', 'name': '海尔智家', 'market': 'SH'},
        {'code': 'sh600887', 'name': '伊利股份', 'market': 'SH'},
        {'code': 'sh601012', 'name': '隆基绿能', 'market': 'SH'},
        {'code': 'sh601088', 'name': '中国神华', 'market': 'SH'},
        {'code': 'sh601166', 'name': '兴业银行', 'market': 'SH'},
        {'code': 'sh601318', 'name': '中国平安', 'market': 'SH'},
        {'code': 'sh601398', 'name': '工商银行', 'market': 'SH'},
        {'code': 'sh601628', 'name': '中国人寿', 'market': 'SH'},
        {'code': 'sh601668', 'name': '中国建筑', 'market': 'SH'},
        {'code': 'sh601888', 'name': '中国中免', 'market': 'SH'},
        {'code': 'sh603259', 'name': '药明康德', 'market': 'SH'},
        {'code': 'sh603288', 'name': '海天味业', 'market': 'SH'},
        {'code': 'sh603501', 'name': '韦尔股份', 'market': 'SH'},
        
        # 科创板
        {'code': 'sh688001', 'name': '华兴源创', 'market': 'SH'},
        {'code': 'sh688002', 'name': '睿创微纳', 'market': 'SH'},
        {'code': 'sh688003', 'name': '天准科技', 'market': 'SH'},
        {'code': 'sh688008', 'name': '澜起科技', 'market': 'SH'},
        {'code': 'sh688009', 'name': '中国通号', 'market': 'SH'},
        {'code': 'sh688012', 'name': '中微公司', 'market': 'SH'},
        {'code': 'sh688036', 'name': '传音控股', 'market': 'SH'},
        {'code': 'sh688111', 'name': '金山办公', 'market': 'SH'},
        {'code': 'sh688169', 'name': '石头科技', 'market': 'SH'},
        {'code': 'sh688981', 'name': '中芯国际', 'market': 'SH'},
        
        # 深圳主板
        {'code': 'sz000001', 'name': '平安银行', 'market': 'SZ'},
        {'code': 'sz000002', 'name': '万科A', 'market': 'SZ'},
        {'code': 'sz000063', 'name': '中兴通讯', 'market': 'SZ'},
        {'code': 'sz000100', 'name': 'TCL科技', 'market': 'SZ'},
        {'code': 'sz000333', 'name': '美的集团', 'market': 'SZ'},
        {'code': 'sz000538', 'name': '云南白药', 'market': 'SZ'},
        {'code': 'sz000568', 'name': '泸州老窖', 'market': 'SZ'},
        {'code': 'sz000651', 'name': '格力电器', 'market': 'SZ'},
        {'code': 'sz000725', 'name': '京东方A', 'market': 'SZ'},
        {'code': 'sz000768', 'name': '中航西飞', 'market': 'SZ'},
        {'code': 'sz000858', 'name': '五粮液', 'market': 'SZ'},
        {'code': 'sz000895', 'name': '双汇发展', 'market': 'SZ'},
        {'code': 'sz002001', 'name': '新和成', 'market': 'SZ'},
        {'code': 'sz002007', 'name': '华兰生物', 'market': 'SZ'},
        {'code': 'sz002024', 'name': '苏宁易购', 'market': 'SZ'},
        {'code': 'sz002027', 'name': '分众传媒', 'market': 'SZ'},
        {'code': 'sz002049', 'name': '紫光国微', 'market': 'SZ'},
        {'code': 'sz002120', 'name': '韵达股份', 'market': 'SZ'},
        {'code': 'sz002142', 'name': '宁波银行', 'market': 'SZ'},
        {'code': 'sz002230', 'name': '科大讯飞', 'market': 'SZ'},
        {'code': 'sz002236', 'name': '大华股份', 'market': 'SZ'},
        {'code': 'sz002271', 'name': '东方雨虹', 'market': 'SZ'},
        {'code': 'sz002304', 'name': '洋河股份', 'market': 'SZ'},
        {'code': 'sz002352', 'name': '顺丰控股', 'market': 'SZ'},
        {'code': 'sz002415', 'name': '海康威视', 'market': 'SZ'},
        {'code': 'sz002460', 'name': '赣锋锂业', 'market': 'SZ'},
        {'code': 'sz002475', 'name': '立讯精密', 'market': 'SZ'},
        {'code': 'sz002594', 'name': '比亚迪', 'market': 'SZ'},
        {'code': 'sz002714', 'name': '牧原股份', 'market': 'SZ'},
        {'code': 'sz002812', 'name': '恩捷股份', 'market': 'SZ'},
        
        # 创业板
        {'code': 'sz300003', 'name': '乐普医疗', 'market': 'SZ'},
        {'code': 'sz300014', 'name': '亿纬锂能', 'market': 'SZ'},
        {'code': 'sz300015', 'name': '爱尔眼科', 'market': 'SZ'},
        {'code': 'sz300033', 'name': '同花顺', 'market': 'SZ'},
        {'code': 'sz300059', 'name': '东方财富', 'market': 'SZ'},
        {'code': 'sz300122', 'name': '智飞生物', 'market': 'SZ'},
        {'code': 'sz300124', 'name': '汇川技术', 'market': 'SZ'},
        {'code': 'sz300142', 'name': '沃森生物', 'market': 'SZ'},
        {'code': 'sz300274', 'name': '阳光电源', 'market': 'SZ'},
        {'code': 'sz300408', 'name': '三环集团', 'market': 'SZ'},
        {'code': 'sz300413', 'name': '芒果超媒', 'market': 'SZ'},
        {'code': 'sz300433', 'name': '蓝思科技', 'market': 'SZ'},
        {'code': 'sz300498', 'name': '温氏股份', 'market': 'SZ'},
        {'code': 'sz300750', 'name': '宁德时代', 'market': 'SZ'},
        {'code': 'sz300760', 'name': '迈瑞医疗', 'market': 'SZ'},
        {'code': 'sz300999', 'name': '金龙鱼', 'market': 'SZ'},
    ]
    
    return stocks

def main():
    print("🌪️ 生成核心100只股票列表...")
    stocks = get_top100_stocks()
    
    # 保存为当前任务列表
    output_file = WORKSPACE / "data" / "core100_stocks.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(stocks, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 已生成 {len(stocks)} 只核心股票")
    print(f"💾 保存到 {output_file}")
    
    # 同时更新 all_stocks.json（核心100 + 扩展3000）
    # 读取扩展列表
    with open(WORKSPACE / "data" / "all_stocks.json") as f:
        extended = json.load(f)
    
    # 核心100放前面（优先抓取）
    combined = stocks + [s for s in extended if s['code'] not in {x['code'] for x in stocks}]
    
    with open(WORKSPACE / "data" / "all_stocks.json", 'w', encoding='utf-8') as f:
        json.dump(combined, f, ensure_ascii=False, indent=2)
    
    print(f"\n📊 总列表: {len(combined)} 只")
    print(f"  - 核心100: 优先立即抓取")
    print(f"  - 扩展3000+: 定时任务逐步补全")

if __name__ == '__main__':
    main()
