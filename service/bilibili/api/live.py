"""
直播API封装
"""
from typing import Optional
from ..client import BiliClient
from ..models import LiveRoomInfoResponse, LiveInfoResponse


class LiveAPI:
    """直播API"""
    
    # API端点
    ROOM_INIT = "https://api.live.bilibili.com/room/v1/Room/room_init"
    ROOM_INFO_OLD = "https://api.live.bilibili.com/room/v1/Room/getRoomInfoOld"
    ROOM_INFO = "https://api.live.bilibili.com/xlive/web-room/v1/index/getInfoByRoom"
    
    def __init__(self, client: BiliClient):
        """
        初始化直播API
        Args:
            client: BiliClient实例
        """
        self.client = client
    
    async def get_room_info(self, room_id: int) -> Optional[LiveRoomInfoResponse]:
        """
        获取直播间信息
        Args:
            room_id: 直播间号（可以为短号）
        Returns:
            LiveRoomInfoResponse
        """
        params = {"room_id": room_id}
        
        try:
            response = await self.client.get(
                self.ROOM_INIT,
                api_type="live",
                params=params
            )
            data = response.json()
            return LiveRoomInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("LiveAPI", f"获取直播间信息失败: {e}")
            return None
    
    async def get_room_info_by_uid(self, uid: int) -> Optional[LiveRoomInfoResponse]:
        """
        根据用户UID获取直播间信息（旧版API）
        Args:
            uid: 用户UID
        Returns:
            LiveRoomInfoResponse
        """
        params = {"mid": uid}
        
        try:
            response = await self.client.get(
                self.ROOM_INFO_OLD,
                api_type="live",
                params=params
            )
            data = response.json()
            return LiveRoomInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("LiveAPI", f"获取直播间信息失败: {e}")
            return None
    
    async def get_live_info(self, room_id: int) -> Optional[LiveInfoResponse]:
        """
        获取直播详情
        Args:
            room_id: 直播间号
        Returns:
            LiveInfoResponse
        """
        params = {"room_id": room_id}
        
        try:
            response = await self.client.get(
                self.ROOM_INFO,
                api_type="live",
                params=params
            )
            data = response.json()
            return LiveInfoResponse(**data)
        except Exception as e:
            from infra.logger import logger
            logger.warn("LiveAPI", f"获取直播详情失败: {e}")
            return None

