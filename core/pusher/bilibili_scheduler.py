"""
B站订阅调度器（基于新的订阅系统）
"""
from typing import Optional
import asyncio

from adapter.napcat.http_api import NapCatHttpClient
from infra.logger import logger
from service.bilibili.service import BiliService
from service.bilibili.subscription import (
    SubscriptionManager, FilterManager, SubscriptionStorage,
    SubscriptionScheduler, TaskType
)
from service.bilibili.models import BiliCookie


class BilibiliScheduler:
    """B站订阅调度器"""
    
    def __init__(self, http_client: NapCatHttpClient):
        """
        初始化调度器
        Args:
            http_client: NapCat HTTP客户端
        """
        self.client = http_client
        self.service = BiliService()
        
        # 初始化订阅系统
        storage = SubscriptionStorage()
        filter_manager = FilterManager(storage)
        self.manager = SubscriptionManager(storage, filter_manager)
        self.filter_manager = filter_manager
        
        # 创建调度器
        self.scheduler = SubscriptionScheduler(
            manager=self.manager,
            filter_manager=filter_manager,
            dynamic_api=self.service.dynamic_api,
            video_api=self.service.video_api,
            live_api=self.service.live_api,
            season_api=self.service.season_api,
            get_cookies=self._get_cookies_sync,
            send_message=self._send_message,
            check_intervals={
                TaskType.DYNAMIC: 5,  # 5分钟检查一次动态
                TaskType.VIDEO: 10,
                TaskType.LIVE: 30,
                TaskType.SEASON: 30
            }
        )
    
    def _get_cookies_sync(self) -> Optional[BiliCookie]:
        """同步获取Cookie（供调度器使用）"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，使用 run_coroutine_threadsafe
                future = asyncio.run_coroutine_threadsafe(
                    self.service.get_valid_cookies(), loop
                )
                result = future.result(timeout=10)
            else:
                # 如果事件循环未运行，直接运行
                result = loop.run_until_complete(self.service.get_valid_cookies())
            
            if result:
                return result[0]
        except Exception as e:
            logger.warn("BilibiliScheduler", f"获取Cookie失败: {e}")
        return None
    
    def _send_message(self, group_id: str, message: str, at_message: Optional[str] = None):
        """发送消息（供调度器使用）"""
        try:
            full_message = (at_message + "\n" + message) if at_message else message
            
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果事件循环正在运行，创建任务
                asyncio.create_task(
                    self.client.send_group_msg(int(group_id), full_message)
                )
            else:
                # 如果事件循环未运行，直接运行
                loop.run_until_complete(
                    self.client.send_group_msg(int(group_id), full_message)
                )
        except Exception as e:
            logger.warn("BilibiliScheduler", f"发送消息到群 {group_id} 失败: {e}")
    
    def start(self):
        """启动调度器"""
        # 确保Cookie有效
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.service.ensure_valid_cookies())
            else:
                loop.run_until_complete(self.service.ensure_valid_cookies())
        except Exception as e:
            logger.warn("BilibiliScheduler", f"初始化Cookie失败: {e}")
        
        # 启动订阅调度器
        self.scheduler.start()
        logger.info("BilibiliScheduler", "B站订阅调度器已启动")
    
    def stop(self):
        """停止调度器"""
        self.scheduler.stop()
        logger.info("BilibiliScheduler", "B站订阅调度器已停止")
