"""
B站链接自动解析器
参考 bilibili-helper 的正则表达式
"""
import re
import inspect
from typing import Optional, Tuple, Dict, Any, Callable, Awaitable, Union
from urllib.parse import urlparse

from infra.logger import logger
from .api.dynamic import DynamicAPI
from .api.video import VideoAPI
from .api.live import LiveAPI
from .api.season import SeasonAPI
from .api.user import UserAPI
from .models import BiliCookie


class BilibiliParser:
    """B站链接解析器"""
    
    # 正则表达式模式
    VIDEO_REGEX = re.compile(r"(?i)(?<!\w)(?:av(\d+)|(BV1[1-9A-NP-Za-km-z]{9}))")
    # 动态链接：t.bilibili.com/xxx 或 t.bilibili.com/h5/dynamic/detail/xxx
    DYNAMIC_REGEX = re.compile(r"t\.bilibili\.com/(?:h5/dynamic/detail/)?(\d+)")
    # 直播间链接：live.bilibili.com/xxx 或 live.bilibili.com/h5/xxx
    ROOM_REGEX = re.compile(r"live\.bilibili\.com/(?:h5/)?(\d+)")
    # 用户空间链接：space.bilibili.com/xxx 或 bilibili.com/space/xxx
    SPACE_REGEX = re.compile(r"(?:space\.bilibili\.com/|bilibili\.com/space/)(\d+)")
    SEASON_REGEX = re.compile(r"(?i)(?<!\w)ss(\d{4,10})")
    EPISODE_REGEX = re.compile(r"(?i)(?<!\w)ep(\d{4,10})")
    MEDIA_REGEX = re.compile(r"(?i)(?<!\w)md(\d{4,10})")
    ARTICLE_REGEX = re.compile(r"(?i)(?<!\w)cv(\d{4,10})")
    # 专栏链接：bilibili.com/read/mobile?id=xxx 或 bilibili.com/read/mobile/xxx
    ARTICLE_URL_REGEX = re.compile(r"bilibili\.com/read/mobile(?:\?id=|/)(\d+)")
    SHORT_LINK_REGEX = re.compile(r"(?:b23\.tv|bili2233\.cn)/?([0-9A-z]+)")
    
    def __init__(
        self,
        dynamic_api: DynamicAPI,
        video_api: VideoAPI,
        live_api: LiveAPI,
        season_api: SeasonAPI,
        user_api: UserAPI,
        get_cookies: Optional[Union[
            Callable[[], Optional[BiliCookie]],  # 同步函数
            Callable[[], Awaitable[Optional[BiliCookie]]]  # 异步函数
        ]] = None
    ):
        """
        初始化解析器
        Args:
            dynamic_api: 动态API
            video_api: 视频API
            live_api: 直播API
            season_api: 剧集API
            user_api: 用户API
            get_cookies: 获取Cookie的函数
        """
        self.dynamic_api = dynamic_api
        self.video_api = video_api
        self.live_api = live_api
        self.season_api = season_api
        self.user_api = user_api
        self.get_cookies = get_cookies
    
    async def _get_cookies(self) -> Optional[BiliCookie]:
        """
        内部方法：获取Cookie，支持同步和异步函数
        """
        if not self.get_cookies:
            return None
        
        # 检查是否是协程函数
        if inspect.iscoroutinefunction(self.get_cookies):
            return await self.get_cookies()
        else:
            # 同步函数，直接调用
            return self.get_cookies()
    
    def find_links(self, text: str) -> list[Tuple[str, str, str]]:
        """
        在文本中查找所有B站链接
        Args:
            text: 文本内容
        Returns:
            [(link_type, id, matched_text), ...]
        """
        links = []
        
        # 视频
        for match in self.VIDEO_REGEX.finditer(text):
            aid, bvid = match.groups()
            if bvid:
                links.append(("video", bvid, match.group()))
            elif aid:
                links.append(("video", aid, match.group()))
        
        # 动态
        for match in self.DYNAMIC_REGEX.finditer(text):
            links.append(("dynamic", match.group(1), match.group(0)))
        
        # 直播间
        for match in self.ROOM_REGEX.finditer(text):
            links.append(("live", match.group(1), match.group(0)))
        
        # 用户空间
        for match in self.SPACE_REGEX.finditer(text):
            links.append(("user", match.group(1), match.group(0)))
        
        # 剧集
        for match in self.SEASON_REGEX.finditer(text):
            links.append(("season", match.group(1), match.group()))
        
        # 分集
        for match in self.EPISODE_REGEX.finditer(text):
            links.append(("episode", match.group(1), match.group()))
        
        # 媒体
        for match in self.MEDIA_REGEX.finditer(text):
            links.append(("media", match.group(1), match.group()))
        
        # 专栏
        for match in self.ARTICLE_REGEX.finditer(text):
            links.append(("article", match.group(1), match.group()))
        
        for match in self.ARTICLE_URL_REGEX.finditer(text):
            links.append(("article", match.group(1), match.group(0)))
        
        # 短链接（需要解析跳转）
        for match in self.SHORT_LINK_REGEX.finditer(text):
            links.append(("short_link", match.group(1), match.group(0)))
        
        return links
    
    async def parse_video(self, aid: Optional[int] = None, bvid: Optional[str] = None) -> Optional[str]:
        """
        解析视频信息
        Args:
            aid: 视频AV号
            bvid: 视频BV号
        Returns:
            格式化后的消息
        """
        try:
            cookies = await self._get_cookies() if self.get_cookies else None
            response = await self.video_api.get_video_info(aid=aid, bvid=bvid, cookies=cookies)
            
            if not response or not response.data:
                return None
            
            video = response.data
            author_name = video.owner.name if video.owner else "未知"
            
            from .template.engine import TemplateEngine
            return TemplateEngine.render_video(video, author_name)
        except Exception as e:
            logger.warn("BilibiliParser", f"解析视频失败: {e}")
            return None
    
    async def parse_dynamic(self, dynamic_id: str) -> Optional[str]:
        """
        解析动态信息
        Args:
            dynamic_id: 动态ID
        Returns:
            格式化后的消息
        """
        try:
            cookies = await self._get_cookies() if self.get_cookies else None
            response = await self.dynamic_api.get_dynamic_detail(dynamic_id, cookies=cookies)
            
            if not response or not response.data or not response.data.items:
                return None
            
            item = response.data.items[0]
            author = item.modules.module_author
            dynamic = item.modules.module_dynamic
            
            desc_text = dynamic.desc.text if dynamic.desc else ""
            
            from .template.engine import TemplateEngine
            return TemplateEngine.render_dynamic(item, author.name, desc_text)
        except Exception as e:
            logger.warn("BilibiliParser", f"解析动态失败: {e}")
            return None
    
    async def parse_live(self, room_id: int) -> Optional[str]:
        """
        解析直播信息
        Args:
            room_id: 直播间号
        Returns:
            格式化后的消息
        """
        try:
            response = await self.live_api.get_live_info(room_id)
            
            if not response or not response.data or not response.data.room_info:
                return None
            
            room_info = response.data.room_info
            anchor_name = ""
            if response.data.anchor_info:
                anchor_name = response.data.anchor_info.get("base_info", {}).get("uname", "")
            
            from .template.engine import TemplateEngine
            return TemplateEngine.render_live(room_info, anchor_name)
        except Exception as e:
            logger.warn("BilibiliParser", f"解析直播信息失败: {e}")
            return None
    
    async def parse_user(self, uid: int) -> Optional[str]:
        """
        解析用户信息
        Args:
            uid: 用户UID
        Returns:
            格式化后的消息
        """
        try:
            cookies = await self._get_cookies() if self.get_cookies else None
            response = await self.user_api.get_user_info(uid, cookies=cookies)
            
            if not response or not response.data:
                return None
            
            from .template.engine import TemplateEngine
            return TemplateEngine.render_user(response.data)
        except Exception as e:
            logger.warn("BilibiliParser", f"解析用户信息失败: {e}")
            return None
    
    async def parse_season(self, season_id: int) -> Optional[str]:
        """
        解析剧集信息
        Args:
            season_id: 剧集ID
        Returns:
            格式化后的消息
        """
        try:
            response = await self.season_api.get_season_info(season_id)
            
            if not response or not response.result:
                return None
            
            season_info = response.result
            
            # 获取最新分集
            if season_info.new_ep:
                from .template.engine import TemplateEngine
                return TemplateEngine.render_season(season_info, season_info.new_ep)
            
            return None
        except Exception as e:
            logger.warn("BilibiliParser", f"解析剧集信息失败: {e}")
            return None
    
    async def parse(self, link_type: str, link_id: str) -> Optional[str]:
        """
        通用解析方法
        Args:
            link_type: 链接类型
            link_id: 链接ID
        Returns:
            格式化后的消息
        """
        try:
            if link_type == "video":
                # 判断是aid还是bvid
                if link_id.startswith("BV"):
                    return await self.parse_video(bvid=link_id)
                else:
                    return await self.parse_video(aid=int(link_id))
            elif link_type == "dynamic":
                return await self.parse_dynamic(link_id)
            elif link_type == "live":
                return await self.parse_live(int(link_id))
            elif link_type == "user":
                return await self.parse_user(int(link_id))
            elif link_type == "season":
                return await self.parse_season(int(link_id))
            elif link_type == "episode":
                # 分集需要先获取分集信息，这里简化处理
                return None  # TODO: 实现分集解析
            elif link_type == "article":
                return None  # TODO: 实现专栏解析
            elif link_type == "short_link":
                # 短链接需要解析跳转
                return None  # TODO: 实现短链接解析
            else:
                return None
        except Exception as e:
            logger.warn("BilibiliParser", f"解析 {link_type}:{link_id} 失败: {e}")
            return None

