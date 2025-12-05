"""
登录API封装
"""
import asyncio
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

from ..client import BiliClient
from ..models import (
    QRCodeGenerateResponse, QRCodePollResponse,
    BiliCookie, CookieInfoResponse, CookieRefreshResponse,
    CookieConfirmResponse
)


class LoginAPI:
    """登录API"""
    
    # API端点
    QRCODE_GENERATE = "https://passport.bilibili.com/x/passport-login/web/qrcode/generate"
    QRCODE_POLL = "https://passport.bilibili.com/x/passport-login/web/qrcode/poll"
    COOKIE_INFO = "https://passport.bilibili.com/x/passport-login/web/cookie/info"
    COOKIE_REFRESH = "https://passport.bilibili.com/x/passport-login/web/cookie/refresh"
    COOKIE_CONFIRM = "https://passport.bilibili.com/x/passport-login/web/confirm/refresh"
    
    def __init__(self, client: BiliClient):
        """
        初始化登录API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def generate_qrcode(self) -> Optional[Tuple[str, str]]:
        """
        生成登录二维码
        Returns:
            (qr_url, qrcode_key)
        """
        try:
            response = await self.client.get(
                self.QRCODE_GENERATE,
                api_type="login"
            )
            data = response.json()
            qr_response = QRCodeGenerateResponse(**data)
            
            if qr_response.code != 0 or not qr_response.data:
                return None
            
            return qr_response.data.url, qr_response.data.qrcode_key
        except Exception as e:
            from infra.logger import logger
            logger.warn("LoginAPI", f"生成二维码失败: {e}")
            return None
    
    async def poll_qrcode(self, qrcode_key: str) -> Optional[QRCodePollResponse]:
        """
        轮询扫码登录状态
        Args:
            qrcode_key: 二维码key
        Returns:
            QRCodePollResponse
        """
        params = {"qrcode_key": qrcode_key}
        
        try:
            response = await self.client.get(
                self.QRCODE_POLL,
                api_type="login",
                params=params
            )
            data = response.json()
            return QRCodePollResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("LoginAPI", f"轮询二维码失败: {e}")
            return None
    
    @staticmethod
    def extract_cookies_from_url(url: str) -> Optional[BiliCookie]:
        """
        从登录成功返回的URL中提取Cookie信息
        Args:
            url: 登录成功后的URL
        Returns:
            BiliCookie
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
                return BiliCookie(**cookie_dict)
            else:
                from infra.logger import logger
                logger.warn("LoginAPI", "URL中缺少必需的Cookie参数")
                return None
        except Exception as e:
            from infra.logger import logger
            logger.warn("LoginAPI", f"从URL解析Cookie失败: {e}")
            return None
    
    async def wait_for_login(
        self,
        qrcode_key: str,
        timeout: int = 180
    ) -> Optional[Tuple[BiliCookie, str]]:
        """
        等待用户扫码登录
        Args:
            qrcode_key: 二维码key
            timeout: 超时时间（秒）
        Returns:
            (BiliCookie, refresh_token)
        """
        start_time = asyncio.get_event_loop().time()
        
        while True:
            # 检查超时
            if asyncio.get_event_loop().time() - start_time > timeout:
                from infra.logger import logger
                logger.warn("LoginAPI", "二维码登录超时")
                return None
            
            # 轮询
            poll_response = await self.poll_qrcode(qrcode_key)
            if not poll_response:
                await asyncio.sleep(2)
                continue
            
            if poll_response.code != 0:
                from infra.logger import logger
                logger.warn("LoginAPI", f"轮询失败: {poll_response.message}")
                await asyncio.sleep(2)
                continue
            
            if not poll_response.data:
                await asyncio.sleep(2)
                continue
            
            if poll_response.data.code == 0:
                # 登录成功
                from infra.logger import logger
                logger.info("LoginAPI", "扫码登录成功，获取Cookie和refresh_token...")
                cookies = self.extract_cookies_from_url(poll_response.data.url)
                if cookies:
                    refresh_token = poll_response.data.refresh_token
                    if not refresh_token:
                        logger.warn("LoginAPI", "无法提取refresh_token")
                        return None
                    return cookies, refresh_token
                else:
                    logger.warn("LoginAPI", "无法提取Cookie")
                    return None
            elif poll_response.data.code == 86038:
                from infra.logger import logger
                logger.warn("LoginAPI", "二维码已失效")
                return None
            elif poll_response.data.code == 86090:
                from infra.logger import logger
                logger.info("LoginAPI", "二维码已扫码，等待确认...")
            elif poll_response.data.code == 86101:
                from infra.logger import logger
                logger.info("LoginAPI", "等待扫码...")
            else:
                from infra.logger import logger
                logger.warn("LoginAPI", f"未知状态码: {poll_response.data.code}")
            
            await asyncio.sleep(2)
    
    async def check_cookie_refresh_needed(
        self,
        cookies: BiliCookie
    ) -> Optional[Tuple[bool, int]]:
        """
        检查是否需要刷新Cookie
        Args:
            cookies: 当前Cookie
        Returns:
            (need_refresh, timestamp)
        """
        url = self.COOKIE_INFO
        params = {"csrf": cookies.bili_jct}
        
        cookie_dict = {
            "SESSDATA": cookies.SESSDATA,
            "bili_jct": cookies.bili_jct,
            "DedeUserID": cookies.DedeUserID,
            "DedeUserID__ckMd5": cookies.DedeUserID__ckMd5
        }
        
        try:
            response = await self.client.get(
                url,
                api_type="login",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            info_response = CookieInfoResponse(**data)
            
            if info_response.code != 0 or not info_response.data:
                return None
            
            return info_response.data.refresh, info_response.data.timestamp
        except Exception as e:
            from infra.logger import logger
            logger.warn("LoginAPI", f"检查Cookie刷新状态失败: {e}")
            return None

