"""
Bilibili API 请求限流器
参考 bilibili-helper 的 BiliApiMutex 实现
"""
import asyncio
import time
from typing import Dict
from collections import defaultdict


class RateLimiter:
    """
    API请求限流器，防止并发请求同一API导致被反爬
    基于互斥锁机制，确保同一API类型在指定时间间隔内只请求一次
    """
    
    def __init__(self, interval: float = 10.0):
        """
        初始化限流器
        Args:
            interval: API访问间隔（秒），默认10秒
        """
        self.interval = interval
        self._last_request_time: Dict[str, float] = defaultdict(float)
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
    
    async def wait(self, api_type: str) -> None:
        """
        等待直到可以请求指定类型的API
        Args:
            api_type: API类型标识（如 'dynamic', 'video', 'live' 等）
        """
        lock = self._locks[api_type]
        async with lock:
            last_time = self._last_request_time[api_type]
            current_time = time.time()
            elapsed = current_time - last_time
            
            if elapsed < self.interval:
                wait_time = self.interval - elapsed
                await asyncio.sleep(wait_time)
            
            self._last_request_time[api_type] = time.time()
    
    def reset(self, api_type: str = None) -> None:
        """
        重置指定API类型的请求时间记录
        Args:
            api_type: API类型，如果为None则重置所有
        """
        if api_type:
            self._last_request_time[api_type] = 0.0
        else:
            self._last_request_time.clear()

