"""
订阅过滤规则
"""
import re
from typing import List, Optional, Set, Dict, Any
from enum import Enum

from infra.logger import logger


class DynamicType(Enum):
    """动态类型枚举"""
    NONE = "DYNAMIC_TYPE_NONE"
    FORWARD = "DYNAMIC_TYPE_FORWARD"  # 转发
    AV = "DYNAMIC_TYPE_AV"  # 视频
    PGC = "DYNAMIC_TYPE_PGC"  # 剧集
    WORD = "DYNAMIC_TYPE_WORD"  # 纯文字
    DRAW = "DYNAMIC_TYPE_DRAW"  # 带图
    ARTICLE = "DYNAMIC_TYPE_ARTICLE"  # 专栏
    MUSIC = "DYNAMIC_TYPE_MUSIC"  # 音乐
    LIVE = "DYNAMIC_TYPE_LIVE"  # 直播间分享
    LIVE_RCMD = "DYNAMIC_TYPE_LIVE_RCMD"  # 直播开播
    UGC_SEASON = "DYNAMIC_TYPE_UGC_SEASON"  # 合集更新


class MajorType(Enum):
    """动态主体类型枚举"""
    NONE = "MAJOR_TYPE_NONE"
    ARCHIVE = "MAJOR_TYPE_ARCHIVE"  # 视频
    PGC = "MAJOR_TYPE_PGC"  # 剧集
    DRAW = "MAJOR_TYPE_DRAW"  # 带图
    ARTICLE = "MAJOR_TYPE_ARTICLE"  # 专栏
    MUSIC = "MAJOR_TYPE_MUSIC"  # 音频
    LIVE = "MAJOR_TYPE_LIVE"  # 直播间分享
    LIVE_RCMD = "MAJOR_TYPE_LIVE_RCMD"  # 直播状态
    UGC_SEASON = "MAJOR_TYPE_UGC_SEASON"  # 合集更新
    OPUS = "MAJOR_TYPE_OPUS"  # 图文动态
    COMMON = "MAJOR_TYPE_COMMON"  # 一般类型


class FilterRule:
    """过滤规则"""
    
    def __init__(
        self,
        dynamic_types: Optional[Set[DynamicType]] = None,
        major_types: Optional[Set[MajorType]] = None,
        content_patterns: Optional[List[str]] = None,
        video_tids: Optional[Set[int]] = None,
        video_types: Optional[Set[str]] = None  # 付费、联合、回放
    ):
        """
        初始化过滤规则
        Args:
            dynamic_types: 允许的动态类型（None表示不过滤）
            major_types: 允许的主体类型（None表示不过滤）
            content_patterns: 内容屏蔽正则表达式列表
            video_tids: 允许的视频分区ID列表（None表示不过滤）
            video_types: 屏蔽的视频类型（None表示不过滤）
        """
        self.dynamic_types = dynamic_types or set()
        self.major_types = major_types or set()
        self.content_patterns = content_patterns or []
        self.video_tids = video_tids or set()
        self.video_types = video_types or set()
        
        # 编译正则表达式
        self._compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.content_patterns
        ]
    
    def should_filter_dynamic(self, dynamic_type: str, major_type: Optional[str] = None) -> bool:
        """
        判断是否应该过滤动态
        Args:
            dynamic_type: 动态类型
            major_type: 主体类型（可选）
        Returns:
            True表示应该过滤（不推送），False表示不过滤（推送）
        """
        # 检查动态类型过滤
        if self.dynamic_types:
            try:
                dt = DynamicType(dynamic_type)
                if dt not in self.dynamic_types:
                    return True  # 不在允许列表中，过滤
            except ValueError:
                # 未知类型，如果设置了过滤则过滤掉
                if self.dynamic_types:
                    return True
        
        # 检查主体类型过滤
        if self.major_types and major_type:
            try:
                mt = MajorType(major_type)
                if mt not in self.major_types:
                    return True  # 不在允许列表中，过滤
            except ValueError:
                # 未知类型，如果设置了过滤则过滤掉
                if self.major_types:
                    return True
        
        return False
    
    def should_filter_content(self, text: str) -> bool:
        """
        判断内容是否应该被过滤
        Args:
            text: 文本内容
        Returns:
            True表示应该过滤，False表示不过滤
        """
        if not self._compiled_patterns:
            return False
        
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return True  # 匹配到屏蔽规则，过滤
        
        return False
    
    def should_filter_video(self, tid: Optional[int] = None, video_type: Optional[str] = None) -> bool:
        """
        判断视频是否应该被过滤
        Args:
            tid: 视频分区ID
            video_type: 视频类型（付费、联合、回放）
        Returns:
            True表示应该过滤，False表示不过滤
        """
        # 检查分区过滤
        if self.video_tids and tid is not None:
            if tid not in self.video_tids:
                return True  # 不在允许的分区列表中，过滤
        
        # 检查类型过滤
        if self.video_types and video_type:
            if video_type in self.video_types:
                return True  # 在屏蔽类型列表中，过滤
        
        return False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "dynamic_types": [dt.value for dt in self.dynamic_types] if self.dynamic_types else None,
            "major_types": [mt.value for mt in self.major_types] if self.major_types else None,
            "content_patterns": self.content_patterns,
            "video_tids": list(self.video_tids) if self.video_tids else None,
            "video_types": list(self.video_types) if self.video_types else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilterRule":
        """从字典创建"""
        dynamic_types = None
        if data.get("dynamic_types"):
            dynamic_types = {DynamicType(dt) for dt in data["dynamic_types"]}
        
        major_types = None
        if data.get("major_types"):
            major_types = {MajorType(mt) for mt in data["major_types"]}
        
        return cls(
            dynamic_types=dynamic_types,
            major_types=major_types,
            content_patterns=data.get("content_patterns"),
            video_tids=set(data["video_tids"]) if data.get("video_tids") else None,
            video_types=set(data["video_types"]) if data.get("video_types") else None
        )


