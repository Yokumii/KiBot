# Bilibili 服务优化设计文档

> 版本: 1.0
> 日期: 2025-12-19

## 1. 背景与目标

### 1.1 当前问题
- **风控问题**: 使用 Playwright 浏览器截图方式容易触发 B站反爬机制
- **资源消耗**: Playwright 启动浏览器消耗大量内存和 CPU
- **功能单一**: 仅支持动态订阅推送，缺少视频信息查询等功能
- **模型不完整**: 多数字段使用 `Dict[str, Any]`，缺乏类型安全

### 1.2 优化目标
1. **替换截图方案**: 使用 API 返回数据解析 + 文本/图片渲染，避免浏览器截图
2. **完善数据模型**: 为每种动态类型创建完整的 Pydantic 模型
3. **增加功能**: 视频信息查询、UP主信息查询、评论获取等
4. **提升可维护性**: 分离关注点，抽象内容渲染器

---

## 2. 动态类型分析

根据 B站 API 文档，动态主要类型如下：

| 类型枚举 | 说明 | 主要内容字段 |
|---------|------|-------------|
| `DYNAMIC_TYPE_AV` | 视频动态 | `modules.module_dynamic.major.archive` |
| `DYNAMIC_TYPE_DRAW` | 图文动态 | `modules.module_dynamic.major.draw` |
| `DYNAMIC_TYPE_WORD` | 纯文字动态 | `modules.module_dynamic.desc.text` |
| `DYNAMIC_TYPE_FORWARD` | 转发动态 | `orig` (原动态) + `desc.text` |
| `DYNAMIC_TYPE_ARTICLE` | 专栏文章 | `modules.module_dynamic.major.article` |
| `DYNAMIC_TYPE_MUSIC` | 音频动态 | `modules.module_dynamic.major.music` |
| `DYNAMIC_TYPE_LIVE_RCMD` | 直播推荐 | `modules.module_dynamic.major.live_rcmd` |
| `DYNAMIC_TYPE_COMMON_SQUARE` | 通用卡片 | `modules.module_dynamic.major.common` |

---

## 3. 架构设计

### 3.1 模块结构

```
service/bilibili/
├── __init__.py
├── client.py              # HTTP 客户端，封装 API 调用
├── service.py             # 业务服务层，组合各功能
├── models/                # 数据模型目录（新建）
│   ├── __init__.py
│   ├── common.py          # 通用模型（BiliCookie, BaseResponse 等）
│   ├── dynamic.py         # 动态相关模型
│   ├── video.py           # 视频相关模型
│   ├── user.py            # 用户相关模型
│   └── auth.py            # 登录认证模型
├── renderer/              # 内容渲染器目录（新建）
│   ├── __init__.py
│   ├── base.py            # 渲染器基类
│   ├── dynamic_renderer.py # 动态内容渲染器
│   └── video_renderer.py  # 视频信息渲染器
└── utils/
    ├── __init__.py
    ├── cookie_refresher.py
    ├── qrcode_generator.py
    └── screenshot.py      # 保留但标记废弃，后续删除
```

### 3.2 类图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           BiliService                                │
│  - client: BiliClient                                                │
│  - renderer: DynamicRenderer                                         │
│  + get_user_dynamics() → List[DynamicItem]                          │
│  + get_video_info(bvid) → VideoInfo                                 │
│  + get_user_info(mid) → UserInfo                                    │
│  + render_dynamic(dynamic) → RenderedContent                        │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌─────────────────────────────┐     ┌─────────────────────────────────┐
│        BiliClient           │     │      DynamicRenderer            │
│  + get_user_dynamics()      │     │  + render(DynamicItem) → str    │
│  + get_video_info()         │     │  + render_video()               │
│  + get_user_info()          │     │  + render_draw()                │
│  + get_dynamic_detail()     │     │  + render_forward()             │
└─────────────────────────────┘     │  + render_article()             │
                                    └─────────────────────────────────┘
```

---

## 4. 数据模型设计

### 4.1 通用模型 (`models/common.py`)

```python
from typing import Optional, Generic, TypeVar
from pydantic import BaseModel

T = TypeVar('T')

class BiliResponse(BaseModel, Generic[T]):
    """B站 API 通用响应"""
    code: int
    message: str
    ttl: int = 1
    data: Optional[T] = None

    @property
    def is_success(self) -> bool:
        return self.code == 0

class BiliCookie(BaseModel):
    """B站 Cookie 信息"""
    DedeUserID: str
    DedeUserID__ckMd5: str
    SESSDATA: str
    bili_jct: str
