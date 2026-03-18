#!/usr/bin/env python3
"""
事件驱动模块 - Redis Streams 版
支持消息持久化和ACK确认机制
"""

import json
import time
import threading
from pathlib import Path
from typing import Dict, List, Optional, Callable
from datetime import datetime

try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    print("⚠️ Redis未安装，使用数据库轮询模式")

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_logger import get_logger

log = get_logger("事件驱动-Streams")

# 配置
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
STREAM_SIGNALS = 'trade_signals'
CONSUMER_GROUP = 'facai'
CONSUMER_NAME = 'consumer_1'


class SignalPublisher:
    """信号发布器 - Streams版"""
    
    def __init__(self):
        self.use_redis = REDIS_AVAILABLE
        
        if self.use_redis:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                self.redis.ping()
                
                # 创建消费者组(如果不存在)
                try:
                    self.redis.xgroup_create(STREAM_SIGNALS, CONSUMER_GROUP, id='0', mkstream=True)
                except:
                    pass  # 已存在
                
                log.success("Redis Streams连接成功")
            except Exception as e:
                log.warning(f"Redis连接失败: {e}，使用数据库模式")
                self.use_redis = False
        else:
            log.info("使用数据库轮询模式")
    
    def publish_signal(self, signal: Dict) -> bool:
        """发布交易信号到Stream"""
        signal['timestamp'] = datetime.now().isoformat()
        
        if self.use_redis:
            try:
                # 使用Streams添加消息
                msg_id = self.redis.xadd(STREAM_SIGNALS, signal)
                log.success(f"已发布信号: {signal.get('code')} -> {msg_id}")
                return True
            except Exception as e:
                log.error(f"Redis发布失败: {e}")
        
        # 降级: 保存到数据库
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
                self.redis.xadd('system_alerts', alert)
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
    """信号订阅器 - Streams版"""
    
    def __init__(self):
        self.use_redis = REDIS_AVAILABLE
        self.callbacks: List[Callable] = []
        self.running = False
        self.thread = None
        
        if self.use_redis:
            try:
                self.redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
                self.redis.ping()
                
                # 确保消费者组存在
                try:
                    self.redis.xgroup_create(STREAM_SIGNALS, CONSUMER_GROUP, id='0', mkstream=True)
                except:
                    pass
                
                log.success("Redis Streams订阅器连接成功")
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
            self.thread = threading.Thread(target=self._listen_streams, daemon=True)
        else:
            self.thread = threading.Thread(target=self._poll_database, daemon=True)
        
        self.thread.start()
        log.success("信号监听已启动(Streams模式)")
    
    def stop(self):
        """停止监听"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        log.info("信号监听已停止")
    
    def _listen_streams(self):
        """Streams监听模式"""
        last_id = '0'  # 从最新消息开始
        
        while self.running:
            try:
                # 读取新消息
                messages = self.redis.xread(
                    {STREAM_SIGNALS: last_id},
                    count=10,
                    block=5000  # 5秒阻塞
                )
                
                if not messages:
                    continue
                
                for stream, msgs in messages:
                    for msg_id, data in msgs:
                        last_id = msg_id
                        
                        try:
                            self._dispatch(data)
                            
                            # ACK确认
                            self.redis.xack(STREAM_SIGNALS, CONSUMER_GROUP, msg_id)
                            
                        except Exception as e:
                            log.error(f"处理消息失败: {e}")
                
            except Exception as e:
                log.error(f"Streams监听错误: {e}")
                time.sleep(1)
    
    def _poll_database(self):
        """数据库轮询模式(降级)"""
        import sqlite3
        
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
            
            time.sleep(5)
    
    def _dispatch(self, signal: Dict):
        """分发信号到回调"""
        log.success(f"收到信号: {signal.get('code')} {signal.get('name')}")
        
        for callback in self.callbacks:
            try:
                callback(signal)
            except Exception as e:
                log.error(f"回调失败 {callback.__name__}: {e}")
    
    def get_pending_messages(self) -> int:
        """获取未处理消息数量"""
        if not self.use_redis:
            return 0
        
        try:
            info = self.redis.xinfo_group(STREAM_SIGNALS)
            return info.get('pending', 0)
        except:
            return 0


# ============ 便捷函数 ============

def create_publisher() -> SignalPublisher:
    """创建发布器"""
    return SignalPublisher()


def create_subscriber() -> SignalSubscriber:
    """创建订阅器"""
    return SignalSubscriber()


# ============ 测试 ============

if __name__ == '__main__':
    print("=== Streams测试 ===")
    
    pub = create_publisher()
    
    test_signal = {
        'code': 'sh600519',
        'name': '贵州茅台',
        'strategy': '测试',
        'entry_price': 1500.0,
        'score': 85
    }
    
    pub.publish_signal(test_signal)
    
    print(f"未处理消息: {pub.redis.xinfo_group(STREAM_SIGNALS)}")
