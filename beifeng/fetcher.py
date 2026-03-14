#!/usr/bin/env python3
"""
北风 - 数据抓取模块
支持：新浪财经、腾讯财经
"""

import requests
import json
import re
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")


logger = logging.getLogger("北风")

# 请求间隔控制（秒）
MIN_DELAY = 0.1
MAX_DELAY = 0.5

class RateLimiter:
    """请求速率限制器"""
    def __init__(self):
        self.last_request_time = 0
    
    def wait(self):
        """等待随机延迟"""
        delay = random.uniform(MIN_DELAY, MAX_DELAY)
        elapsed = time.time() - self.last_request_time
        if elapsed < delay:
            time.sleep(delay - elapsed)
        self.last_request_time = time.time()

# 全局速率限制器
_rate_limiter = RateLimiter()


@dataclass
class KLineData:
    """标准化K线数据"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float


class SinaFetcher:
    """新浪财经数据抓取"""
    
    BASE_URL = "https://quotes.money.163.com/service/chddata.html"
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_daily(self, stock_code: str, start_date: datetime, end_date: datetime) -> List[KLineData]:
        """
        获取日线数据
        股票代码格式：sh000001(上证指数), sz000001(平安银行)
        """
        # 转换代码格式
        code = self._convert_code(stock_code)
        
        # 格式化日期
        start_str = start_date.strftime('%Y%m%d')
        end_str = end_date.strftime('%Y%m%d')
        
        url = f"{self.BASE_URL}?code={code}&start={start_str}&end={end_str}&fields=TCLOSE;HIGH;LOW;TOPEN;LCLOSE;CHG;PCHG;TURNOVER;VOTURNOVER;VATURNOVER;TCAP;MCAP"
        
        try:
            # 速率限制
            _rate_limiter.wait()
            
            logger.info(f"  请求: {stock_code} ({start_str} ~ {end_str})")
            response = self.session.get(url, timeout=self.timeout)
            response.encoding = 'gb2312'
            
            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}")
            
            return self._parse_csv(response.text, stock_code)
            
        except Exception as e:
            logger.error(f"  新浪抓取失败: {e}")
            raise
    
    def _convert_code(self, stock_code: str) -> str:
        """转换为网易接口代码格式"""
        # sh000001 -> 0000001
        # sz000001 -> 1000001
        if stock_code.startswith('sh'):
            return '0' + stock_code[2:]
        elif stock_code.startswith('sz'):
            return '1' + stock_code[2:]
        elif stock_code.startswith('bj'):
            return '2' + stock_code[2:]
        return stock_code
    
    def _parse_csv(self, csv_text: str, stock_code: str) -> List[KLineData]:
        """解析CSV数据，包含完整数据清洗"""
        lines = csv_text.strip().split('\n')
        result = []
        invalid_count = 0
        
        # 跳过标题行
        for line in lines[1:]:
            if not line.strip():
                continue
            
            parts = line.split(',')
            if len(parts) < 10:
                continue
            
            try:
                # CSV格式: 日期,股票代码,名称,收盘价,最高价,最低价,开盘价,前收盘,涨跌额,涨跌幅,换手率,成交量,成交金额,总市值,流通市值
                date_str = parts[0].strip()
                timestamp = datetime.strptime(date_str, '%Y-%m-%d')
                
                # 数据清洗：转换为数值，处理无效值
                def to_float(val: str, default: float = 0.0) -> float:
                    """安全转换为float"""
                    if not val or val.strip() == '' or val.strip() == 'None':
                        return default
                    try:
                        f = float(val.strip())
                        # 检查异常值
                        if f < 0 or f > 1000000:  # 价格范围检查
                            return default
                        return f
                    except (ValueError, TypeError):
                        return default
                
                def to_int(val: str, default: int = 0) -> int:
                    """安全转换为int"""
                    if not val or val.strip() == '' or val.strip() == 'None':
                        return default
                    try:
                        return int(float(val.strip()))
                    except (ValueError, TypeError):
                        return default
                
                close = to_float(parts[3])
                high = to_float(parts[4])
                low = to_float(parts[5])
                open_price = to_float(parts[6])
                volume = to_int(parts[12])
                amount = to_float(parts[13])
                
                # 数据有效性检查
                if close <= 0 or high <= 0 or low <= 0 or open_price <= 0:
                    invalid_count += 1
                    continue
                
                # 价格逻辑检查（放宽条件）
                if low > high:
                    invalid_count += 1
                    continue
                
                kline = KLineData(
                    timestamp=timestamp,
                    close=close,
                    high=high,
                    low=low,
                    open=open_price,
                    volume=volume,
                    amount=amount
                )
                result.append(kline)
                
            except (ValueError, IndexError) as e:
                logger.warning(f"  解析行失败: {line[:50]}... ({e})")
                invalid_count += 1
                continue
        
        if invalid_count > 0:
            logger.warning(f"  清洗过滤: {invalid_count} 条无效记录")
        
        logger.info(f"  解析完成: {len(result)} 条有效记录")
        return result


class TencentFetcher:
    """腾讯财经数据抓取（备选）"""
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_daily(self, stock_code: str, start_date: datetime, end_date: datetime) -> List[KLineData]:
        """获取日线数据"""
        # 腾讯接口需要转换代码格式
        tencent_code = self._convert_code(stock_code)
        
        url = f"https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,{start_date.strftime('%Y-%m-%d')},{end_date.strftime('%Y-%m-%d')},500,qfq"
        
        try:
            # 速率限制
            _rate_limiter.wait()
            
            logger.info(f"  腾讯请求: {stock_code}")
            response = self.session.get(url, timeout=self.timeout)
            data = response.json()
            
            return self._parse_json(data, tencent_code)
            
        except Exception as e:
            logger.error(f"  腾讯抓取失败: {e}")
            raise
    
    def _convert_code(self, stock_code: str) -> str:
        """转换为腾讯代码格式"""
        if stock_code.startswith('sh'):
            return 'sh' + stock_code[2:]
        elif stock_code.startswith('sz'):
            return 'sz' + stock_code[2:]
        elif stock_code.startswith('bj'):
            return 'bj' + stock_code[2:]
        return stock_code
    
    def _parse_json(self, data: Dict, code: str) -> List[KLineData]:
        """解析JSON数据，包含完整数据清洗"""
        result = []
        invalid_count = 0
        
        key = code
        if 'data' not in data or key not in data['data']:
            logger.warning(f"  无数据返回: {code}")
            return result
        
        klines = data['data'][key].get('qfqday', [])
        if not klines:
            klines = data['data'][key].get('day', [])
        
        for item in klines:
            try:
                # 格式: [日期, 开盘, 收盘, 最低, 最高, 成交量]
                date_str = item[0]
                timestamp = datetime.strptime(date_str, '%Y-%m-%d')
                
                # 数据清洗
                def to_float(val, default: float = 0.0) -> float:
                    """安全转换为float"""
                    if val is None or val == '' or val == 'None':
                        return default
                    try:
                        f = float(val)
                        if f < 0 or f > 1000000:
                            return default
                        return f
                    except (ValueError, TypeError):
                        return default
                
                def to_int(val, default: int = 0) -> int:
                    """安全转换为int"""
                    if val is None or val == '' or val == 'None':
                        return default
                    try:
                        return int(float(val))
                    except (ValueError, TypeError):
                        return default
                
                open_price = to_float(item[1])
                close = to_float(item[2])
                high = to_float(item[3])  # 腾讯格式: [日期,开盘,收盘,最高,最低,成交量]
                low = to_float(item[4])
                volume = to_int(item[5])
                
                # 数据有效性检查
                if close <= 0 or high <= 0 or low <= 0 or open_price <= 0:
                    invalid_count += 1
                    continue
                
                # 价格逻辑检查（放宽条件）
                if low > high:
                    invalid_count += 1
                    continue
                
                kline = KLineData(
                    timestamp=timestamp,
                    open=open_price,
                    close=close,
                    low=low,
                    high=high,
                    volume=volume,
                    amount=0.0  # 腾讯接口不直接提供成交额
                )
                result.append(kline)
                
            except (ValueError, IndexError) as e:
                logger.warning(f"  解析项失败: {item} ({e})")
                invalid_count += 1
                continue
        
        if invalid_count > 0:
            logger.warning(f"  腾讯清洗过滤: {invalid_count} 条无效记录")
        
        logger.info(f"  腾讯解析完成: {len(result)} 条有效记录")
        return result


class DataFetcher:
    """统一数据抓取入口"""
    
    def __init__(self, source: str = 'sina', timeout: int = 30):
        self.source = source
        self.timeout = timeout
        
        if source == 'sina':
            self.fetcher = SinaFetcher(timeout)
        elif source == 'tencent':
            self.fetcher = TencentFetcher(timeout)
        else:
            raise ValueError(f"未知数据源: {source}")
    
    def fetch_daily(self, stock_code: str, start_date: datetime, end_date: datetime) -> List[Dict]:
        """
        获取日线数据，返回标准化字典列表
        """
        klines = self.fetcher.fetch_daily(stock_code, start_date, end_date)
        
        # 转换为字典格式（用于数据库存储）
        return [
            {
                'timestamp': k.timestamp.isoformat(),
                'open': k.open,
                'high': k.high,
                'low': k.low,
                'close': k.close,
                'volume': k.volume,
                'amount': k.amount
            }
            for k in klines
        ]


if __name__ == '__main__':
    # 测试
    logging.basicConfig(level=logging.INFO)
    
    fetcher = DataFetcher('sina')
    data = fetcher.fetch_daily(
        'sh000001',
        datetime.now() - timedelta(days=30),
        datetime.now()
    )
    log.info(f"获取到 {len(data)} 条记录")
    if data:
        log.info("最新一条:", data[-1])
