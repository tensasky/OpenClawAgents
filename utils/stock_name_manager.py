#!/usr/bin/env python3
"""
股票名称管理工具
从北风数据库查询，确保准确性
"""

import sqlite3
from pathlib import Path
from typing import Dict, Optional
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("System")


BEIFENG_DB = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"

class StockNameManager:
    """股票名称管理器"""
    
    def __init__(self):
        self.cache: Dict[str, str] = {}
        self.load_all_names()
    
    def load_all_names(self):
        """从北风数据库加载所有股票名称"""
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            # 从daily表获取股票代码和名称
            cursor.execute("""
                SELECT DISTINCT stock_code, 
                       MAX(CASE WHEN stock_name IS NOT NULL THEN stock_name END) as name
                FROM daily
                GROUP BY stock_code
            """)
            
            for row in cursor.fetchall():
                code, name = row
                if code and name:
                    self.cache[code] = name
            
            conn.close()
            log.info(f"✅ 已加载 {len(self.cache)} 只股票名称")
            
        except Exception as e:
            log.info(f"❌ 加载失败: {e}")
    
    def get_name(self, stock_code: str) -> Optional[str]:
        """获取股票名称"""
        # 先从缓存查
        if stock_code in self.cache:
            return self.cache[stock_code]
        
        # 缓存未命中，查询数据库
        try:
            conn = sqlite3.connect(BEIFENG_DB)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT stock_name FROM daily 
                WHERE stock_code = ? AND stock_name IS NOT NULL
                LIMIT 1
            """, (stock_code,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result and result[0]:
                self.cache[stock_code] = result[0]
                return result[0]
            
            return None
            
        except Exception as e:
            log.info(f"查询失败 {stock_code}: {e}")
            return None
    
    def validate_name(self, stock_code: str, name: str) -> bool:
        """验证股票名称是否正确"""
        correct_name = self.get_name(stock_code)
        if correct_name is None:
            log.info(f"⚠️  未找到 {stock_code} 的名称记录")
            return False
        
        if correct_name != name:
            log.info(f"❌ 名称不匹配: {stock_code}")
            log.info(f"   输入: {name}")
            log.info(f"   正确: {correct_name}")
            return False
        
        return True
    
    def auto_correct(self, stock_code: str, input_name: str) -> str:
        """自动修正股票名称"""
        correct_name = self.get_name(stock_code)
        if correct_name and correct_name != input_name:
            log.info(f"🔄 自动修正: {stock_code} {input_name} -> {correct_name}")
            return correct_name
        return input_name


# 全局实例
stock_manager = StockNameManager()


def get_stock_name(stock_code: str) -> str:
    """获取股票名称的便捷函数"""
    name = stock_manager.get_name(stock_code)
    return name if name else stock_code


def validate_and_correct(stock_code: str, input_name: str) -> str:
    """验证并修正的便捷函数"""
    return stock_manager.auto_correct(stock_code, input_name)


if __name__ == '__main__':
    log.info("="*70)
    log.info("📊 股票名称管理工具")
    log.info("="*70)
    
    # 测试
    test_codes = ['sh600348', 'sz301667', 'sh601888', 'sz300750']
    
    log.info("\n查询测试:")
    for code in test_codes:
        name = get_stock_name(code)
        log.info(f"  {code} -> {name}")
    
    log.info("\n验证测试:")
    log.info(f"  sz301667 '测试股份': {stock_manager.validate_name('sz301667', '测试股份')}")
    log.info(f"  sz301667 '纳百川': {stock_manager.validate_name('sz301667', '纳百川')}")
    
    log.info("\n自动修正测试:")
    corrected = validate_and_correct('sz301667', '测试股份')
    log.info(f"  修正结果: {corrected}")
    
    log.info("="*70)
