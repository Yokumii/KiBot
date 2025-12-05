"""
视频API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import VideoInfoResponse, VideoSearchResult, BiliCookie


class VideoAPI:
    """视频API"""
    
    # API端点
    VIDEO_INFO = "https://api.bilibili.com/x/web-interface/wbi/view"
    VIDEO_USER = "https://api.bilibili.com/x/space/wbi/arc/search"
    
    def __init__(self, client: BiliClient):
        """
        初始化视频API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def get_video_info(
        self,
        aid: Optional[int] = None,
        bvid: Optional[str] = None,
        cookies: Optional[BiliCookie] = None
    ) -> Optional[VideoInfoResponse]:
        """
        获取视频详细信息
        Args:
            aid: 视频AV号（与bvid二选一）
            bvid: 视频BV号（与aid二选一）
            cookies: 用户Cookie（某些视频需要登录）
        Returns:
            VideoInfoResponse
        """
        if not aid and not bvid:
            raise ValueError("aid和bvid至少需要提供一个")
        
        params = {}
        if aid:
            params["aid"] = aid
        if bvid:
            params["bvid"] = bvid
        
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
                self.VIDEO_INFO,
                api_type="video",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            return VideoInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("VideoAPI", f"获取视频信息失败: {e}")
            return None
    
    async def get_user_videos(
        self,
        mid: int,
        keyword: str = "",
        page_size: int = 30,
        page_num: int = 1,
        cookies: Optional[BiliCookie] = None
    ) -> Optional[VideoSearchResult]:
        """
        获取用户视频列表
        Args:
            mid: 用户UID
            keyword: 搜索关键词（可选）
            page_size: 每页数量
            page_num: 页码
            cookies: 用户Cookie（可选）
        Returns:
            VideoSearchResult
        """
        params = {
            "mid": mid,
            "keyword": keyword,
            "order": "pubdate",
            "jsonp": "jsonp",
            "ps": page_size,
            "pn": page_num,
            "tid": 0
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
                self.VIDEO_USER,
                api_type="video",
                params=params,
                cookies=cookie_dict
            )
            data = response.json()
            return VideoSearchResult(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("VideoAPI", f"获取用户视频列表失败: {e}")
            return None

