"""
重试装饰器和错误恢复机制
"""
import asyncio
import functools
from typing import Callable, TypeVar, Optional, List, Type, Awaitable
from datetime import datetime, timedelta

from infra.logger import logger
from ..exceptions import BiliException, BiliNetworkException, BiliRateLimitException

T = TypeVar('T')


def retry_on_exception(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable[[Exception, int], None]] = None
):
    """
    重试装饰器
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
        exceptions: 需要重试的异常类型
        on_retry: 重试时的回调函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries - 1:
                        if on_retry:
                            on_retry(e, attempt + 1)
                        else:
                            logger.warn(
                                "Retry",
                                f"{func.__name__} 失败，{current_delay}秒后重试 ({attempt + 1}/{max_retries}): {e}"
                            )
                        
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error("Retry", f"{func.__name__} 重试 {max_retries} 次后仍然失败")
                        raise
            
            if last_exception:
                raise last_exception
        
        return wrapper
    return decorator


def retry_on_bili_exception(max_retries: int = 3):
    """针对B站异常的专用重试装饰器"""
    return retry_on_exception(
        max_retries=max_retries,
        delay=2.0,
        backoff=2.0,
        exceptions=(BiliNetworkException, BiliRateLimitException),
        on_retry=lambda e, attempt: logger.warn(
            "Retry",
            f"B站请求失败，正在重试 ({attempt}/{max_retries}): {e.message}"
        )
    )


class CircuitBreaker:
    """熔断器（同步版本，异步版本需要单独实现）"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        初始化熔断器
        Args:
            failure_threshold: 失败阈值
            recovery_timeout: 恢复超时时间（秒）
            expected_exception: 预期的异常类型
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half_open
    
    async def call_async(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        """
        通过熔断器异步调用函数
        Args:
            func: 要调用的异步函数
            *args: 位置参数
            **kwargs: 关键字参数
        Returns:
            函数返回值
        """
        if self.state == "open":
            # 检查是否可以进入半开状态
            if self.last_failure_time:
                elapsed = (datetime.now() - self.last_failure_time).total_seconds()
                if elapsed >= self.recovery_timeout:
                    self.state = "half_open"
                    self.failure_count = 0
                else:
                    raise BiliException("熔断器处于开启状态，请求被拒绝")
        
        try:
            result = await func(*args, **kwargs)
            # 成功调用，重置失败计数
            if self.state == "half_open":
                self.state = "closed"
            self.failure_count = 0
            return result
        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()
            
            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.warn(
                    "CircuitBreaker",
                    f"熔断器开启，失败次数: {self.failure_count}"
                )
            
            raise