class FilterManager:
    """过滤规则管理器"""
    
    def __init__(self, storage: "SubscriptionStorage"):
        """
        初始化过滤管理器
        Args:
            storage: 存储管理器
        """
        self.storage = storage
        self._filters: Dict[str, FilterRule] = {}
        self._load_filters()
    
    def _load_filters(self):
        """加载过滤规则"""
        filters_data = self.storage.load_filters()
        for group_id, filter_data in filters_data.items():
            try:
                self._filters[group_id] = FilterRule.from_dict(filter_data)
            except Exception as e:
                logger.warn("FilterManager", f"加载群 {group_id} 的过滤规则失败: {e}")
    
    def get_filter(self, group_id: str) -> FilterRule:
        """
        获取群的过滤规则
        Args:
            group_id: 群ID
        Returns:
            FilterRule（如果没有则返回空规则）
        """
        return self._filters.get(group_id, FilterRule())
    
    def set_filter(self, group_id: str, filter_rule: FilterRule):
        """
        设置群的过滤规则
        Args:
            group_id: 群ID
            filter_rule: 过滤规则
        """
        self._filters[group_id] = filter_rule
        self._save_filters()
    
    def add_content_pattern(self, group_id: str, pattern: str):
        """
        添加内容屏蔽规则
        Args:
            group_id: 群ID
            pattern: 正则表达式模式
        """
        filter_rule = self.get_filter(group_id)
        if pattern not in filter_rule.content_patterns:
            filter_rule.content_patterns.append(pattern)
            filter_rule._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            self.set_filter(group_id, filter_rule)
    
    def remove_content_pattern(self, group_id: str, pattern: str):
        """
        移除内容屏蔽规则
        Args:
            group_id: 群ID
            pattern: 正则表达式模式
        """
        filter_rule = self.get_filter(group_id)
        if pattern in filter_rule.content_patterns:
            filter_rule.content_patterns.remove(pattern)
            filter_rule._compiled_patterns = [
                re.compile(p, re.IGNORECASE) for p in filter_rule.content_patterns
            ]
            self.set_filter(group_id, filter_rule)
    
    def add_dynamic_type_filter(self, group_id: str, dynamic_type: DynamicType):
        """
        添加动态类型过滤（只允许指定类型）
        Args:
            group_id: 群ID
            dynamic_type: 动态类型
        """
        filter_rule = self.get_filter(group_id)
        if not filter_rule.dynamic_types:
            filter_rule.dynamic_types = set()
        filter_rule.dynamic_types.add(dynamic_type)
        self.set_filter(group_id, filter_rule)
    
    def remove_dynamic_type_filter(self, group_id: str, dynamic_type: DynamicType):
        """
        移除动态类型过滤
        Args:
            group_id: 群ID
            dynamic_type: 动态类型
        """
        filter_rule = self.get_filter(group_id)
        if filter_rule.dynamic_types and dynamic_type in filter_rule.dynamic_types:
            filter_rule.dynamic_types.remove(dynamic_type)
            if not filter_rule.dynamic_types:
                filter_rule.dynamic_types = None
            self.set_filter(group_id, filter_rule)
    
    def add_video_tid_filter(self, group_id: str, tid: int):
        """
        添加视频分区过滤（只允许指定分区）
        Args:
            group_id: 群ID
            tid: 分区ID
        """
        filter_rule = self.get_filter(group_id)
        if not filter_rule.video_tids:
            filter_rule.video_tids = set()
        filter_rule.video_tids.add(tid)
        self.set_filter(group_id, filter_rule)
    
    def remove_video_tid_filter(self, group_id: str, tid: int):
        """
        移除视频分区过滤
        Args:
            group_id: 群ID
            tid: 分区ID
        """
        filter_rule = self.get_filter(group_id)
        if filter_rule.video_tids and tid in filter_rule.video_tids:
            filter_rule.video_tids.remove(tid)
            if not filter_rule.video_tids:
                filter_rule.video_tids = None
            self.set_filter(group_id, filter_rule)
    
    def _save_filters(self):
        """保存过滤规则"""
        filters_data = {
            group_id: filter_rule.to_dict()
            for group_id, filter_rule in self._filters.items()
        }
        self.storage.save_filters(filters_data)

