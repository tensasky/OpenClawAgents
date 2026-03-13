#!/usr/bin/env python3
"""
北风 - 数据库配置（物理隔离版本）
"""

from pathlib import Path

# 数据库路径（物理隔离）
DATA_DIR = Path.home() / "Documents/OpenClawAgents/beifeng/data"

# 真实历史数据（日线+分钟）
REAL_DB = DATA_DIR / "stocks_real.db"

# 实时虚拟数据（交易时段分钟聚合）
VIRTUAL_DB = DATA_DIR / "stocks_virtual.db"

# 原数据库（保留兼容）
LEGACY_DB = DATA_DIR / "stocks.db"

# 数据库选择规则
DB_CONFIG = {
    'daily_real': REAL_DB,      # 真实日线（收盘后）
    'daily_virtual': VIRTUAL_DB, # 虚拟日线（交易时段）
    'minute': REAL_DB,          # 分钟数据
}

def get_db_path(data_type: str, is_virtual: bool = False) -> Path:
    """
    获取数据库路径
    
    Args:
        data_type: 'daily' 或 'minute'
        is_virtual: 是否虚拟数据（仅日线有效）
    
    Returns:
        数据库路径
    """
    if data_type == 'daily':
        return VIRTUAL_DB if is_virtual else REAL_DB
    elif data_type == 'minute':
        return REAL_DB
    else:
        raise ValueError(f"未知数据类型: {data_type}")


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == '__main__':
    print("="*70)
    print("北风数据库配置（物理隔离）")
    print("="*70)
    
    print(f"\n📁 真实数据数据库: {REAL_DB}")
    print(f"   - 日线表: daily")
    print(f"   - 分钟表: minute")
    
    print(f"\n📁 虚拟数据数据库: {VIRTUAL_DB}")
    print(f"   - 虚拟日线表: daily_virtual")
    
    print(f"\n💡 使用示例:")
    print(f"   真实日线: get_db_path('daily', is_virtual=False)")
    print(f"   虚拟日线: get_db_path('daily', is_virtual=True)")
    print(f"   分钟数据: get_db_path('minute')")
    
    print("\n" + "="*70)