```

### 4.2 动态模型 (`models/dynamic.py`)

```python
from typing import Optional, List
from pydantic import BaseModel
from enum import Enum

class DynamicType(str, Enum):
    """动态类型枚举"""
    AV = "DYNAMIC_TYPE_AV"           # 视频
    DRAW = "DYNAMIC_TYPE_DRAW"       # 图文
    WORD = "DYNAMIC_TYPE_WORD"       # 纯文字
    FORWARD = "DYNAMIC_TYPE_FORWARD" # 转发
    ARTICLE = "DYNAMIC_TYPE_ARTICLE" # 专栏
    MUSIC = "DYNAMIC_TYPE_MUSIC"     # 音乐
    LIVE_RCMD = "DYNAMIC_TYPE_LIVE_RCMD"  # 直播
    COMMON = "DYNAMIC_TYPE_COMMON_SQUARE" # 通用卡片
    NONE = "DYNAMIC_TYPE_NONE"       # 无效/已删除

# === 作者信息 ===
class DynamicAuthor(BaseModel):
    """动态作者信息"""
    mid: int
    name: str
    face: str
    pub_action: Optional[str] = None  # "发布了视频"、"投稿了"等
    pub_time: Optional[str] = None    # 发布时间文本
    pub_ts: Optional[int] = None      # 发布时间戳

# === 视频内容 ===
class DynamicArchive(BaseModel):
    """视频动态内容"""
    aid: int
    bvid: str
    title: str
    desc: str
    cover: str                # 封面图 URL
    duration_text: str        # 时长文本 "12:34"
    stat: 'ArchiveStat'

class ArchiveStat(BaseModel):
    """视频统计"""
    play: int      # 播放量
    danmaku: int   # 弹幕数

# === 图文内容 ===
class DrawItem(BaseModel):
    """图片项"""
    src: str       # 图片 URL
    width: int
    height: int

class DynamicDraw(BaseModel):
    """图文动态内容"""
    items: List[DrawItem]

# === 专栏内容 ===
class DynamicArticle(BaseModel):
    """专栏文章内容"""
    id: int
    title: str
    desc: str
    covers: List[str]
    label: str     # 分类标签

# === 音乐内容 ===
class DynamicMusic(BaseModel):
    """音乐动态内容"""
    id: int
    title: str
    cover: str
    label: str     # "音频"

# === 通用卡片 ===
class DynamicCommon(BaseModel):
    """通用卡片内容"""
    title: str
    desc: str
    cover: str
    url: str       # 跳转链接

# === 动态主体 ===
class DynamicMajor(BaseModel):
    """动态主要内容"""
    type: str
    archive: Optional[DynamicArchive] = None
    draw: Optional[DynamicDraw] = None
    article: Optional[DynamicArticle] = None
    music: Optional[DynamicMusic] = None
    common: Optional[DynamicCommon] = None

class DynamicDesc(BaseModel):
    """动态文字描述"""
    text: str
    rich_text_nodes: Optional[List[dict]] = None  # 富文本节点

class DynamicModule(BaseModel):
    """动态模块"""
    module_author: DynamicAuthor
    module_dynamic: 'ModuleDynamic'

class ModuleDynamic(BaseModel):
    """动态内容模块"""
    desc: Optional[DynamicDesc] = None
    major: Optional[DynamicMajor] = None

# === 动态条目 ===
class DynamicItem(BaseModel):
    """动态条目"""
    id_str: str
    type: DynamicType
    modules: DynamicModule
    visible: bool
    orig: Optional['DynamicItem'] = None  # 转发原动态

    @property
    def author(self) -> DynamicAuthor:
        return self.modules.module_author

    @property
    def content(self) -> Optional[ModuleDynamic]:
        return self.modules.module_dynamic

# === 动态列表响应 ===
class DynamicListData(BaseModel):
    """动态列表数据"""
    has_more: bool
    items: List[DynamicItem]
    offset: str
    update_baseline: str
    update_num: int
```

### 4.3 视频模型 (`models/video.py`)

```python
from typing import Optional, List
from pydantic import BaseModel

class VideoOwner(BaseModel):
    """视频 UP主"""
    mid: int
    name: str
    face: str

class VideoStat(BaseModel):
    """视频统计数据"""
    view: int       # 播放量
    danmaku: int    # 弹幕数
    reply: int      # 评论数
    favorite: int   # 收藏数
    coin: int       # 投币数
    share: int      # 分享数
    like: int       # 点赞数

