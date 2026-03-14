#!/usr/bin/env python3
"""
北风 - 分钟数据抓取模块
实时获取当日分钟线，支持交易决策
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from pathlib import Path

WORKSPACE = Path.home() / "Documents/OpenClawAgents/beifeng"


class MinuteDataFetcher:
    """分钟数据抓取器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def fetch_tencent_minute(self, stock_code: str) -> List[Dict]:
        """
        从腾讯财经获取当日分钟数据
        
        返回格式: [{time, price, volume, avg_price}, ...]
        """
        # 转换代码格式
        if stock_code.startswith('sh'):
            tencent_code = 'sh' + stock_code[2:]
        elif stock_code.startswith('sz'):
            tencent_code = 'sz' + stock_code[2:]
        else:
            tencent_code = stock_code
        
        url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={tencent_code}"
        
        try:
            response = self.session.get(url, timeout=10)
            data = response.json()
            
            key = tencent_code
            if 'data' not in data or key not in data['data']:
                log.info(f"  无分钟数据: {stock_code}")
                return []
            
            stock_data = data['data'][key]
            
            # 提取当日数据
            minute_data = []
            
            # 最新价格 - qt 格式: {key: [列表数据], ...}
            qt_data = stock_data.get('qt', {})
            if isinstance(qt_data, dict) and key in qt_data:
                qt_list = qt_data[key]
                if isinstance(qt_list, list) and len(qt_list) > 3:
                    latest_price = qt_list[3]  # 第4个元素是当前价格
                else:
                    latest_price = '0'
            else:
                latest_price = '0'
            
            # 分钟数据 - 腾讯格式: data -> data -> data (嵌套)
            raw_data = stock_data.get('data', {})
            if isinstance(raw_data, dict):
                # 腾讯格式: {'data': [...], 'date': '...'}
                data_list = raw_data.get('data', [])
            elif isinstance(raw_data, list):
                data_list = raw_data
            else:
                data_list = []
            
            for item in data_list:
                # 格式: "时间 价格 成交量 均价"
                parts = item.split()
                if len(parts) >= 3:
                    minute_data.append({
                        'time': parts[0],  # HH:MM
                        'price': float(parts[1]),
                        'volume': int(parts[2]),
                        'avg_price': float(parts[3]) if len(parts) > 3 else float(parts[1])
                    })
            
            return minute_data
            
        except Exception as e:
            log.info(f"  腾讯分钟数据失败: {e}")
            return []
    
    def fetch_sina_minute(self, stock_code: str) -> List[Dict]:
        """从新浪财经获取分钟数据（备用）"""
        # 新浪分钟数据接口
        if stock_code.startswith('sh'):
            sina_code = 'sh' + stock_code[2:]
        elif stock_code.startswith('sz'):
            sina_code = 'sz' + stock_code[2:]
        else:
            sina_code = stock_code
        
        url = f"https://quotes.sina.cn/cn/api/quotes.php?symbol={sina_code}&type=min"
        
        try:
            response = self.session.get(url, timeout=10)
            # 解析返回数据
            return []
            
        except Exception as e:
            log.info(f"  新浪分钟数据失败: {e}")
            return []
    
    def fetch_minute_data(self, stock_code: str) -> List[Dict]:
        """获取分钟数据（主入口）"""
        log.info(f"  获取 {stock_code} 分钟数据...")
        
        # 优先腾讯
        data = self.fetch_tencent_minute(stock_code)
        
        if not data:
            # 腾讯失败用新浪
            data = self.fetch_sina_minute(stock_code)
        
        log.info(f"    获取 {len(data)} 条分钟数据")
        return data
    
    def analyze_minute_trend(self, data: List[Dict]) -> Dict:
        """分析分钟线趋势，生成交易信号"""
        if not data or len(data) < 2:
            return {"signal": "数据不足", "strength": 0}
        
        # 计算关键指标
        prices = [d['price'] for d in data]
        volumes = [d['volume'] for d in data]
        
        open_price = prices[0]
        latest_price = prices[-1]
        high_price = max(prices)
        low_price = min(prices)
        
        # 涨跌幅
        change_pct = (latest_price - open_price) / open_price * 100
        
        # 成交量分析
        avg_volume = sum(volumes) / len(volumes)
        latest_volume = volumes[-1]
        volume_ratio = latest_volume / avg_volume if avg_volume > 0 else 1
        
        # 趋势判断
        if change_pct > 5 and volume_ratio > 1.5:
            signal = "强势上涨"
            strength = 5
        elif change_pct > 3:
            signal = "温和上涨"
            strength = 4
        elif change_pct > 0:
            signal = "小幅上涨"
            strength = 3
        elif change_pct > -3:
            signal = "小幅下跌"
            strength = 2
        elif change_pct > -5:
            signal = "温和下跌"
            strength = 1
        else:
            signal = "强势下跌"
            strength = 0
        
        # 计算支撑位和压力位（简单移动平均）
        if len(prices) >= 20:
            ma20 = sum(prices[-20:]) / 20
        else:
            ma20 = sum(prices) / len(prices)
        
        return {
            "signal": signal,
            "strength": strength,
            "change_pct": round(change_pct, 2),
            "open": open_price,
            "latest": latest_price,
            "high": high_price,
            "low": low_price,
            "ma20": round(ma20, 2),
            "volume_ratio": round(volume_ratio, 2),
            "data_points": len(data)
        }


def fetch_and_analyze(stock_code: str) -> Dict:
    """获取并分析分钟数据"""
    fetcher = MinuteDataFetcher()
    
    # 获取分钟数据
    minute_data = fetcher.fetch_minute_data(stock_code)
    
    # 分析趋势
    analysis = fetcher.analyze_minute_trend(minute_data)
    
    return {
        "stock_code": stock_code,
        "minute_data": minute_data,
        "analysis": analysis,
        "update_time": datetime.now().isoformat()
    }


if __name__ == '__main__':
    import sys
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent/../ "utils"))
from agent_logger import get_logger

log = get_logger("北风")

    
    stock_code = sys.argv[1] if len(sys.argv) > 1 else "sz300480"
    
    log.info("=" * 60)
    log.info(f"🌪️ 北风 - 分钟数据抓取")
    log.info("=" * 60)
    
    result = fetch_and_analyze(stock_code)
    
    log.info(f"\n股票: {result['stock_code']}")
    log.info(f"更新时间: {result['update_time']}")
    log.info(f"\n分钟数据: {len(result['minute_data'])} 条")
    
    if result['minute_data']:
        log.info(f"\n最新5条:")
        for d in result['minute_data'][-5:]:
            log.info(f"  {d['time']} 价格:{d['price']} 量:{d['volume']}")
    
    log.info(f"\n趋势分析:")
    analysis = result['analysis']
    log.info(f"  信号: {analysis.get('signal', 'N/A')}")
    log.info(f"  涨跌幅: {analysis.get('change_pct', 0)}%")
    log.info(f"  开盘: {analysis.get('open', 0)}")
    log.info(f"  最新: {analysis.get('latest', 0)}")
    log.info(f"  最高: {analysis.get('high', 0)}")
    log.info(f"  最低: {analysis.get('low', 0)}")
    log.info(f"  量比: {analysis.get('volume_ratio', 0)}")
