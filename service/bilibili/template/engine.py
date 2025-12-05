"""
模板引擎
"""
import re
from typing import Any, Dict, Optional
from .templates import TemplateType, get_template


class TemplateEngine:
    """模板引擎"""
    
    # 特殊标记处理
    SPECIAL_MARKERS = {
        "#images": lambda data: _format_images(data.get("images", [])),
        "#detail": lambda data: _format_detail(data),
        "#screenshot": lambda data: _format_screenshot(data),
    }
    
    @staticmethod
    def render(template_type: TemplateType, data: Dict[str, Any]) -> str:
        """
        渲染模板
        Args:
            template_type: 模板类型
            data: 数据字典
        Returns:
            渲染后的字符串
        """
        template = get_template(template_type)
        
        # 处理特殊标记
        for marker, handler in TemplateEngine.SPECIAL_MARKERS.items():
            if marker in template:
                replacement = handler(data)
                template = template.replace(marker, replacement or "")
        
        # 替换普通变量
        result = template
        for key, value in data.items():
            placeholder = f"{{{key}}}"
            if placeholder in result:
                result = result.replace(placeholder, str(value) if value is not None else "")
        
        # 清理多余的换行
        result = re.sub(r'\n{3,}', '\n\n', result)
        result = result.strip()
        
        return result
    
    @staticmethod
    def render_dynamic(dynamic_item: Any, author_name: str, desc_text: str = "") -> str:
        """
        渲染动态模板
        Args:
            dynamic_item: 动态条目
            author_name: 作者名称
            desc_text: 动态文字内容
        Returns:
            渲染后的消息
        """
        data = {
            "author_name": author_name,
            "desc_text": desc_text,
            "dynamic_id": dynamic_item.id_str,
            "dynamic_type": dynamic_item.type,
            "images": _extract_images(dynamic_item),
        }
        return TemplateEngine.render(TemplateType.DYNAMIC, data)
    
    @staticmethod
    def render_video(video: Any, author_name: str) -> str:
        """
        渲染视频模板
        Args:
            video: 视频信息
            author_name: 作者名称
        Returns:
            渲染后的消息
        """
        data = {
            "author_name": author_name,
            "title": video.title,
            "bvid": video.bvid,
            "aid": video.aid,
            "view": getattr(video.stat, "view", 0) if hasattr(video, "stat") else 0,
            "reply": getattr(video.stat, "reply", 0) if hasattr(video, "stat") else 0,
            "like": getattr(video.stat, "like", 0) if hasattr(video, "stat") else 0,
            "duration": getattr(video, "duration", 0),
            "pic": getattr(video, "pic", ""),
        }
        return TemplateEngine.render(TemplateType.VIDEO, data)
    
    @staticmethod
    def render_live(room_info: Any, anchor_name: str = "") -> str:
        """
        渲染直播模板
        Args:
            room_info: 直播间信息
            anchor_name: 主播名称
        Returns:
            渲染后的消息
        """
        data = {
            "title": room_info.title,
            "room_id": room_info.room_id,
            "anchor_name": anchor_name or "未知",
            "online": room_info.online,
            "area_name": getattr(room_info, "area_name", ""),
        }
        return TemplateEngine.render(TemplateType.LIVE, data)
    
    @staticmethod
    def render_season(season_info: Any, episode: Any) -> str:
        """
        渲染剧集模板
        Args:
            season_info: 剧集信息
            episode: 分集信息
        Returns:
            渲染后的消息
        """
        data = {
            "title": season_info.title,
            "episode_title": episode.long_title if hasattr(episode, "long_title") else episode.title,
            "episode_id": episode.ep_id if hasattr(episode, "ep_id") else episode.episode_id,
            "cover": getattr(season_info, "cover", ""),
        }
        return TemplateEngine.render(TemplateType.SEASON, data)
    
    @staticmethod
    def render_user(user_info: Any) -> str:
        """
        渲染用户信息模板
        Args:
            user_info: 用户信息
        Returns:
            渲染后的消息
        """
        data = {
            "name": user_info.name,
            "sign": user_info.sign or "这个人很懒，什么都没有留下",
            "mid": user_info.mid,
            "fans": getattr(user_info, "fans", 0),
            "following": getattr(user_info, "following", 0),
            "level": user_info.level,
        }
        return TemplateEngine.render(TemplateType.USER, data)


def _extract_images(dynamic_item: Any) -> list:
    """从动态中提取图片列表"""
    images = []
    try:
        if hasattr(dynamic_item, "modules") and dynamic_item.modules.module_dynamic:
            major = dynamic_item.modules.module_dynamic.major
            if major and hasattr(major, "draw") and major.draw:
                draw = major.draw
                if isinstance(draw, dict) and "items" in draw:
                    for item in draw["items"]:
                        if isinstance(item, dict) and "src" in item:
                            images.append(item["src"])
    except Exception:
        pass
    return images


def _format_images(images: list) -> str:
    """格式化图片列表"""
    if not images:
        return ""
    return "\n".join([f"[图片] {img}" for img in images[:9]])  # 最多显示9张


def _format_detail(data: Dict[str, Any]) -> str:
    """格式化详细信息"""
    # 根据不同类型返回详细信息
    detail_type = data.get("detail_type", "")
    if detail_type == "dynamic":
        return _format_dynamic_detail(data)
    elif detail_type == "video":
        return _format_video_detail(data)
    return ""


def _format_dynamic_detail(data: Dict[str, Any]) -> str:
    """格式化动态详细信息"""
    return ""  # TODO: 实现动态详细信息格式化


def _format_video_detail(data: Dict[str, Any]) -> str:
    """格式化视频详细信息"""
    return ""  # TODO: 实现视频详细信息格式化


def _format_screenshot(data: Dict[str, Any]) -> str:
    """格式化截图"""
    screenshot_path = data.get("screenshot_path", "")
    if screenshot_path:
        return f"[CQ:image,file=file://{screenshot_path}]"
    return ""

