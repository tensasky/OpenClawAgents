#!/usr/bin/env python3
"""
哨兵模块 - 心跳监测与数据对账
财神爷监控系统增强

功能:
1. 心跳监测 - 北风数据更新监控
2. 数据对账 - 持仓与账户余额校验
"""

import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime, timedelta

import sys
sys.path.insert(0, str(Path(__file__).parent))
from db_pool import get_pool
from agent_logger import get_logger
from unified_notifier import notify_alert
from flow_control import FlowController

log = get_logger("哨兵")

# 配置
DB_PATH = Path.home() / "Documents/OpenClawAgents/beifeng/data/stocks_real.db"
PORTFOLIO_PATH = Path.home() / "Documents/OpenClawAgents/facai/data/portfolio.db"

# 阈值
MINUTE_TIMEOUT = 10 * 60  # 10分钟无更新=警告
DAILY_TIMEOUT = 30 * 60    # 30分钟无日线=警告


class HeartbeatMonitor:
    """心跳监测"""
    
    def __init__(self):
        self.pool = get_pool(DB_PATH)
    
    def get_last_update(self, table: str = 'minute') -> Optional[datetime]:
        """获取最后更新时间"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute(f"""
                SELECT MAX(timestamp) FROM {table}
            """)
            row = cursor.fetchone()
            
            if row and row[0]:
                return datetime.fromisoformat(row[0])
        except Exception as e:
            log.error(f"查询失败: {e}")
        finally:
            self.pool.release_connection(conn)
        
        return None
    
    def check_minute_heartbeat(self) -> Dict:
        """检查分钟数据心跳"""
        last = self.get_last_update('minute')
        
        if not last:
            return {'status': 'critical', 'msg': '无分钟数据', 'last': None}
        
        elapsed = (datetime.now() - last).total_seconds()
        
        if elapsed > MINUTE_TIMEOUT:
            return {
                'status': 'critical' if elapsed > MINUTE_TIMEOUT * 2 else 'warning',
                'msg': f'分钟数据滞后 {elapsed/60:.1f}分钟',
                'last': last.isoformat(),
                'elapsed': elapsed
            }
        
        return {
            'status': 'ok',
            'msg': f'分钟数据正常 ({elapsed:.0f}秒前)',
            'last': last.isoformat(),
            'elapsed': elapsed
        }
    
    def check_daily_heartbeat(self) -> Dict:
        """检查日线数据心跳"""
        last = self.get_last_update('daily')
        
        if not last:
            return {'status': 'critical', 'msg': '无日线数据', 'last': None}
        
        elapsed = (datetime.now() - last).total_seconds()
        
        if elapsed > DAILY_TIMEOUT:
            return {
                'status': 'warning',
                'msg': f'日线数据滞后 {elapsed/60:.1f}分钟',
                'last': last.isoformat(),
                'elapsed': elapsed
            }
        
        return {
            'status': 'ok',
            'msg': f'日线数据正常',
            'last': last.isoformat(),
            'elapsed': elapsed
        }
    
    def run_heartbeat_check(self) -> Dict:
        """执行完整心跳检测"""
        minute = self.check_minute_heartbeat()
        daily = self.check_daily_heartbeat()
        
        # 综合状态
        if minute['status'] == 'critical' or daily['status'] == 'critical':
            status = 'critical'
        elif minute['status'] == 'warning' or daily['status'] == 'warning':
            status = 'warning'
        else:
            status = 'ok'
        
        return {
            'status': status,
            'minute': minute,
            'daily': daily,
            'timestamp': datetime.now().isoformat()
        }


class DataReconciliation:
    """数据对账"""
    
    def __init__(self):
        self.pool = get_pool(PORTFOLIO_PATH)
    
    def get_account(self) -> Optional[Dict]:
        """获取账户信息"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("SELECT * FROM account LIMIT 1")
            row = cursor.fetchone()
            
            if row:
                return {
                    'id': row[0],
                    'cash_balance': row[1],
                    'total_assets': row[2]
                }
        finally:
            self.pool.release_connection(conn)
        
        return None
    
    def get_positions_value(self) -> float:
        """计算持仓市值"""
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        total = 0.0
        try:
            cursor.execute("SELECT quantity, current_price FROM positions")
            for row in cursor.fetchall():
                total += row[0] * row[1]
        finally:
            self.pool.release_connection(conn)
        
        return total
    
    def check_reconciliation(self, tolerance: float = 100.0) -> Dict:
        """执行对账"""
        account = self.get_account()
        
        if not account:
            return {'status': 'error', 'msg': '无账户数据'}
        
        cash = account['cash_balance']
        positions_value = self.get_positions_value()
        total_assets = account['total_assets']
        
        calculated_total = cash + positions_value
        diff = abs(calculated_total - total_assets)
        
        # 使用百分比容差
        tolerance = total_assets * TOLERANCE_PCT if total_assets > 0 else 100
        
        if diff > tolerance:
            return {
                'status': 'warning',
                'msg': f'对账差异 {diff:.2f}元 ({diff/total_assets*100:.2f}%)',
                'cash': cash,
                'positions_value': positions_value,
                'total_assets': total_assets,
                'calculated_total': calculated_total,
                'diff': diff
            }
        
        return {
            'status': 'ok',
            'msg': f'对账正常 (差异{abs(diff)/total_assets*100:.3f}%)',
            'cash': cash,
            'positions_value': positions_value,
            'total_assets': total_assets,
            'calculated_total': calculated_total
        }
    
    def run_reconciliation(self) -> Dict:
        """执行完整对账"""
        return self.check_reconciliation()




