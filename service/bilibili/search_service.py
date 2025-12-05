"""
B站搜索服务
"""
import inspect
from typing import Optional, List, Dict, Any, Callable, Awaitable, Union

from infra.logger import logger
from .api.search import SearchAPI
from .api.user import UserAPI
from .api.season import SeasonAPI
from .api.video import VideoAPI
from .models import BiliCookie


class BilibiliSearchService:
    """B站搜索服务"""
    
    def __init__(
        self,
        search_api: SearchAPI,
        user_api: UserAPI,
        season_api: SeasonAPI,
        video_api: VideoAPI,
        get_cookies: Optional[Union[
            Callable[[], Optional[BiliCookie]],  # 同步函数
            Callable[[], Awaitable[Optional[BiliCookie]]]  # 异步函数
        ]] = None
    ):
        """
        初始化搜索服务
        Args:
            search_api: 搜索API
            user_api: 用户API
            season_api: 剧集API
            video_api: 视频API
            get_cookies: 获取Cookie的函数
        """
        self.search_api = search_api
        self.user_api = user_api
        self.season_api = season_api
        self.video_api = video_api
        self.get_cookies = get_cookies
    
    async def search_user(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索用户
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
        Returns:
            用户信息列表
        """
        try:
            response = await self.search_api.search_user(keyword, page=1, page_size=limit)
            
            if not response or not response.data or not response.data.result:
                return []
            
            results = []
            # 解析搜索结果
            # 注意：实际API返回格式可能需要根据实际情况调整
            for item in response.data.result[:limit]:
                if isinstance(item, dict):
                    results.append({
                        "mid": item.get("mid"),
                        "name": item.get("uname"),
                        "face": item.get("upic"),
                        "sign": item.get("usign", ""),
                        "fans": item.get("fans", 0),
                        "videos": item.get("videos", 0)
                    })
            
            return results
        except Exception as e:
            logger.warn("BilibiliSearchService", f"搜索用户失败: {e}")
            return []
    
    async def search_bangumi(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索番剧
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
        Returns:
            番剧信息列表
        """
        try:
            response = await self.search_api.search_bangumi(keyword, page=1, page_size=limit)
            
            if not response or not response.data or not response.data.result:
                return []
            
            results = []
            for item in response.data.result[:limit]:
                if isinstance(item, dict):
                    results.append({
                        "season_id": item.get("season_id"),
                        "title": item.get("title"),
                        "cover": item.get("cover"),
                        "evaluate": item.get("evaluate", ""),
                        "media_id": item.get("media_id"),
                    })
            
            return results
        except Exception as e:
            logger.warn("BilibiliSearchService", f"搜索番剧失败: {e}")
            return []
    
    async def search_video(self, keyword: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        搜索视频
        Args:
            keyword: 搜索关键词
            limit: 返回结果数量限制
        Returns:
            视频信息列表
        """
        try:
            response = await self.search_api.search_video(keyword, page=1, page_size=limit)
            
            if not response or not response.data or not response.data.result:
                return []
            
            results = []
            for item in response.data.result[:limit]:
                if isinstance(item, dict):
                    results.append({
                        "aid": item.get("aid"),
                        "bvid": item.get("bvid"),
                        "title": item.get("title"),
                        "pic": item.get("pic"),
                        "author": item.get("author"),
                        "mid": item.get("mid"),
                        "play": item.get("play", 0),
                        "video_review": item.get("video_review", 0),
                        "duration": item.get("duration", ""),
                    })
            
            return results
        except Exception as e:
            logger.warn("BilibiliSearchService", f"搜索视频失败: {e}")
            return []
    
    def format_user_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化用户搜索结果"""
        if not results:
            return "❌ 未找到相关用户"
        
        lines = ["👤 搜索结果：\n"]
        for idx, user in enumerate(results, 1):
            lines.append(
                f"{idx}. {user['name']} (UID: {user['mid']})\n"
                f"   粉丝: {user['fans']} | 视频: {user['videos']}\n"
                f"   🔗 https://space.bilibili.com/{user['mid']}\n"
            )
        
        return "".join(lines)
    
    def format_bangumi_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化番剧搜索结果"""
        if not results:
            return "❌ 未找到相关番剧"
        
        lines = ["📺 搜索结果：\n"]
        for idx, bangumi in enumerate(results, 1):
            lines.append(
                f"{idx}. {bangumi['title']}\n"
                f"   🔗 https://www.bilibili.com/bangumi/play/ss{bangumi['season_id']}\n"
            )
        
        return "".join(lines)
    
    def format_video_results(self, results: List[Dict[str, Any]]) -> str:
        """格式化视频搜索结果"""
        if not results:
            return "❌ 未找到相关视频"
        
        lines = ["📹 搜索结果：\n"]
        for idx, video in enumerate(results, 1):
            lines.append(
                f"{idx}. {video['title']}\n"
                f"   UP主: {video['author']} | 播放: {video['play']} | 时长: {video['duration']}\n"
                f"   🔗 https://www.bilibili.com/video/{video['bvid']}\n"
            )
        
        return "".join(lines)

