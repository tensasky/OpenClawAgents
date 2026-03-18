#!/usr/bin/env python3
"""
流控模块 - 限流器+断路器
用于保护系统稳定性

功能:
1. RateLimiter - 限流器，控制请求频率
2. CircuitBreaker - 断路器，防止故障扩散
3. FlowController - 统一流控管理器
"""

import time
import threading
from typing import Callable, Any, Optional
from collections import deque
from datetime import datetime, timedelta
from enum import Enum

# 日志
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from utils.agent_logger import get_logger

log = get_logger("流控")


class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 断开
    HALF_OPEN = "half_open"  # 半开


class RateLimiter:
    """限流器 - 滑动窗口"""
    
    def __init__(self, max_calls: int, window_seconds: int):
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls = deque()
        self.lock = threading.Lock()
    
    def allow(self) -> bool:
        """是否允许请求"""
        with self.lock:
            now = time.time()
            
            # 清理过期记录
            while self.calls and self.calls[0] < now - self.window_seconds:
                self.calls.popleft()
            
            # 检查是否超限
            if len(self.calls) >= self.max_calls:
                return False
            
            # 记录请求
            self.calls.append(now)
            return True
    
    def wait_and_allow(self, max_wait: float = 1.0) -> bool:
        """等待并允许(带超时)"""
        start = time.time()
        
        while time.time() - start < max_wait:
            if self.allow():
                return True
            time.sleep(0.01)
        
        return False
    
    def get_remaining(self) -> int:
        """剩余可用次数"""
        with self.lock:
            now = time.time()
            while self.calls and self.calls[0] < now - self.window_seconds:
                self.calls.popleft()
            return self.max_calls - len(self.calls)


class CircuitBreaker:
    """断路器"""
    
    def __init__(
        self, 
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        
        self.lock = threading.Lock()
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """执行函数(带断路器)"""
        with self.lock:
            # 检查状态
            if self.state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self.state = CircuitState.HALF_OPEN
                    log.info("断路器: 进入半开状态")
                else:
                    raise CircuitOpenError("断路器已打开")
            
            # 执行函数
            try:
                result = func(*args, **kwargs)
                self._on_success()
                return result
            except Exception as e:
                self._on_failure()
                raise
    
    def _should_attempt_recovery(self) -> bool:
        """是否应该尝试恢复"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout
    
    def _on_success(self):
        """成功回调"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.success_count = 0
                log.success("断路器: 已关闭，系统恢复正常")
    
    def _on_failure(self):
        """失败回调"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            log.warning("断路器: 半开状态失败，重新打开")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log.warning(f"断路器: 打开 (失败{self.failure_count}次)")
    
    def get_state(self) -> str:
        """获取状态"""
        return self.state.value


class FlowController:
    """统一流控管理器"""
    
    # 全局限流器
    _global_limiters = {}
    _global_breakers = {}
    _lock = threading.Lock()
    
    @classmethod
    def get_limiter(cls, name: str, max_calls: int = 10, window: int = 60) -> RateLimiter:
        """获取限流器"""
        with cls._lock:
            if name not in cls._global_limiters:
                cls._global_limiters[name] = RateLimiter(max_calls, window)
            return cls._global_limiters[name]
    
    @classmethod
    def get_breaker(cls, name: str, threshold: int = 5) -> CircuitBreaker:
        """获取断路器"""
        with cls._lock:
            if name not in cls._global_breakers:
                cls._global_breakers[name] = CircuitBreaker(failure_threshold=threshold)
            return cls._global_breakers[name]
    
    @classmethod
    def rate_limit(cls, name: str, max_calls: int = 10, window: int = 60):
        """限流装饰器"""
        limiter = cls.get_limiter(name, max_calls, window)
        
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                if not limiter.allow():
                    log.warning(f"限流触发: {name}")
                    raise RateLimitError(f"请求过于频繁: {name}")
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    @classmethod
    def circuit_break(cls, name: str, threshold: int = 5):
        """断路器装饰器"""
        breaker = cls.get_breaker(name, threshold)
        
        def decorator(func: Callable):
            def wrapper(*args, **kwargs):
                return breaker.call(func, *args, **kwargs)
            return wrapper
        return decorator
    
    @classmethod
    def status(cls) -> dict:
        """获取流控状态"""
        return {
            'limiters': {
                name: {'max': l.max_calls, 'remaining': l.get_remaining()}
                for name, l in cls._global_limiters.items()
            },
            'breakers': {
                name: b.get_state()
                for name, b in cls._global_breakers.items()
            }
        }


# 异常类
class RateLimitError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


# ============ 集成到事件驱动 ============

class ControlledSignalPublisher:
    """带流控的信号发布器"""
    
    def __init__(self):
        from utils.event_bus import SignalPublisher
        
        self.publisher = SignalPublisher()
        # 限流: 每秒最多10个信号
        self.rate_limiter = FlowController.get_limiter('signal_publish', 10, 1)
        # 断路器: 连续5次失败断开
        self.breaker = FlowController.get_breaker('signal_publish', 5)
    
    def publish_signal(self, signal: dict) -> bool:
        """发布信号(带流控)"""
        try:
            # 限流检查
            if not self.rate_limiter.allow():
                log.warning(f"信号发布限流: {signal.get('code')}")
                return False
            
            # 断路器保护
            return self.breaker.call(self._do_publish, signal)
            
        except CircuitOpenError:
            log.error("断路器打开，暂停信号发布")
            return False
        except RateLimitError:
            return False
        except Exception as e:
            log.error(f"信号发布失败: {e}")
            return False
    
    def _do_publish(self, signal: dict) -> bool:
        """实际发布"""
        return self.publisher.publish_signal(signal)


class ControlledSignalSubscriber:
    """带流控的信号订阅器"""
    
    def __init__(self):
        from utils.event_bus import SignalSubscriber
        
        self.subscriber = SignalSubscriber()
        # 限流: 处理最多100个/分钟
        self.rate_limiter = FlowController.get_limiter('signal_process', 100, 60)
        # 断路器
        self.breaker = FlowController.get_breaker('signal_process', 10)
        
        # 包装回调
        self._original_callbacks = []
    
    def subscribe(self, callback: Callable):
        """注册回调(带流控)"""
        def controlled_callback(signal):
            if not self.rate_limiter.allow():
                log.warning(f"信号处理限流，跳过: {signal.get('code')}")
                return
            
            try:
                self.breaker.call(callback, signal)
            except CircuitOpenError:
                log.error("信号处理断路器打开，暂停处理")
            except Exception as e:
                log.error(f"信号处理失败: {e}")
        
        self._original_callbacks.append(callback)
        self.subscriber.subscribe(controlled_callback)
    
    def start(self):
        self.subscriber.start()
    
    def stop(self):
        self.subscriber.stop()


# ============ 测试 ============

if __name__ == '__main__':
    print("=== 流控模块测试 ===")
    
    # 测试限流器
    limiter = RateLimiter(3, 10)
    for i in range(5):
        print(f"请求{i+1}: {'允许' if limiter.allow() else '拒绝'}")
    
    print("\n=== 流控状态 ===")
    print(FlowController.status())
    
    print("\n=== 测试完成 ===")
