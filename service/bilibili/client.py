"""
Bilibili HTTP 客户端（增强版）
支持限流、重试、连接池、WBI签名等功能
"""
import asyncio
import httpx
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlparse, parse_qs

from infra.logger import logger
from .models import NavInfoResponse, WbiImages
from .exceptions import BiliAPIException, BiliNetworkException, raise_for_code
from .utils.rate_limiter import RateLimiter
from .utils.wbi_sign import extract_wbi_keys, generate_wbi_sign
from .utils.cache import ResponseCache


class BiliClient:
    """
    Bilibili HTTP客户端
    支持多客户端连接池、请求限流、自动重试、WBI签名等功能
    """
    
    def __init__(
        self,
        timeout: float = 15.0,
        connect_timeout: float = 5.0,
        api_interval: float = 10.0,
        max_retries: int = 3,
        client_pool_size: int = 3
    ):
        """
        初始化客户端
        Args:
            timeout: 请求超时时间（秒）
            connect_timeout: 连接超时时间（秒）
            api_interval: API访问间隔（秒）
            max_retries: 最大重试次数
            client_pool_size: 客户端连接池大小
        """
        self.base_url = "https://passport.bilibili.com"
        self.api_base_url = "https://api.bilibili.com"
        self.live_api_base_url = "https://api.live.bilibili.com"
        
        self.timeout = httpx.Timeout(timeout, connect=connect_timeout)
        self.rate_limiter = RateLimiter(interval=api_interval)
        self.max_retries = max_retries
        
        # 创建客户端连接池
        self.clients: List[httpx.AsyncClient] = []
        self.current_client_index = 0
        self._init_clients(client_pool_size)
        
        # WBI签名相关
        self._wbi_img_key: Optional[str] = None
        self._wbi_sub_key: Optional[str] = None
        self._wbi_salt: Optional[str] = None
        
        # 响应缓存（可选）
        self.cache: Optional[ResponseCache] = None
        self.cache_enabled = False
    
    def enable_cache(self, default_ttl: int = 300, max_size: int = 1000):
        """
        启用响应缓存
        Args:
            default_ttl: 默认缓存时间（秒）
            max_size: 最大缓存条目数
        """
        self.cache = ResponseCache(default_ttl=default_ttl, max_size=max_size)
        self.cache_enabled = True
    
    def disable_cache(self):
        """禁用响应缓存"""
        self.cache_enabled = False
        if self.cache:
            self.cache.clear()
            self.cache = None
    
    def _init_clients(self, pool_size: int):
        """初始化客户端连接池"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "keep-alive",
            "Referer": "https://www.bilibili.com/",
        }
        
        for _ in range(pool_size):
            client = httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout,
                follow_redirects=True,
                http2=True  # 启用HTTP/2
            )
            self.clients.append(client)
    
    def _get_client(self) -> httpx.AsyncClient:
        """获取当前客户端（轮询）"""
        client = self.clients[self.current_client_index]
        self.current_client_index = (self.current_client_index + 1) % len(self.clients)
        return client
    
    async def _get_wbi_keys(self) -> Tuple[Optional[str], Optional[str]]:
        """
        获取WBI签名密钥
        Returns:
            (img_key, sub_key)
        """
        if self._wbi_img_key and self._wbi_sub_key:
            return self._wbi_img_key, self._wbi_sub_key
        
        try:
            url = f"{self.api_base_url}/x/web-interface/nav"
            client = self._get_client()
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                nav_response = NavInfoResponse(**data)
                if nav_response.data and nav_response.data.wbi_img:
                    img_key, sub_key = extract_wbi_keys(
                        nav_response.data.wbi_img.img_url,
                        nav_response.data.wbi_img.sub_url
                    )
                    self._wbi_img_key = img_key
                    self._wbi_sub_key = sub_key
                    return img_key, sub_key
        except Exception as e:
            logger.warn("BiliClient", f"获取WBI密钥失败: {e}")
        
        return None, None
    
    def _should_use_wbi(self, url: str) -> bool:
        """判断URL是否需要WBI签名"""
        return "wbi" in url.lower()
    
    async def _add_wbi_sign(self, params: Dict[str, Any], url: str) -> Dict[str, Any]:
        """
        为参数添加WBI签名
        Args:
            params: 原始参数
            url: 请求URL
        Returns:
            添加了w_rid和wts的参数
        """
        if not self._should_use_wbi(url):
            return params
        
        img_key, sub_key = await self._get_wbi_keys()
        if not img_key or not sub_key:
            logger.warn("BiliClient", "WBI密钥获取失败，跳过签名")
            return params
        
        sign_params = generate_wbi_sign(params, img_key, sub_key)
        return {**params, **sign_params}
    
    async def request(
        self,
        method: str,
        url: str,
        api_type: str = "default",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_cache: bool = True,
        cache_ttl: Optional[int] = None,
        **kwargs
    ) -> httpx.Response:
        """
        发送HTTP请求（带限流和重试）
        Args:
            method: HTTP方法
            url: 请求URL
            api_type: API类型（用于限流）
            params: URL参数
            data: 请求体数据
            cookies: Cookie
            headers: 额外请求头
            use_cache: 是否使用缓存（仅GET请求）
            cache_ttl: 缓存时间（秒），None则使用默认值
            **kwargs: 其他httpx参数
        Returns:
            HTTP响应
        Raises:
            BiliAPIException: API返回错误
        """
        # 注意：缓存功能需要特殊处理，因为需要构造Response对象
        # 这里暂时不实现缓存响应返回，只缓存JSON数据用于后续优化
        
        # 等待限流
        await self.rate_limiter.wait(api_type)
        
        # 处理WBI签名
        if params and self._should_use_wbi(url):
            params = await self._add_wbi_sign(params, url)
        
        client = self._get_client()
        
        # 重试机制
        last_exception = None
        for attempt in range(self.max_retries):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    data=data,
                    cookies=cookies,
                    headers=headers,
                    **kwargs
                )
                
                # 检查响应状态
                if response.status_code != 200:
                    raise_for_code(
                        response.status_code,
                        f"HTTP {response.status_code}",
                        url
                    )
                
                # 检查业务错误码
                try:
                    json_data = response.json()
                    code = json_data.get("code", 0)
                    if code != 0:
                        message = json_data.get("message", "未知错误")
                        raise_for_code(code, message, url)
                except (ValueError, KeyError):
                    # 不是JSON响应或格式不对，继续返回原始响应
                    pass
                
                # 缓存响应（仅GET请求且成功）
                if method.upper() == "GET" and use_cache and self.cache_enabled and self.cache:
                    try:
                        # 缓存JSON数据
                        json_data = response.json()
                        self.cache.set(url, json_data, params, cache_ttl)
                    except (ValueError, AttributeError):
                        # 不是JSON响应，不缓存
                        pass
                
                return response
                
            except (httpx.TimeoutException, httpx.NetworkError) as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避
                    logger.warn(
                        "BiliClient",
                        f"请求失败，{wait_time}秒后重试 ({attempt + 1}/{self.max_retries}): {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise BiliNetworkException(f"请求失败: {e}") from e
            except BiliAPIException:
                raise
            except Exception as e:
                raise BiliAPIException(-1, f"未知错误: {e}", url) from e
        
        if last_exception:
            raise BiliNetworkException(f"请求失败: {last_exception}") from last_exception
    
    async def get(
        self,
        url: str,
        api_type: str = "default",
        params: Optional[Dict[str, Any]] = None,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """发送GET请求"""
        return await self.request(
            "GET", url, api_type=api_type,
            params=params, cookies=cookies, headers=headers, **kwargs
        )
    
    async def post(
        self,
        url: str,
        api_type: str = "default",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        cookies: Optional[Dict[str, str]] = None,
        headers: Optional[Dict[str, str]] = None,
        **kwargs
    ) -> httpx.Response:
        """发送POST请求"""
        return await self.request(
            "POST", url, api_type=api_type,
            params=params, data=data, cookies=cookies, headers=headers, **kwargs
        )

    @staticmethod
    def extract_cookies_from_url(url: str) -> Optional[Dict[str, str]]:
        """
        从登录成功返回的URL中提取Cookie信息
        Args:
            url: 登录成功后的URL
        Returns:
            Cookie字典
        """
        try:
            parsed_url = urlparse(url)
            query_params = parse_qs(parsed_url.query)

            cookie_dict = {
                'DedeUserID': query_params.get('DedeUserID', [''])[0],
                'DedeUserID__ckMd5': query_params.get('DedeUserID__ckMd5', [''])[0],
                'SESSDATA': query_params.get('SESSDATA', [''])[0],
                'bili_jct': query_params.get('bili_jct', [''])[0]
            }

            # 验证所有必需的cookie字段是否存在且不为空
            if all(cookie_dict.values()):
                return cookie_dict
            else:
                logger.warn("BiliClient", "URL中缺少必需的Cookie参数")
                return None
        except Exception as e:
            logger.warn("BiliClient", f"从URL解析Cookie失败: {e}")
            return None

    async def close(self):
        """关闭所有客户端"""
        for client in self.clients:
            await client.aclose()
        self.clients.clear()