class LimitDownMonitor:
    """跌停流动性监控"""
    
    def __init__(self):
        self.pool = get_pool(DB_PATH)
    
    def check_positions_limit_down(self) -> list:
        """检查持仓股是否跌停"""
        import requests
        
        conn = self.pool.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT symbol, current_price FROM positions
            WHERE quantity > 0
        """)
        
        positions = cursor.fetchall()
        self.pool.release_connection(conn)
        
        limit_down_stocks = []
        
        for symbol, current_price in positions:
            try:
                # 获取实时数据
                url = f"https://qt.gtimg.cn/q={symbol}"
                resp = requests.get(url, timeout=3)
                
                if '~' in resp.text:
                    parts = resp.text.split('~')
                    price = float(parts[3]) if parts[3] else 0
                    change_pct = float(parts[32]) if parts[32] else 0
                    
                    # 跌停检测 (-9.9%以下)
                    if change_pct <= -9.9:
                        # 获取封单量
                        volume = int(parts[36]) if parts[36] else 0
                        
                        limit_down_stocks.append({
                            'symbol': symbol,
                            'price': price,
                            'change_pct': change_pct,
                            'volume': volume,
                            'risk_level': 'HIGH' if change_pct <= -9.5 else 'MEDIUM'
                        })
                        
            except Exception as e:
                log.debug(f"检查{symbol}跌停失败: {e}")
        
        return limit_down_stocks
    
    def run_limit_down_check(self) -> dict:
        """执行跌停检查"""
        log.step("检查跌停流动性")
        
        limit_downs = self.check_positions_limit_down()
        
        if limit_downs:
            log.warning(f"发现{len(limit_downs)}只跌停股!")
            
            for stock in limit_downs:
                msg = f"🚨 跌停预警: {stock['symbol']} 跌幅{stock['change_pct']:.1f}%"
                
                if stock['risk_level'] == 'HIGH':
                    msg += " ⚠️ 封单巨大，可能无法止损"
                
                try:
                    from unified_notifier import notify_alert
                    notify_alert("哨兵-跌停", msg)
                except:
                    pass
        
        return {
            'count': len(limit_downs),
            'stocks': limit_downs
        }

class Sentinel:
    """哨兵 - 整合心跳监测与数据对账"""
    
    def __init__(self):
        self.heartbeat = HeartbeatMonitor()
        self.reconciliation = DataReconciliation()
        self.limit_down = LimitDownMonitor()
    
    def run(self) -> Dict:
        """执行完整哨兵检测"""
        log.step("🔍 哨兵检测开始")
        
        # 心跳检测
        heartbeat_result = self.heartbeat.run_heartbeat_check()
        log.info(f"心跳检测: {heartbeat_result['status']}")
        
        # 跌停流动性检查
        limit_result = self.limit_down.run_limit_down_check()
        
        # 数据对账
        recon_result = self.reconciliation.run_reconciliation()
        log.info(f"数据对账: {recon_result['status']}")
        
        # 综合结果
        if heartbeat_result['status'] == 'critical':
            self._send_alert("🚨 数据告警!", heartbeat_result)
        
        if recon_result['status'] == 'warning':
            self._send_alert("⚠️ 对账异常!", recon_result)
        
        return {
            'heartbeat': heartbeat_result,
            'reconciliation': recon_result,
            'timestamp': datetime.now().isoformat()
        }
    
    def _send_alert(self, title: str, data: Dict):
        """发送告警"""
        msg = f"{title}\n{data.get('msg', '')}"
        
        try:
            notify_alert("哨兵", msg)
            log.warning(f"已发送告警: {title}")
        except Exception as e:
            log.error(f"发送告警失败: {e}")


def run_sentinel():
    """运行哨兵"""
    sentinel = Sentinel()
    result = sentinel.run()
    
    log.success(f"✅ 哨兵检测完成: {result['heartbeat']['status']}")
    return result


if __name__ == '__main__':
    run_sentinel()
