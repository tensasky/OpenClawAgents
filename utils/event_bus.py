#!/usr/bin/env python3
"""
事件驱动模块 - Redis Pub/Sub
实现信号实时推送

功能:
1. 发布信号 - 红中生成信号后立即推送
2. 订阅信号 - 发财实时接收并执行
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime

# Redis (可选依赖)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis未安装，使用数据库轮询模式")

# 日志
import sys
sys.path.insert(0, str(Path(__file__).parent))
from utils.agent_logger import get_logger

log = get_logger("事件驱动")

# 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
CHANNEL_SIGNALS = 'trade_signals'
CHANNEL_ALERTS = 'system_alerts'

# 数据库轮询间隔(秒)
POLL_INTERVAL = 5


class SignalPublisher:
    """信号发布器"""
    
    def __init__(self, use_redis: bool = True):
        self.use_redis = use_redis and REDIS_AVAILABLE
        
        if self.use_redis:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                self.redis.ping()
                log.success("Redis连接成功")
            except Exception as e:
                log.warning(f"Redis连接失败: {e}，使用数据库模式")
                self.use_redis = False
        else:
            log.info("使用数据库轮询模式")
    
    def publish_signal(self, signal: Dict) -> bool:
        """发布交易信号"""
        # 限流检查
        limiter = FlowController.get_limiter('signal_publish', 20, 1)
        if not limiter.allow():
            log.warning(f'信号发布限流: {signal.get("code")}')
            return False
        
        signal['timestamp'] = datetime.now().isoformat()
        signal_json = json.dumps(signal, ensure_ascii=False)
        
        if self.use_redis:
            try:
                self.redis.publish(CHANNEL_SIGNALS, signal_json)
                log.success(f"已发布信号: {signal.get('code')} {signal.get('name')}")
                return True
            except Exception as e:
                log.error(f"发布失败: {e}")
        
        # 降级: 写入数据库
        self._save_to_db(signal)
        return False
    
    def publish_alert(self, alert_type: str, message: str) -> bool:
        """发布系统告警"""
        alert = {
            'type': alert_type,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.use_redis:
            try:
                self.redis.publish(CHANNEL_ALERTS, json.dumps(alert))
                return True
            except:
                pass
        
        return False
    
    def _save_to_db(self, signal: Dict):
        """降级: 保存到数据库"""
        import sqlite3
        
        db_path = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
        
        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO signals (
                    timestamp, stock_code, stock_name, strategy, version,
                    entry_price, stop_loss, target_1, target_2, score, sent_discord
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                signal.get('timestamp'),
                signal.get('code'),
                signal.get('name'),
                signal.get('strategy', ''),
                signal.get('version', ''),
                signal.get('entry_price', 0),
                signal.get('stop_loss', 0),
                signal.get('target_1', 0),
                signal.get('target_2', 0),
                signal.get('score', 0)
            ))
            
            conn.commit()
            conn.close()
            
            log.info(f"信号已保存到数据库: {signal.get('code')}")
            
        except Exception as e:
            log.error(f"数据库保存失败: {e}")


class SignalSubscriber:
    """信号订阅器"""
    
    def __init__(self, use_redis: bool = True):
        self.use_redis = use_redis and REDIS_AVAILABLE
        self.callbacks: List[Callable] = []
        self.running = False
        self.thread = None
        
        if self.use_redis:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                self.redis.ping()
                log.success("Redis订阅器连接成功")
            except Exception as e:
                log.warning(f"Redis连接失败: {e}，使用数据库轮询模式")
                self.use_redis = False
    
    def subscribe(self, callback: Callable):
        """注册信号回调"""
        self.callbacks.append(callback)
        log.info(f"已注册回调: {callback.__name__}")
    
    def start(self):
        """开始监听"""
        self.running = True
        
        if self.use_redis:
            self.thread = threading.Thread(target=self._listen_redis, daemon=True)
        else:
            self.thread = threading.Thread(target=self._poll_database, daemon=True)
        
        self.thread.start()
        log.success("信号监听已启动")
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log.info("信号监听已停止")
    
    def _listen_redis(self):
        """Redis监听模式"""
        pubsub = self.redis.pubsub()
        pubsub.subscribe(CHANNEL_SIGNALS)
        
        for message in pubsub.listen():
            if not self.running:
                break
            
            if message['type'] == 'message':
                try:
                    signal = json.loads(message['data'])
                    self._dispatch(signal)
                except Exception as e:
                    log.error(f"解析信号失败: {e}")
    
    def _poll_database(self):
        """数据库轮询模式(降级)"""
        import sqlite3
        from utils.db_pool import get_pool
        
        db_path = Path.home() / "Documents/OpenClawAgents/hongzhong/data/signals_v3.db"
        last_id = 0
        
        while self.running:
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT * FROM signals 
                    WHERE id > ? AND sent_discord = 0
                    ORDER BY id DESC LIMIT 10
                """, (last_id,))
                
                rows = cursor.fetchall()
                
                if rows:
                    last_id = rows[-1][0]
                    
                    for row in rows:
                        signal = {
                            'code': row[2],
                            'name': row[3],
                            'strategy': row[4],
                            'entry_price': row[6],
                            'stop_loss': row[7],
                            'score': row[10]
                        }
                        self._dispatch(signal)
                
                conn.close()
                
            except Exception as e:
                log.error(f"轮询失败: {e}")
            
            time.sleep(POLL_INTERVAL)
    
    def _dispatch(self, signal: Dict):
        """分发信号到回调"""
        log.success(f"收到信号: {signal.get('code')} {signal.get('name')}")
        
        for callback in self.callbacks:
            try:
                callback(signal)
            except Exception as e:
                log.error(f"回调失败 {callback.__name__}: {e}")


# ============ 便捷函数 ============

def create_publisher() -> SignalPublisher:
    """创建发布器"""
    return SignalPublisher()


def create_subscriber() -> SignalSubscriber:
    """创建订阅器"""
    return SignalSubscriber()


# ============ 测试 ============

if __name__ == '__main__':
    print("=== 信号发布测试 ===")
    
    publisher = create_publisher()
    
    # 测试信号
    test_signal = {
        'code': 'sh600519',
        'name': '贵州茅台',
        'strategy': '测试策略',
        'entry_price': 1500.0,
        'stop_loss': 1425.0,
        'score': 85.0
    }
    
    publisher.publish_signal(test_signal)
    
    print("=== 信号订阅测试 ===")
    
    def on_signal(sig):
        print(f"收到信号: {sig}")
    
    subscriber = create_subscriber()
    subscriber.subscribe(on_signal)
    subscriber.start()
    
    # 监听10秒
    time.sleep(10)
    subscriber.stop()