class VideoDimension(BaseModel):
    """视频分辨率"""
    width: int
    height: int
    rotate: int = 0

class VideoPage(BaseModel):
    """视频分P"""
    cid: int
    page: int
    part: str       # 分P标题
    duration: int   # 时长（秒）

class VideoInfo(BaseModel):
    """视频详细信息"""
    bvid: str
    aid: int
    title: str
    pic: str                    # 封面
    desc: str                   # 简介
    pubdate: int                # 发布时间戳
    duration: int               # 总时长（秒）
    owner: VideoOwner
    stat: VideoStat
    dimension: VideoDimension
    pages: List[VideoPage] = []
    tname: str = ""             # 分区名

    @property
    def url(self) -> str:
        return f"https://www.bilibili.com/video/{self.bvid}"

    @property
    def duration_text(self) -> str:
        """格式化时长"""
        m, s = divmod(self.duration, 60)
        h, m = divmod(m, 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
```

### 4.4 用户模型 (`models/user.py`)

```python
from typing import Optional
from pydantic import BaseModel

class UserInfo(BaseModel):
    """用户基本信息"""
    mid: int
    name: str
    face: str           # 头像
    sign: str = ""      # 签名
    level: int = 0      # 等级
    sex: str = "保密"

class UserStat(BaseModel):
    """用户统计"""
    follower: int       # 粉丝数
    following: int      # 关注数

class UserCard(BaseModel):
    """用户名片"""
    info: UserInfo
    stat: UserStat
```

---

## 5. 内容渲染器设计

### 5.1 渲染器基类 (`renderer/base.py`)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List

@dataclass
class RenderedContent:
    """渲染结果"""
    text: str                           # 文本内容
    images: List[str] = None           # 图片 URL 列表

    def __post_init__(self):
        if self.images is None:
            self.images = []

class BaseRenderer(ABC):
    """渲染器基类"""

    @abstractmethod
    def render(self, data) -> RenderedContent:
        """渲染数据为可发送的内容"""
        pass
```

### 5.2 动态渲染器 (`renderer/dynamic_renderer.py`)

```python
from typing import Optional
from ..models.dynamic import DynamicItem, DynamicType, DynamicArchive, DynamicDraw
from .base import BaseRenderer, RenderedContent

class DynamicRenderer(BaseRenderer):
    """动态内容渲染器"""

    def render(self, dynamic: DynamicItem) -> RenderedContent:
        """根据动态类型分发渲染"""
        handlers = {
            DynamicType.AV: self._render_video,
            DynamicType.DRAW: self._render_draw,
            DynamicType.WORD: self._render_word,
            DynamicType.FORWARD: self._render_forward,
            DynamicType.ARTICLE: self._render_article,
            DynamicType.MUSIC: self._render_music,
            DynamicType.COMMON: self._render_common,
        }

        handler = handlers.get(dynamic.type, self._render_unknown)
        return handler(dynamic)

    def _render_header(self, dynamic: DynamicItem) -> str:
        """渲染动态头部（作者信息）"""
        author = dynamic.author
        action = author.pub_action or "发布了动态"
        time_str = author.pub_time or ""
        return f"🔔 {author.name} {action}\n⏰ {time_str}\n"

    def _render_video(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染视频动态"""
        header = self._render_header(dynamic)
        archive = dynamic.content.major.archive

        text = f"""{header}
📺 {archive.title}
⏱️ 时长: {archive.duration_text}
▶️ {archive.stat.play} 播放 | 💬 {archive.stat.danmaku} 弹幕

📝 {archive.desc[:100]}{'...' if len(archive.desc) > 100 else ''}

🔗 https://www.bilibili.com/video/{archive.bvid}"""

        return RenderedContent(text=text, images=[archive.cover])

    def _render_draw(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染图文动态"""
        header = self._render_header(dynamic)
        desc = dynamic.content.desc.text if dynamic.content.desc else ""
        draw = dynamic.content.major.draw

        text = f"""{header}
📝 {desc}

🖼️ 共 {len(draw.items)} 张图片"""

        # 最多取前4张图片
        images = [item.src for item in draw.items[:4]]
        return RenderedContent(text=text, images=images)

    def _render_word(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染纯文字动态"""
        header = self._render_header(dynamic)
        desc = dynamic.content.desc.text if dynamic.content.desc else ""

        text = f"""{header}
📝 {desc}"""

        return RenderedContent(text=text)

    def _render_forward(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染转发动态"""
        header = self._render_header(dynamic)
        desc = dynamic.content.desc.text if dynamic.content.desc else ""

        # 渲染原动态
        orig_content = ""
        if dynamic.orig:
            orig_rendered = self.render(dynamic.orig)
            orig_content = f"\n━━━ 原动态 ━━━\n{orig_rendered.text}"

        text = f"""{header}
💬 {desc}
{orig_content}"""

        return RenderedContent(text=text)

    def _render_article(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染专栏文章动态"""
        header = self._render_header(dynamic)
        article = dynamic.content.major.article

        text = f"""{header}
📑 {article.title}

📝 {article.desc[:150]}{'...' if len(article.desc) > 150 else ''}

🔗 https://www.bilibili.com/read/cv{article.id}"""

        images = article.covers[:1] if article.covers else []
        return RenderedContent(text=text, images=images)

    def _render_music(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染音乐动态"""
        header = self._render_header(dynamic)
        music = dynamic.content.major.music

        text = f"""{header}
🎵 {music.title}

🔗 https://www.bilibili.com/audio/au{music.id}"""

        return RenderedContent(text=text, images=[music.cover])

    def _render_common(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染通用卡片动态"""
        header = self._render_header(dynamic)
        common = dynamic.content.major.common

        text = f"""{header}
📌 {common.title}

📝 {common.desc}

🔗 {common.url}"""

        return RenderedContent(text=text, images=[common.cover])

    def _render_unknown(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染未知类型动态"""
        header = self._render_header(dynamic)

        text = f"""{header}
⚠️ 暂不支持的动态类型: {dynamic.type}

🔗 https://t.bilibili.com/{dynamic.id_str}"""

        return RenderedContent(text=text)
```

### 5.3 视频渲染器 (`renderer/video_renderer.py`)

```python
from ..models.video import VideoInfo
from .base import BaseRenderer, RenderedContent

class VideoRenderer(BaseRenderer):
    """视频信息渲染器"""

    def render(self, video: VideoInfo) -> RenderedContent:
        """渲染视频详细信息"""
        stat = video.stat

        text = f"""📺 {video.title}

👤 UP主: {video.owner.name}
📁 分区: {video.tname}
⏱️ 时长: {video.duration_text}

📊 数据统计:
  ▶️ {self._format_num(stat.view)} 播放
  💬 {self._format_num(stat.danmaku)} 弹幕
  💰 {self._format_num(stat.coin)} 投币
  ⭐ {self._format_num(stat.favorite)} 收藏
  👍 {self._format_num(stat.like)} 点赞

📝 简介:
{video.desc[:200]}{'...' if len(video.desc) > 200 else ''}

🔗 {video.url}"""

        return RenderedContent(text=text, images=[video.pic])

    @staticmethod
    def _format_num(num: int) -> str:
        """格式化数字"""
        if num >= 100000000:
            return f"{num / 100000000:.1f}亿"
        elif num >= 10000:
            return f"{num / 10000:.1f}万"
        return str(num)
```

---

## 6. 客户端 API 扩展

### 6.1 新增 API 方法 (`client.py`)

```python
class BiliClient:
    # ... 现有方法 ...

    async def get_video_info(self, bvid: str = None, aid: int = None) -> Optional[VideoInfo]:
        """
        获取视频详细信息
        API: https://api.bilibili.com/x/web-interface/view
        """
        url = f"{self.api_base_url}/x/web-interface/view"
        params = {}
        if bvid:
            params["bvid"] = bvid
        elif aid:
            params["aid"] = aid
        else:
            return None

        try:
            response = await self.client.get(url, params=params)
            data = response.json()
            if data.get("code") == 0:
                return VideoInfo(**data["data"])
        except Exception as e:
            logger.warn("BiliClient", f"获取视频信息失败: {e}")
        return None

    async def get_user_info(self, mid: int) -> Optional[UserCard]:
        """
        获取用户名片信息
        API: https://api.bilibili.com/x/web-interface/card
        """
        url = f"{self.api_base_url}/x/web-interface/card"
        params = {"mid": mid, "photo": "true"}

        try:
            response = await self.client.get(url, params=params)
            data = response.json()
            if data.get("code") == 0:
                return UserCard(**data["data"])
        except Exception as e:
            logger.warn("BiliClient", f"获取用户信息失败: {e}")
        return None

    async def get_dynamic_detail(self, dynamic_id: str, cookies: BiliCookie) -> Optional[DynamicItem]:
        """
        获取单条动态详情
        API: https://api.bilibili.com/x/polymer/web-dynamic/v1/detail
        """
        url = f"{self.api_base_url}/x/polymer/web-dynamic/v1/detail"
        params = {"id": dynamic_id}

        cookie_dict = self._make_cookie_dict(cookies)

        try:
            response = await self.client.get(url, params=params, cookies=cookie_dict)
            data = response.json()
            if data.get("code") == 0 and data.get("data", {}).get("item"):
                return DynamicItem(**data["data"]["item"])
        except Exception as e:
            logger.warn("BiliClient", f"获取动态详情失败: {e}")
        return None
```

---

## 7. 服务层更新

### 7.1 BiliService 更新 (`service.py`)

```python
from .renderer.dynamic_renderer import DynamicRenderer
from .renderer.video_renderer import VideoRenderer
from .renderer.base import RenderedContent

class BiliService:
    def __init__(self):
        self.client = BiliClient()
        self.cookie_file = "cache/bilibili_cookies.json"
        self.qr_generator = QRCodeGenerator()
        self.cookie_refresher = CookieRefresher(self.client.client)

        # 新增渲染器
        self.dynamic_renderer = DynamicRenderer()
        self.video_renderer = VideoRenderer()

    # ... 现有方法保持不变 ...

    async def get_video_info(self, bvid: str = None, aid: int = None) -> Optional[VideoInfo]:
        """获取视频信息"""
        return await self.client.get_video_info(bvid=bvid, aid=aid)

    async def get_user_info(self, mid: int) -> Optional[UserCard]:
        """获取用户信息"""
        return await self.client.get_user_info(mid)

    def render_dynamic(self, dynamic: DynamicItem) -> RenderedContent:
        """渲染动态内容"""
        return self.dynamic_renderer.render(dynamic)

    def render_video(self, video: VideoInfo) -> RenderedContent:
        """渲染视频信息"""
        return self.video_renderer.render(video)
```

---

## 8. 调度器更新

### 8.1 BilibiliScheduler 更新 (`core/pusher/bilibili_scheduler.py`)

```python
# 移除 screenshot 依赖
# from service.bilibili.utils.screenshot import BilibiliScreenshot

class BilibiliScheduler:
    def __init__(self, http_client):
        self.service = BiliService()
        self.client: NapCatHttpClient = http_client
        # 移除: self.screenshot = BilibiliScreenshot()

        # ... 其他初始化代码 ...

    async def check_new_dynamics(self, up_uid: str) -> List[RenderedContent]:
        """检查UP主是否有新动态，返回渲染后的内容列表"""
        try:
            current_baseline = self.update_baselines.get(up_uid, "")

            dynamics = await self.service.get_user_dynamics(int(up_uid))
            if not dynamics or not dynamics.data or not dynamics.data.items:
                return []

            rendered_contents = []

            for dynamic in dynamics.data.items:
                # 检查是否为新动态
                if dynamic.id_str == current_baseline:
                    break

                # 使用渲染器替代截图
                content = self.service.render_dynamic(dynamic)
                rendered_contents.append(content)

            # 更新 baseline
            if dynamics.data.items:
                new_baseline = dynamics.data.items[0].id_str
                self.update_baselines[up_uid] = new_baseline
                self.save_update_baselines()

            return rendered_contents

        except Exception as e:
            logger.warn("BilibiliScheduler", f"检查UP主 {up_uid} 新动态时出错: {e}")
            return []

    async def _check_all_subscriptions(self):
        """检查所有订阅的UP主是否有新动态"""
        all_ups = set()
        for group_ups in self.subscriptions.values():
            all_ups.update(group_ups)

        for up_uid in all_ups:
            try:
                new_contents = await self.check_new_dynamics(up_uid)
                if new_contents:
                    logger.info("BilibiliScheduler", f"UP主 {up_uid} 有 {len(new_contents)} 条新动态")

                    for group_id, subscribed_ups in self.subscriptions.items():
                        if up_uid in subscribed_ups:
                            for content in new_contents:
                                await self._send_rendered_content(int(group_id), content)

            except Exception as e:
                logger.warn("BilibiliScheduler", f"处理UP主 {up_uid} 动态时出错: {e}")

    async def _send_rendered_content(self, group_id: int, content: RenderedContent):
        """发送渲染后的内容到群"""
        try:
            # 发送文本
            await self.client.send_group_msg(group_id, content.text)

            # 发送图片（如果有）
            for image_url in content.images:
                cq_image = f"[CQ:image,file={image_url}]"
                await self.client.send_group_msg(group_id, cq_image)

        except Exception as e:
            logger.warn("BilibiliScheduler", f"发送动态到群 {group_id} 时出错: {e}")
```

---

## 9. Handler 命令扩展

### 9.1 新增命令 (`core/handler.py`)

```python
class Handler:
    # ... 现有方法 ...

    async def bilibili_handler(self, message: GroupMessage, clean_text: str):
        """处理 B站 相关命令"""
        parts = clean_text.split(maxsplit=2)

        if len(parts) < 2:
            await self._send_bilibili_help(message.group_id)
            return

        sub_cmd = parts[1]

        if sub_cmd == "订阅":
            # 现有订阅逻辑
            pass
        elif sub_cmd == "取消订阅":
            # 现有取消订阅逻辑
            pass
        elif sub_cmd == "视频":
            # 新增：视频信息查询
            if len(parts) < 3:
                await self.client.send_group_msg(message.group_id, "请提供视频 BV 号，例如：/b站 视频 BV1xx411c7mD")
                return
            await self._handle_video_info(message.group_id, parts[2])
        elif sub_cmd == "UP主":
            # 新增：UP主信息查询
            if len(parts) < 3:
                await self.client.send_group_msg(message.group_id, "请提供 UP主 UID，例如：/b站 UP主 123456")
                return
            await self._handle_user_info(message.group_id, parts[2])
        else:
            await self._send_bilibili_help(message.group_id)

    async def _handle_video_info(self, group_id: int, bvid: str):
        """处理视频信息查询"""
        video = await self.bili_service.get_video_info(bvid=bvid)
        if not video:
            await self.client.send_group_msg(group_id, f"未找到视频: {bvid}")
            return

        content = self.bili_service.render_video(video)
        await self.client.send_group_msg(group_id, content.text)

        for image_url in content.images:
            await self.client.send_group_msg(group_id, f"[CQ:image,file={image_url}]")

    async def _handle_user_info(self, group_id: int, mid_str: str):
        """处理 UP主 信息查询"""
        try:
            mid = int(mid_str)
        except ValueError:
            await self.client.send_group_msg(group_id, "UID 格式错误，请输入数字")
            return

        user = await self.bili_service.get_user_info(mid)
        if not user:
            await self.client.send_group_msg(group_id, f"未找到 UP主: {mid}")
            return

        text = f"""👤 {user.info.name}
🆔 UID: {user.info.mid}
📝 {user.info.sign or '这个人很懒，什么都没写'}

👥 粉丝: {user.stat.follower}
➕ 关注: {user.stat.following}"""

        await self.client.send_group_msg(group_id, text)
        await self.client.send_group_msg(group_id, f"[CQ:image,file={user.info.face}]")
```

---

## 10. 迁移计划

### 10.1 阶段一：模型重构（低风险）
1. 创建 `models/` 目录，迁移并完善数据模型
2. 更新 `client.py` 使用新模型
3. 保持 `screenshot.py` 暂不删除

### 10.2 阶段二：渲染器实现（中风险）
1. 创建 `renderer/` 目录，实现各渲染器
2. 更新 `BiliService` 集成渲染器
3. 单元测试渲染逻辑

### 10.3 阶段三：调度器切换（高风险）
1. 更新 `BilibiliScheduler` 使用渲染器
2. 灰度测试（保留截图作为 fallback）
3. 确认稳定后移除截图依赖

### 10.4 阶段四：功能扩展（低风险）
1. 添加视频信息查询功能
2. 添加 UP主 信息查询功能
3. 更新帮助文档

---

## 11. 风险与应对

| 风险 | 影响 | 应对措施 |
|-----|------|---------|
| API 字段变更 | 模型解析失败 | 使用 `Optional` + 默认值，记录警告日志 |
| 图片 URL 失效 | 用户无法查看图片 | 检测失效后尝试重新获取 |
| 渲染内容过长 | 消息被截断 | 设置最大长度，超出时省略 |
| 转发链过深 | 递归渲染栈溢出 | 限制转发深度为 2 层 |

---

## 12. 后续优化方向

1. **缓存机制**: 对频繁查询的视频/用户信息添加 Redis 缓存
2. **图片代理**: 自建图片代理避免 B站防盗链
3. **Wbi 签名**: 实现 Wbi 签名支持更多 API
4. **评论获取**: 支持获取热门评论
5. **番剧信息**: 扩展番剧相关 API 支持
