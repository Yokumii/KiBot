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
                # 如果事件循环正在运行，尝试在当前循环中创建任务
                # 注意：这需要确保在异步上下文中调用
                try:
                    # 尝试使用当前事件循环创建任务
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(
                            lambda: asyncio.run(self.service.get_valid_cookies())
                        )
                        result = future.result(timeout=10)
                except Exception as thread_error:
                    # 如果线程池方法失败，尝试直接在当前循环中运行
                    # 但这可能会失败，因为不能在运行中的循环中直接运行协程
                    logger.warn("BilibiliScheduler", f"线程池方法失败，尝试其他方法: {thread_error}")
                    # 创建一个新的事件循环来运行
                    import threading
                    result = None
                    exception_holder = [None]
                    
                    def run_in_new_loop():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            result_value = new_loop.run_until_complete(self.service.get_valid_cookies())
                            exception_holder[0] = result_value
                        except Exception as e:
                            exception_holder[0] = e
                        finally:
                            new_loop.close()
                    
                    thread = threading.Thread(target=run_in_new_loop)
                    thread.start()
                    thread.join(timeout=10)
                    
                    if thread.is_alive():
                        logger.error("BilibiliScheduler", "获取Cookie超时")
                        return None
                    
                    if isinstance(exception_holder[0], Exception):
                        raise exception_holder[0]
                    result = exception_holder[0]
            else:
                # 如果事件循环未运行，直接运行
                result = loop.run_until_complete(self.service.get_valid_cookies())
            
            if result:
                return result[0]
            else:
                logger.warn("BilibiliScheduler", "获取Cookie返回None，可能未登录")
        except asyncio.TimeoutError:
            logger.warn("BilibiliScheduler", "获取Cookie超时")
        except RuntimeError as e:
            # 处理运行时错误（如事件循环相关错误）
            error_msg = str(e) if str(e) else type(e).__name__
            logger.warn("BilibiliScheduler", f"获取Cookie失败（运行时错误）: {error_msg}")
        except Exception as e:
            import traceback
            error_msg = str(e) if str(e) else type(e).__name__
            logger.warn("BilibiliScheduler", f"获取Cookie失败: {error_msg}")
            logger.debug("BilibiliScheduler", f"异常详情: {traceback.format_exc()}")
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
