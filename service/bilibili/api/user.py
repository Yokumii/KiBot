"""
用户API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import UserInfoResponse, BiliCookie


class UserAPI:
    """用户API"""
    
    # API端点
    SPACE_INFO = "https://api.bilibili.com/x/space/wbi/acc/info"
    
    def __init__(self, client: BiliClient):
        """
        初始化用户API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def get_user_info(
        self,
        mid: int,
        cookies: Optional[BiliCookie] = None
    ) -> Optional[UserInfoResponse]:
        """
        获取用户空间详细信息
        Args:
            mid: 用户UID
            cookies: 用户Cookie（可选，某些信息需要登录）
        Returns:
            UserInfoResponse
        """
        params = {"mid": mid}
        
        cookie_dict = None
        if cookies:
            cookie_dict = {
                "SESSDATA": cookies.SESSDATA,
                "bili_jct": cookies.bili_jct,
                "DedeUserID": cookies.DedeUserID,
                "DedeUserID__ckMd5": cookies.DedeUserID__ckMd5
            }
        
        try:
            response = await self.client.get(
                self.SPACE_INFO,
                api_type="user",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            return UserInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("UserAPI", f"获取用户信息失败: {e}")
            return None

