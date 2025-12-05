"""
搜索API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import SearchResponse


class SearchAPI:
    """搜索API"""
    
    # API端点（使用WBI签名版本）
    SEARCH_ALL = "https://api.bilibili.com/x/web-interface/wbi/search/all/v2"
    SEARCH_TYPE = "https://api.bilibili.com/x/web-interface/wbi/search/type"
    
    def __init__(self, client: BiliClient):
        """
        初始化搜索API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def search_all(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20
    ) -> Optional[SearchResponse]:
        """
        全站搜索
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        Returns:
            SearchResponse
        """
        params = {
            "keyword": keyword,
            "page": page,  # 搜索API使用page和pagesize
            "pagesize": page_size
        }
        
        try:
            response = await self.client.get(
                self.SEARCH_ALL,
                api_type="search",
                params=params
            )
            data = response.json()
            return SearchResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("SearchAPI", f"全站搜索失败: {e}")
            return None
    
    async def search_user(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20
    ) -> Optional[SearchResponse]:
        """
        搜索用户
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        Returns:
            SearchResponse
        """
        return await self._search_type("bili_user", keyword, page, page_size)
    
    async def search_bangumi(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20
    ) -> Optional[SearchResponse]:
        """
        搜索番剧
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        Returns:
            SearchResponse
        """
        return await self._search_type("media_bangumi", keyword, page, page_size)
    
    async def search_video(
        self,
        keyword: str,
        page: int = 1,
        page_size: int = 20
    ) -> Optional[SearchResponse]:
        """
        搜索视频
        Args:
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        Returns:
            SearchResponse
        """
        return await self._search_type("video", keyword, page, page_size)
    
    async def _search_type(
        self,
        search_type: str,
        keyword: str,
        page: int,
        page_size: int
    ) -> Optional[SearchResponse]:
        """
        按类型搜索
        Args:
            search_type: 搜索类型
            keyword: 搜索关键词
            page: 页码
            page_size: 每页数量
        Returns:
            SearchResponse
        """
        params = {
            "search_type": search_type,
            "keyword": keyword,
            "page": page,  # 搜索API使用page和pagesize
            "pagesize": page_size
        }
        
        try:
            response = await self.client.get(
                self.SEARCH_TYPE,
                api_type="search",
                params=params
            )
            data = response.json()
            return SearchResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("SearchAPI", f"搜索失败: {e}")
            return None

