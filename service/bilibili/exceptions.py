"""
Bilibili API 异常定义
"""
from typing import Optional


class BiliException(Exception):
    """B站异常基类"""
    def __init__(self, message: str, code: Optional[int] = None, url: str = ""):
        self.message = message
        self.code = code
        self.url = url
        super().__init__(self.message)


class BiliAPIException(BiliException):
    """B站API异常"""
    def __init__(self, code: int, message: str, url: str = ""):
        super().__init__(message, code, url)
        self.code = code
    
    def __str__(self):
        return f"BiliAPI Error {self.code}: {self.message} (URL: {self.url})"


class BiliAuthException(BiliException):
    """B站认证异常"""
    def __init__(self, message: str = "认证失败", code: int = -101):
        super().__init__(message, code)
        self.code = code


class BiliRateLimitException(BiliException):
    """B站限流异常"""
    def __init__(self, message: str = "请求过于频繁，请稍后再试", retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class BiliNetworkException(BiliException):
    """B站网络异常"""
    def __init__(self, message: str = "网络请求失败"):
        super().__init__(message)


class BiliParseException(BiliException):
    """B站解析异常"""
    def __init__(self, message: str = "解析响应失败"):
        super().__init__(message)


class BiliCookieException(BiliException):
    """B站Cookie异常"""
    def __init__(self, message: str = "Cookie无效或已过期"):
        super().__init__(message)


# 错误码映射
ERROR_CODE_MAP = {
    -101: BiliAuthException,
    -102: BiliAuthException,
    -103: BiliException,
    -104: BiliException,
    -111: BiliAuthException,
    -352: BiliRateLimitException,
    -400: BiliAPIException,
    -403: BiliAuthException,
    -404: BiliAPIException,
    -412: BiliRateLimitException,
    -500: BiliNetworkException,
    -503: BiliNetworkException,
    -504: BiliNetworkException,
}


def raise_for_code(code: int, message: str, url: str = ""):
    """
    根据错误码抛出相应的异常
    Args:
        code: 错误码
        message: 错误消息
        url: 请求URL
    """
    exception_class = ERROR_CODE_MAP.get(code, BiliAPIException)
    if exception_class == BiliAPIException:
        raise BiliAPIException(code, message, url)
    else:
        raise exception_class(message)

