"""
模板定义和管理
"""
import os
from enum import Enum
from typing import Optional, Dict
from pathlib import Path

from infra.logger import logger


class TemplateType(Enum):
    """模板类型"""
    DYNAMIC = "dynamic"  # 动态模板
    VIDEO = "video"  # 视频模板
    LIVE = "live"  # 直播模板
    SEASON = "season"  # 剧集模板
    USER = "user"  # 用户信息模板


class TemplateManager:
    """模板管理器"""
    
    def __init__(self, template_dir: str = "templates/bilibili"):
        """
        初始化模板管理器
        Args:
            template_dir: 模板文件目录
        """
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        self._templates: Dict[TemplateType, str] = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载所有模板"""
        # 默认模板
        default_templates = {
            TemplateType.DYNAMIC: (
                "📢 {author_name} 发布了新动态\n"
                "{desc_text}\n"
                "🔗 https://t.bilibili.com/{dynamic_id}"
            ),
            TemplateType.VIDEO: (
                "📹 {author_name} 发布了新视频\n"
                "📺 {title}\n"
                "👀 播放: {view} | 💬 评论: {reply} | 👍 点赞: {like}\n"
                "🔗 https://www.bilibili.com/video/{bvid}"
            ),
            TemplateType.LIVE: (
                "🔴 开播啦！\n"
                "📺 {title}\n"
                "👤 {anchor_name}\n"
                "👀 观看: {online}\n"
                "🔗 https://live.bilibili.com/{room_id}"
            ),
            TemplateType.SEASON: (
                "📺 {title} 更新了\n"
                "🎬 {episode_title}\n"
                "🔗 https://www.bilibili.com/bangumi/play/ep{episode_id}"
            ),
            TemplateType.USER: (
                "👤 {name}\n"
                "📝 {sign}\n"
                "👥 粉丝: {fans} | 关注: {following}\n"
                "🔗 https://space.bilibili.com/{mid}"
            )
        }
        
        # 尝试从文件加载，如果不存在则使用默认模板
        for template_type in TemplateType:
            template_file = self.template_dir / f"{template_type.value}.txt"
            if template_file.exists():
                try:
                    with open(template_file, "r", encoding="utf-8") as f:
                        self._templates[template_type] = f.read().strip()
                except Exception as e:
                    logger.warn("TemplateManager", f"加载模板 {template_type.value} 失败: {e}")
                    self._templates[template_type] = default_templates[template_type]
            else:
                # 使用默认模板并保存到文件
                self._templates[template_type] = default_templates[template_type]
                self._save_template(template_type, default_templates[template_type])
    
    def _save_template(self, template_type: TemplateType, content: str):
        """保存模板到文件"""
        template_file = self.template_dir / f"{template_type.value}.txt"
        try:
            with open(template_file, "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            logger.warn("TemplateManager", f"保存模板 {template_type.value} 失败: {e}")
    
    def get_template(self, template_type: TemplateType) -> str:
        """
        获取模板内容
        Args:
            template_type: 模板类型
        Returns:
            模板字符串
        """
        return self._templates.get(template_type, "")
    
    def set_template(self, template_type: TemplateType, content: str):
        """
        设置模板内容
        Args:
            template_type: 模板类型
            content: 模板内容
        """
        self._templates[template_type] = content
        self._save_template(template_type, content)
        logger.info("TemplateManager", f"模板 {template_type.value} 已更新")


# 全局模板管理器实例
_template_manager: Optional[TemplateManager] = None


def get_template_manager(template_dir: Optional[str] = None) -> TemplateManager:
    """获取模板管理器实例"""
    global _template_manager
    if _template_manager is None:
        _template_manager = TemplateManager(template_dir)
    return _template_manager


def get_template(template_type: TemplateType) -> str:
    """获取模板"""
    return get_template_manager().get_template(template_type)


def set_template(template_type: TemplateType, content: str):
    """设置模板"""
    get_template_manager().set_template(template_type, content)

