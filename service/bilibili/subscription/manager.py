"""
订阅管理器
"""
from typing import Dict, List, Optional, Set
from datetime import datetime, time

from infra.logger import logger
from .task import SubscriptionTask, TaskType, SleepInterval, AtInterval
from .storage import SubscriptionStorage
from .filter import FilterManager


class SubscriptionManager:
    """订阅管理器"""
    
    def __init__(self, storage: SubscriptionStorage, filter_manager: FilterManager):
        """
        初始化订阅管理器
        Args:
            storage: 存储管理器
            filter_manager: 过滤管理器
        """
        self.storage = storage
        self.filter_manager = filter_manager
        self._tasks: Dict[str, SubscriptionTask] = {}
        self._load_tasks()
    
    def _load_tasks(self):
        """加载任务"""
        tasks_data = self.storage.load_tasks()
        for task_id, task_data in tasks_data.items():
            try:
                self._tasks[task_id] = SubscriptionTask.from_dict(task_data)
            except Exception as e:
                logger.warn("SubscriptionManager", f"加载任务 {task_id} 失败: {e}")
    
    def _save_tasks(self):
        """保存任务"""
        tasks_data = {
            task_id: task.to_dict()
            for task_id, task in self._tasks.items()
        }
        self.storage.save_tasks(tasks_data)
    
    def add_subscription(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        contacts: Optional[Set[str]] = None
    ) -> SubscriptionTask:
        """
        添加订阅
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            contacts: 联系人列表（可选，默认使用群ID）
        Returns:
            SubscriptionTask
        """
        task_id = SubscriptionTask.generate_task_id(task_type, target_id, group_id)
        
        if task_id in self._tasks:
            # 已存在，更新联系人
            task = self._tasks[task_id]
            if contacts:
                task.contacts.update(contacts)
            else:
                task.contacts.add(group_id)
            self._save_tasks()
            logger.info("SubscriptionManager", f"更新订阅任务: {task_id}")
            return task
        
        # 创建新任务
        task = SubscriptionTask(
            task_id=task_id,
            task_type=task_type,
            target_id=target_id,
            group_id=group_id,
            contacts=contacts or {group_id}
        )
        self._tasks[task_id] = task
        self._save_tasks()
        logger.info("SubscriptionManager", f"添加订阅任务: {task_id}")
        return task
    
    def remove_subscription(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str
    ) -> bool:
        """
        移除订阅
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
        Returns:
            是否成功移除
        """
        task_id = SubscriptionTask.generate_task_id(task_type, target_id, group_id)
        
        if task_id in self._tasks:
            del self._tasks[task_id]
            self._save_tasks()
            logger.info("SubscriptionManager", f"移除订阅任务: {task_id}")
            return True
        
        return False
    
    def get_task(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str
    ) -> Optional[SubscriptionTask]:
        """
        获取任务
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
        Returns:
            SubscriptionTask或None
        """
        task_id = SubscriptionTask.generate_task_id(task_type, target_id, group_id)
        return self._tasks.get(task_id)
    
    def get_tasks_by_group(self, group_id: str) -> List[SubscriptionTask]:
        """
        获取群的所有任务
        Args:
            group_id: 群ID
        Returns:
            任务列表
        """
        return [
            task for task in self._tasks.values()
            if task.group_id == group_id
        ]
    
    def get_tasks_by_type(self, task_type: TaskType) -> List[SubscriptionTask]:
        """
        获取指定类型的所有任务
        Args:
            task_type: 任务类型
        Returns:
            任务列表
        """
        return [
            task for task in self._tasks.values()
            if task.task_type == task_type
        ]
    
    def get_all_tasks(self) -> List[SubscriptionTask]:
        """
        获取所有任务
        Returns:
            任务列表
        """
        return list(self._tasks.values())
    
    def set_cron(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        cron: Optional[str]
    ) -> bool:
        """
        设置CRON表达式
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            cron: CRON表达式（None表示使用默认间隔）
        Returns:
            是否成功设置
        """
        task = self.get_task(task_type, target_id, group_id)
        if task:
            task.cron = cron
            self._save_tasks()
            return True
        return False
    
    def add_sleep_interval(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        start: time,
        end: time
    ) -> bool:
        """
        添加休眠时间区间
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            start: 开始时间
            end: 结束时间
        Returns:
            是否成功添加
        """
        task = self.get_task(task_type, target_id, group_id)
        if task:
            interval = SleepInterval(start=start, end=end)
            if interval not in task.sleep_intervals:
                task.sleep_intervals.append(interval)
                self._save_tasks()
                return True
        return False
    
    def remove_sleep_interval(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        start: time,
        end: time
    ) -> bool:
        """
        移除休眠时间区间
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            start: 开始时间
            end: 结束时间
        Returns:
            是否成功移除
        """
        task = self.get_task(task_type, target_id, group_id)
        if task:
            interval = SleepInterval(start=start, end=end)
            if interval in task.sleep_intervals:
                task.sleep_intervals.remove(interval)
                self._save_tasks()
                return True
        return False
    
    def add_at_interval(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        start: time,
        end: time,
        at_all: bool = True
    ) -> bool:
        """
        添加@提醒时间区间
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            start: 开始时间
            end: 结束时间
            at_all: 是否@全体
        Returns:
            是否成功添加
        """
        task = self.get_task(task_type, target_id, group_id)
        if task:
            interval = AtInterval(start=start, end=end, at_all=at_all)
            if interval not in task.at_intervals:
                task.at_intervals.append(interval)
                self._save_tasks()
                return True
        return False
    
    def remove_at_interval(
        self,
        task_type: TaskType,
        target_id: str,
        group_id: str,
        start: time,
        end: time
    ) -> bool:
        """
        移除@提醒时间区间
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
            start: 开始时间
            end: 结束时间
        Returns:
            是否成功移除
        """
        task = self.get_task(task_type, target_id, group_id)
        if task:
            interval = AtInterval(start=start, end=end)
            if interval in task.at_intervals:
                task.at_intervals.remove(interval)
                self._save_tasks()
                return True
        return False
    
    def update_last_check(self, task_id: str, item_id: Optional[str] = None):
        """
        更新最后检查时间和最后项目ID
        Args:
            task_id: 任务ID
            item_id: 最后项目ID（可选）
        """
        if task_id in self._tasks:
            task = self._tasks[task_id]
            task.last_check = datetime.now()
            if item_id:
                task.last_item_id = item_id
            self._save_tasks()

