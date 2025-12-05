"""
动态API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import DynamicResponse, BiliCookie


class DynamicAPI:
    """动态API"""
    
    # API端点
    DYNAMIC_ALL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/feed/all"
    DYNAMIC_DETAIL = "https://api.bilibili.com/x/polymer/web-dynamic/v1/detail"
    
    def __init__(self, client: BiliClient):
        """
        初始化动态API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def get_dynamic_all(
        self,
        host_mid: Optional[int] = None,
        offset: Optional[str] = None,
        update_baseline: Optional[str] = None,
        cookies: Optional[BiliCookie] = None
    ) -> Optional[DynamicResponse]:
        """
        获取全部动态列表
        Args:
            host_mid: UP主UID（可选，不填则获取全部动态）
            offset: 分页偏移量
            update_baseline: 更新基线
            cookies: 用户Cookie（可选，某些动态需要登录）
        Returns:
            DynamicResponse
        """
        params = {
            "platform": "web",
            "features": "itemOpusStyle,listOnlyfans,opusBigCover,onlyfansVote,decorationCard,"
                        "onlyfansAssetsV2,forwardListHidden,ugcDelete",
            "web_location": "333.1365"
        }
        
        if host_mid:
            params["host_mid"] = host_mid
        if offset:
            params["offset"] = offset
        if update_baseline:
            params["update_baseline"] = update_baseline
        
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
                self.DYNAMIC_ALL,
                api_type="dynamic",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            return DynamicResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("DynamicAPI", f"获取动态列表失败: {e}")
            return None
    
    async def get_dynamic_detail(
        self,
        dynamic_id: str,
        cookies: Optional[BiliCookie] = None
    ) -> Optional[DynamicResponse]:
        """
        获取动态详情
        Args:
            dynamic_id: 动态ID
            cookies: 用户Cookie（可选）
        Returns:
            DynamicResponse（data中包含item字段）
        """
        params = {
            "id": dynamic_id,
            "timezone_offset": -480,
            "platform": "web",
            "features": "itemOpusStyle,opusBigCover,onlyfansVote,endFooterHidden,decorationCard,"
                        "onlyfansAssetsV2,ugcDelete,onlyfansQaCard,commentsNewVersion",
            "web_location": "333.1368"
        }
        
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
                self.DYNAMIC_DETAIL,
                api_type="dynamic",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            return DynamicResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("DynamicAPI", f"获取动态详情失败: {e}")
            return None

