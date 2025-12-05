"""
剧集API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import SeasonInfoResponse


class SeasonAPI:
    """剧集API"""
    
    # API端点
    SEASON_INFO = "https://api.bilibili.com/pgc/view/web/season"
    
    def __init__(self, client: BiliClient):
        """
        初始化剧集API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def get_season_info(self, season_id: int) -> Optional[SeasonInfoResponse]:
        """
        获取剧集信息
        Args:
            season_id: 剧集Season ID
        Returns:
            SeasonInfoResponse
        """
        params = {"season_id": season_id}
        
        try:
            response = await self.client.get(
                self.SEASON_INFO,
                api_type="season",
                params=params
            )
            data = response.json()
            return SeasonInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("SeasonAPI", f"获取剧集信息失败: {e}")
            return None

