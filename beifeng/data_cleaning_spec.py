#!/usr/bin/env python3
"""
北风 - 数据录入与清洗规范
明确标注数据源、单位转换、清洗规则
"""

# ============================================================================
# 数据源单位规范
# ============================================================================

DATA_SOURCE_UNITS = {
    'sina': {
        'name': '新浪财经',
        'volume_unit': '手',  # 1手 = 100股
        'volume_multiplier': 100,  # 存储时需要×100
        'amount_unit': '元',
        'price_unit': '元',
    },
    'tencent': {
        'name': '腾讯财经',
        'volume_unit': '手',  # 1手 = 100股
        'volume_multiplier': 100,  # 存储时需要×100
        'amount_unit': '元',
        'price_unit': '元',
    },
    'netease': {
        'name': '网易财经',
        'volume_unit': '股',  # 直接是股，无需转换
        'volume_multiplier': 1,
        'amount_unit': '元',
        'price_unit': '元',
    }
}

# ============================================================================
# 数据清洗规则
# ============================================================================

CLEANING_RULES = {
    # 成交量清洗
    'volume': {
        'min_value': 0,  # 最小值
        'max_value': 10000000000,  # 最大值100亿股（单日）
        'outlier_threshold': 1000,  # 异常阈值（比前5日均量高1000倍）
        'action': 'flag',  # 标记但不删除，人工复核
    },
    
    # 价格清洗
    'price': {
        'max_change_percent': 20,  # 最大涨跌幅20%（科创板除外）
        'check_ohlc': True,  # 检查OHLC合理性
        'action': 'correct',  # 自动修正或标记
    },
    
    # 时间戳清洗
    'timestamp': {
        'trading_hours': [
            ('09:30', '11:30'),  # 上午
            ('13:00', '15:00'),  # 下午
        ],
        'remove_non_trading': True,  # 删除非交易时段数据
    }
}

# ============================================================================
# 数据验证规则
# ============================================================================

VALIDATION_RULES = {
    # 分钟数据 vs 日线数据一致性检查
    'minute_daily_consistency': {
        'volume_tolerance': 5,  # 成交量差异容忍度5%
        'price_tolerance': 0.01,  # 价格差异容忍度0.01元
        'check_required': True,  # 必须检查
    },
    
    # 数据连续性检查
    'continuity': {
        'minute_expected': 240,  # 每日预期240分钟（4小时×60）
        'missing_threshold': 10,  # 缺失超过10分钟告警
    }
}

# ============================================================================
# 单位转换函数
# ============================================================================

def convert_volume(volume: int, source: str) -> int:
    """
    将成交量转换为标准单位（股）
    
    Args:
        volume: 原始成交量
        source: 数据源（sina/tencent/netease）
    
    Returns:
        转换后的成交量（股）
    """
    if source not in DATA_SOURCE_UNITS:
        raise ValueError(f"未知数据源: {source}")
    
    multiplier = DATA_SOURCE_UNITS[source]['volume_multiplier']
    return volume * multiplier


def validate_volume(volume: int, prev_volumes: list = None) -> dict:
    """
    验证成交量合理性
    
    Args:
        volume: 当前成交量
        prev_volumes: 前5日成交量列表
    
    Returns:
        {'valid': bool, 'warning': str, 'action': str}
    """
    rules = CLEANING_RULES['volume']
    
    # 基本范围检查
    if volume < rules['min_value']:
        return {'valid': False, 'warning': '成交量为负', 'action': 'reject'}
    
    if volume > rules['max_value']:
        return {'valid': False, 'warning': f'成交量超过{rules["max_value"]}', 'action': 'reject'}
    
    # 异常值检查
    if prev_volumes and len(prev_volumes) >= 5:
        avg_volume = sum(prev_volumes) / len(prev_volumes)
        if avg_volume > 0 and volume / avg_volume > rules['outlier_threshold']:
            return {
                'valid': True,  # 仍然有效但标记
                'warning': f'成交量异常，比前5日均量高{volume/avg_volume:.0f}倍',
                'action': 'flag'
            }
    
    return {'valid': True, 'warning': None, 'action': 'accept'}


# ============================================================================
# 数据录入模板
# ============================================================================

def format_insert_data(stock_code: str, data_type: str, data: dict, source: str) -> dict:
    """
    格式化数据为数据库插入格式
    
    Args:
        stock_code: 股票代码
        data_type: 'daily' 或 '1min'
        data: 原始数据
        source: 数据源
    
    Returns:
        格式化后的数据字典
    """
    # 单位转换
    volume_gu = convert_volume(data['volume'], source)
    
    # 验证
    validation = validate_volume(volume_gu)
    
    return {
        'stock_code': stock_code,
        'data_type': data_type,
        'timestamp': data['timestamp'],
        'open': data['open'],
        'high': data['high'],
        'low': data['low'],
        'close': data['close'],
        'volume': volume_gu,  # 标准单位：股
        'amount': data['amount'],
        'source': source,
        'validation_status': 'flagged' if validation['action'] == 'flag' else 'valid',
        'validation_warning': validation['warning'],
    }


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == '__main__':
    print("="*70)
    print("北风数据录入与清洗规范")
    print("="*70)
    
    print("\n📊 数据源单位规范:")
    for source, config in DATA_SOURCE_UNITS.items():
        print(f"  {source}: {config['name']}")
        print(f"    成交量单位: {config['volume_unit']} (×{config['volume_multiplier']} → 股)")
    
    print("\n🧹 清洗规则:")
    for field, rules in CLEANING_RULES.items():
        print(f"  {field}: {rules}")
    
    print("\n✅ 验证规则:")
    for check, rules in VALIDATION_RULES.items():
        print(f"  {check}: {rules}")
    
    print("\n" + "="*70)
    
    # 示例：转换新浪成交量
    print("\n💡 示例：新浪成交量转换")
    sina_volume = 10000  # 10000手
    converted = convert_volume(sina_volume, 'sina')
    print(f"  新浪原始: {sina_volume} 手")
    print(f"  转换后: {converted} 股")
    print(f"  验证: {converted} 股 = {converted/100} 手 ✓")
    
    print("\n" + "="*70)
