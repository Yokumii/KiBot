"""
订阅任务调度器
"""
import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from infra.logger import logger
from .manager import SubscriptionManager
from .task import SubscriptionTask, TaskType
from .filter import FilterManager
from ..api.dynamic import DynamicAPI
from ..api.video import VideoAPI
from ..api.live import LiveAPI
from ..api.season import SeasonAPI
from ..models import BiliCookie


class SubscriptionScheduler:
    """订阅任务调度器"""
    
    def __init__(
        self,
        manager: SubscriptionManager,
        filter_manager: FilterManager,
        dynamic_api: DynamicAPI,
        video_api: VideoAPI,
        live_api: LiveAPI,
        season_api: SeasonAPI,
        get_cookies: Callable[[], Optional[BiliCookie]],
        send_message: Callable[[str, str, Optional[str]], None],
        check_intervals: Optional[Dict[TaskType, int]] = None
    ):
        """
        初始化调度器
        Args:
            manager: 订阅管理器
            filter_manager: 过滤管理器
            dynamic_api: 动态API
            video_api: 视频API
            live_api: 直播API
            season_api: 剧集API
            get_cookies: 获取Cookie的函数
            send_message: 发送消息的函数 (group_id, message, at_all)
            check_intervals: 检查间隔（分钟）{TaskType: minutes}
        """
        self.manager = manager
        self.filter_manager = filter_manager
        self.dynamic_api = dynamic_api
        self.video_api = video_api
        self.live_api = live_api
        self.season_api = season_api
        self.get_cookies = get_cookies
        self.send_message = send_message
        
        # 默认检查间隔（分钟）
        self.check_intervals = check_intervals or {
            TaskType.DYNAMIC: 10,
            TaskType.VIDEO: 10,
            TaskType.LIVE: 30,
            TaskType.SEASON: 30
        }
        
        self.scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
        self._running = False
    
    def start(self):
        """启动调度器"""
        if self._running:
            return
        
        self._running = True
        
        # 为每种任务类型添加定时检查任务
        for task_type, interval_minutes in self.check_intervals.items():
            self.scheduler.add_job(
                self._check_tasks,
                trigger=IntervalTrigger(minutes=interval_minutes),
                args=[task_type],
                id=f"check_{task_type.value}",
                replace_existing=True
            )
        
        self.scheduler.start()
        logger.info("SubscriptionScheduler", "订阅调度器已启动")
    
    def stop(self):
        """停止调度器"""
        if not self._running:
            return
        
        self._running = False
        self.scheduler.shutdown(wait=True)
        logger.info("SubscriptionScheduler", "订阅调度器已停止")
    
    async def _check_tasks(self, task_type: TaskType):
        """
        检查指定类型的所有任务
        Args:
            task_type: 任务类型
        """
        tasks = self.manager.get_tasks_by_type(task_type)
        
        for task in tasks:
            try:
                # 检查是否处于休眠时间
                if task.is_sleeping():
                    logger.debug("SubscriptionScheduler", f"任务 {task.task_id} 处于休眠时间，跳过")
                    continue
                
                # 执行检查
                if task_type == TaskType.DYNAMIC:
                    await self._check_dynamic_task(task)
                elif task_type == TaskType.VIDEO:
                    await self._check_video_task(task)
                elif task_type == TaskType.LIVE:
                    await self._check_live_task(task)
                elif task_type == TaskType.SEASON:
                    await self._check_season_task(task)
                
            except Exception as e:
                logger.warn("SubscriptionScheduler", f"检查任务 {task.task_id} 时出错: {e}")
    
    async def _check_dynamic_task(self, task: SubscriptionTask):
        """检查动态任务"""
        cookies = self.get_cookies()
        if not cookies:
            logger.warn("SubscriptionScheduler", f"无法获取Cookie，跳过任务 {task.task_id}")
            return
        
        try:
            host_mid = int(task.target_id)
            response = await self.dynamic_api.get_dynamic_all(
                host_mid=host_mid,
                cookies=cookies
            )
            
            if not response or not response.data or not response.data.items:
                return
            
            # 获取过滤规则
            filter_rule = self.filter_manager.get_filter(task.group_id)
            
            # 检查新动态
            new_items = []
            for item in response.data.items:
                # 检查是否是新动态
                if task.last_item_id and item.id_str == task.last_item_id:
                    break  # 已到达上次检查的位置
                
                # 应用过滤规则
                if filter_rule.should_filter_dynamic(
                    item.type,
                    item.modules.module_dynamic.major.type if item.modules.module_dynamic.major else None
                ):
                    continue
                
                # 检查内容过滤
                if item.modules.module_dynamic.desc:
                    if filter_rule.should_filter_content(item.modules.module_dynamic.desc.text):
                        continue
                
                new_items.append(item)
            
            # 推送新动态
            if new_items:
                # 倒序推送（最新的在前）
                for item in reversed(new_items):
                    await self._send_dynamic_notification(task, item)
                
                # 更新最后检查时间和项目ID
                if new_items:
                    self.manager.update_last_check(task.task_id, new_items[0].id_str)
        
        except Exception as e:
            logger.warn("SubscriptionScheduler", f"检查动态任务 {task.task_id} 失败: {e}")
    
    async def _check_video_task(self, task: SubscriptionTask):
        """检查视频任务"""
        cookies = self.get_cookies()
        if not cookies:
            logger.warn("SubscriptionScheduler", f"无法获取Cookie，跳过任务 {task.task_id}")
            return
        
        try:
            mid = int(task.target_id)
            response = await self.video_api.get_user_videos(
                mid=mid,
                cookies=cookies
            )
            
            if not response or not response.data or not response.data.list:
                return
            
            # 获取过滤规则
            filter_rule = self.filter_manager.get_filter(task.group_id)
            
            # 检查新视频
            new_videos = []
            for video in response.data.list.vlist:
                # 检查是否是新视频
                if task.last_item_id and str(video.aid) == task.last_item_id:
                    break
                
                # 应用过滤规则
                if filter_rule.should_filter_video(
                    tid=video.typeid,
                    video_type=None  # TODO: 从视频信息中提取类型
                ):
                    continue
                
                new_videos.append(video)
            
            # 推送新视频
            if new_videos:
                for video in reversed(new_videos):
                    await self._send_video_notification(task, video)
                
                # 更新最后检查时间
                if new_videos:
                    self.manager.update_last_check(task.task_id, str(new_videos[0].aid))
        
        except Exception as e:
            logger.warn("SubscriptionScheduler", f"检查视频任务 {task.task_id} 失败: {e}")
    
    async def _check_live_task(self, task: SubscriptionTask):
        """检查直播任务"""
        try:
            # 先通过UID获取直播间号
            uid = int(task.target_id)
            room_info = await self.live_api.get_room_info_by_uid(uid)
            
            if not room_info or not room_info.data:
                return
            
            room_id = room_info.data.room_id
            
            # 获取直播间信息
            live_info = await self.live_api.get_live_info(room_id)
            
            if not live_info or not live_info.data or not live_info.data.room_info:
                return
            
            room_info_data = live_info.data.room_info
            
            # 检查是否开播
            if room_info_data.live_status == 1:  # 直播中
                # 检查是否是新开播
                if task.last_item_id == "live":
                    return  # 已经在直播中，不重复推送
                
                await self._send_live_notification(task, room_info_data)
                self.manager.update_last_check(task.task_id, "live")
            else:
                # 未开播，清除状态
                if task.last_item_id == "live":
                    self.manager.update_last_check(task.task_id, None)
        
        except Exception as e:
            logger.warn("SubscriptionScheduler", f"检查直播任务 {task.task_id} 失败: {e}")
    
    async def _check_season_task(self, task: SubscriptionTask):
        """检查剧集任务"""
        try:
            season_id = int(task.target_id)
            response = await self.season_api.get_season_info(season_id)
            
            if not response or not response.result:
                return
            
            season_info = response.result
            
            # 检查新分集
            if season_info.new_ep:
                new_ep_id = str(season_info.new_ep.id)
                if task.last_item_id != new_ep_id:
                    await self._send_season_notification(task, season_info)
                    self.manager.update_last_check(task.task_id, new_ep_id)
        
        except Exception as e:
            logger.warn("SubscriptionScheduler", f"检查剧集任务 {task.task_id} 失败: {e}")
    
    async def _send_dynamic_notification(self, task: SubscriptionTask, item: Any):
        """发送动态通知"""
        author = item.modules.module_author
        dynamic = item.modules.module_dynamic
        
        # 使用模板系统
        from ..template.engine import TemplateEngine
        desc_text = dynamic.desc.text if dynamic.desc else ""
        message = TemplateEngine.render_dynamic(item, author.name, desc_text)
        
        if not message:
            return
        
        # 检查是否需要@
        at_message = None
        if task.should_at():
            if task.get_at_all():
                at_message = "[CQ:at,qq=all]"
            # 可以添加@特定用户的逻辑
        
        # 发送消息到群
        self.send_message(task.group_id, message, at_message)
    
    async def _send_video_notification(self, task: SubscriptionTask, video: Any):
        """发送视频通知"""
        from ..template.engine import TemplateEngine
        message = TemplateEngine.render_video(video)
        
        if not message:
            return
        
        # 检查是否需要@
        at_message = None
        if task.should_at():
            if task.get_at_all():
                at_message = "[CQ:at,qq=all]"
        
        # 发送消息到群
        self.send_message(task.group_id, message, at_message)
    
    async def _send_live_notification(self, task: SubscriptionTask, room_info: Any):
        """发送直播通知"""
        from ..template.engine import TemplateEngine
        message = TemplateEngine.render_live(room_info)
        
        if not message:
            return
        
        # 检查是否需要@（直播默认@全体）
        at_message = "[CQ:at,qq=all]" if (task.should_at() and task.get_at_all()) or not task.should_at() else None
        
        # 发送消息到群
        self.send_message(task.group_id, message, at_message)
    
    async def _send_season_notification(self, task: SubscriptionTask, season_info: Any):
        """发送剧集通知"""
        from ..template.engine import TemplateEngine
        new_ep = season_info.new_ep
        message = TemplateEngine.render_season(season_info, new_ep)
        
        if not message:
            return
        
        # 检查是否需要@
        at_message = None
        if task.should_at():
            if task.get_at_all():
                at_message = "[CQ:at,qq=all]"
        
        # 发送消息到群
        self.send_message(task.group_id, message, at_message)

