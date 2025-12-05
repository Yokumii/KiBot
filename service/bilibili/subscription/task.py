"""
订阅任务模型
"""
from typing import Optional, Set, List
from datetime import datetime, time
from enum import Enum
from dataclasses import dataclass, field


class TaskType(Enum):
    """订阅任务类型"""
    DYNAMIC = "dynamic"  # 动态订阅
    VIDEO = "video"  # 视频订阅
    LIVE = "live"  # 直播订阅
    SEASON = "season"  # 剧集订阅


@dataclass
class SleepInterval:
    """休眠时间区间"""
    start: time
    end: time
    
    def __contains__(self, t: time) -> bool:
        """判断时间是否在区间内"""
        if self.start <= self.end:
            return self.start <= t <= self.end
        else:
            # 跨天情况
            return t >= self.start or t <= self.end


@dataclass
class AtInterval:
    """@提醒时间区间"""
    start: time
    end: time
    at_all: bool = True  # 是否@全体
    
    def __contains__(self, t: time) -> bool:
        """判断时间是否在区间内"""
        if self.start <= self.end:
            return self.start <= t <= self.end
        else:
            # 跨天情况
            return t >= self.start or t <= self.end


@dataclass
class SubscriptionTask:
    """订阅任务"""
    task_id: str  # 任务ID，格式：{type}_{target_id}_{group_id}
    task_type: TaskType  # 任务类型
    target_id: str  # 目标ID（UP主UID、Season ID等）
    group_id: str  # 群ID
    contacts: Set[str] = field(default_factory=set)  # 联系人列表（群ID或用户ID）
    cron: Optional[str] = None  # CRON表达式（可选）
    sleep_intervals: List[SleepInterval] = field(default_factory=list)  # 休眠时间区间
    at_intervals: List[AtInterval] = field(default_factory=list)  # @提醒时间区间
    last_check: Optional[datetime] = None  # 最后检查时间
    last_item_id: Optional[str] = None  # 最后推送的项目ID
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.contacts:
            self.contacts.add(self.group_id)
    
    def is_sleeping(self, current_time: Optional[time] = None) -> bool:
        """
        判断当前是否处于休眠时间
        Args:
            current_time: 当前时间（可选，默认使用当前时间）
        Returns:
            True表示休眠中，False表示正常
        """
        if not self.sleep_intervals:
            return False
        
        if current_time is None:
            current_time = datetime.now().time()
        
        return any(current_time in interval for interval in self.sleep_intervals)
    
    def should_at(self, current_time: Optional[time] = None) -> bool:
        """
        判断当前是否应该@提醒
        Args:
            current_time: 当前时间（可选，默认使用当前时间）
        Returns:
            True表示应该@，False表示不@
        """
        if not self.at_intervals:
            return False
        
        if current_time is None:
            current_time = datetime.now().time()
        
        return any(current_time in interval for interval in self.at_intervals)
    
    def get_at_all(self, current_time: Optional[time] = None) -> bool:
        """
        获取是否应该@全体
        Args:
            current_time: 当前时间（可选，默认使用当前时间）
        Returns:
            True表示@全体，False表示不@全体
        """
        if current_time is None:
            current_time = datetime.now().time()
        
        for interval in self.at_intervals:
            if current_time in interval:
                return interval.at_all
        
        return False
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "target_id": self.target_id,
            "group_id": self.group_id,
            "contacts": list(self.contacts),
            "cron": self.cron,
            "sleep_intervals": [
                {"start": interval.start.isoformat(), "end": interval.end.isoformat()}
                for interval in self.sleep_intervals
            ],
            "at_intervals": [
                {
                    "start": interval.start.isoformat(),
                    "end": interval.end.isoformat(),
                    "at_all": interval.at_all
                }
                for interval in self.at_intervals
            ],
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "last_item_id": self.last_item_id
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "SubscriptionTask":
        """从字典创建"""
        sleep_intervals = [
            SleepInterval(
                start=time.fromisoformat(interval["start"]),
                end=time.fromisoformat(interval["end"])
            )
            for interval in data.get("sleep_intervals", [])
        ]
        
        at_intervals = [
            AtInterval(
                start=time.fromisoformat(interval["start"]),
                end=time.fromisoformat(interval["end"]),
                at_all=interval.get("at_all", True)
            )
            for interval in data.get("at_intervals", [])
        ]
        
        last_check = None
        if data.get("last_check"):
            last_check = datetime.fromisoformat(data["last_check"])
        
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            target_id=data["target_id"],
            group_id=data["group_id"],
            contacts=set(data.get("contacts", [])),
            cron=data.get("cron"),
            sleep_intervals=sleep_intervals,
            at_intervals=at_intervals,
            last_check=last_check,
            last_item_id=data.get("last_item_id")
        )
    
    @staticmethod
    def generate_task_id(task_type: TaskType, target_id: str, group_id: str) -> str:
        """
        生成任务ID
        Args:
            task_type: 任务类型
            target_id: 目标ID
            group_id: 群ID
        Returns:
            任务ID
        """
        return f"{task_type.value}_{target_id}_{group_id}"

