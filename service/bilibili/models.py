from typing import Optional, List, Dict, Any
from pydantic import BaseModel


# 二维码登录相关模型
class QRCodeGenerateResponse(BaseModel):
    """二维码生成响应"""
    code: int
    message: str
    ttl: int
    data: Optional['QRCodeData'] = None


class QRCodeData(BaseModel):
    """二维码数据"""
    url: str
    qrcode_key: str


class QRCodePollResponse(BaseModel):
    """二维码轮询响应"""
    code: int
    message: str
    data: Optional['QRCodePollData'] = None


class QRCodePollData(BaseModel):
    """二维码轮询数据"""
    url: str
    refresh_token: str
    timestamp: int
    code: int
    message: str


class BiliCookie(BaseModel):
    """B站Cookie信息"""
    DedeUserID: str
    DedeUserID__ckMd5: str
    SESSDATA: str
    bili_jct: str


# 动态相关模型，具体格式参考
# https://socialsisteryi.github.io/bilibili-API-collect/docs/dynamic/all.html#%E8%8E%B7%E5%8F%96%E5%85%A8%E9%83%A8%E5%8A%A8%E6%80%81%E5%88%97%E8%A1%A8
# 二编，获取动态所使用的API针对部分类型的动态返回的动态内容并不全，所以下面的数据模型基本没用，留着以后再完善吧
class DynamicResponse(BaseModel):
    """动态列表响应"""
    code: int
    message: str
    ttl: int
    data: Optional['DynamicData'] = None


class DynamicData(BaseModel):
    """动态数据"""
    has_more: bool
    items: List['DynamicItem']
    offset: str
    update_baseline: str
    update_num: int


class DynamicItem(BaseModel):
    """动态条目"""
    basic: 'DynamicBasic'
    id_str: str
    modules: 'DynamicModules'
    type: str   # 动态类型，具体见
    # https://socialsisteryi.github.io/bilibili-API-collect/docs/dynamic/dynamic_enum.html#%E5%8A%A8%E6%80%81%E7%B1%BB%E5%9E%8B
    visible: bool
    orig: Optional['DynamicItem'] = None


class DynamicBasic(BaseModel):
    """动态基础信息"""
    comment_id_str: str   # 需要用，与动态类型有关，比如 DYNAMIC_TYPE_AV 则代表发布视频的AV号	
    comment_type: int   # 数字标识符，没啥用
    like_icon: Dict[str, Any]   # 鸟用没有
    rid_str: str   # 和 comment_id_str 差不多，没啥用


class DynamicModules(BaseModel):
    """动态模块信息"""
    module_author: 'ModuleAuthor'   # UP主信息
    module_dynamic: 'ModuleDynamic'   # 动态内容信息	
    module_more: Optional[Dict[str, Any]] = None
    module_stat: Optional[Dict[str, Any]] = None
    module_interaction: Optional[Dict[str, Any]] = None
    module_fold: Optional[Dict[str, Any]] = None
    module_dispute: Optional[Dict[str, Any]] = None
    module_tag: Optional[Dict[str, Any]] = None


class ModuleAuthor(BaseModel):
    """UP主信息"""
    face: str
    face_nft: bool
    following: Optional[bool]
    jump_url: str
    label: str
    mid: int
    name: str
    pub_action: Optional[str] = None  # 发布动作，如"发布了视频"、"发布了动态"等
    official_verify: Optional[Dict[str, Any]] = None


class ModuleDynamic(BaseModel):
    """动态内容信息"""
    additional: Optional[Dict[str, Any]] = None   # 内容卡片信息，不管
    desc: Optional['DynamicDesc'] = None   # 动态文字内容
    major: Optional['DynamicMajor'] = None   # 动态主体对象，转发动态为NULL
    topic: Optional[Dict[str, Any]] = None   # 话题，不管


class DynamicDesc(BaseModel):
    """动态描述"""
    rich_text_nodes: Optional[List[Dict[str, Any]]] = None   # 富文本内容
    text: str   # 纯文本内容


class DynamicMajor(BaseModel):
    """动态主要内容"""
    archive: Optional[Dict[str, Any]] = None
    draw: Optional[Dict[str, Any]] = None
    article: Optional[Dict[str, Any]] = None
    live_rcmd: Optional[Dict[str, Any]] = None
    ugc_season: Optional[Dict[str, Any]] = None
    live: Optional[Dict[str, Any]] = None
    music: Optional[Dict[str, Any]] = None
    common: Optional[Dict[str, Any]] = None
    type: str


# Cookie刷新相关模型
class CookieInfoResponse(BaseModel):
    """Cookie信息检查响应"""
    code: int
    message: str
    ttl: int
    data: Optional['CookieInfoData'] = None


class CookieInfoData(BaseModel):
    """Cookie信息数据"""
    refresh: bool
    timestamp: int


class CookieRefreshResponse(BaseModel):
    """Cookie刷新响应"""
    code: int
    message: str
    ttl: int
    data: Optional['CookieRefreshData'] = None


class CookieRefreshData(BaseModel):
    """Cookie刷新数据"""
    status: int
    message: str
    refresh_token: str


class CookieConfirmResponse(BaseModel):
    """Cookie确认响应"""
    code: int
    message: str
    ttl: int


# ==================== 视频相关模型 ====================

class VideoInfoResponse(BaseModel):
    """视频信息响应"""
    code: int
    message: str
    ttl: int
    data: Optional['VideoInfo'] = None


class VideoInfo(BaseModel):
    """视频信息"""
    aid: int
    bvid: str
    cid: Optional[int] = None
    copyright: int  # 1:原创 2:转载
    ctime: int  # 创建时间戳
    desc: str  # 视频简介
    desc_v2: Optional[List[Dict[str, Any]]] = None
    dimension: Optional[Dict[str, Any]] = None
    duration: int  # 视频时长（秒）
    dynamic: str  # 同步发布的动态文字
    owner: Optional['VideoOwner'] = None
    pages: Optional[List['VideoPage']] = None
    pic: str  # 封面图
    pubdate: int  # 发布时间戳
    redirect_url: Optional[str] = None
    season_id: Optional[int] = None
    staff: Optional[List[Dict[str, Any]]] = None
    stat: Optional['VideoStat'] = None
    subtitle: Optional[Dict[str, Any]] = None
    tid: int  # 分区ID
    title: str
    tname: str  # 分区名称
    videos: int  # 分P数
    rights: Optional[Dict[str, Any]] = None
    is_chargeable_season: bool = False
    is_story: bool = False
    is_upower_exclusive: bool = False


class VideoOwner(BaseModel):
    """视频UP主信息"""
    mid: int
    name: str
    face: str


class VideoPage(BaseModel):
    """视频分P信息"""
    cid: int
    page: int
    part: str
    duration: int


class VideoStat(BaseModel):
    """视频统计数据"""
    aid: int
    view: int  # 播放数
    danmaku: int  # 弹幕数
    reply: int  # 评论数
    favorite: int  # 收藏数
    coin: int  # 投币数
    share: int  # 分享数
    like: int  # 点赞数
    now_rank: int
    his_rank: int
    evaluation: str
    vt: int


class VideoSearchResult(BaseModel):
    """视频搜索结果"""
    code: int
    message: str
    ttl: int
    data: Optional['VideoSearchData'] = None


class VideoSearchData(BaseModel):
    """视频搜索数据"""
    list: Optional['VideoList'] = None
    page: Optional['VideoSearchPage'] = None


class VideoList(BaseModel):
    """视频列表"""
    tlist: Optional[Dict[str, 'VideoTypeInfo']] = None
    vlist: List['VideoSimple']


class VideoTypeInfo(BaseModel):
    """视频类型信息"""
    count: int
    name: str
    tid: int


class VideoSimple(BaseModel):
    """简单视频信息"""
    aid: int
    bvid: str
    title: str
    pic: str
    author: str
    mid: int
    created: int
    length: str
    description: str
    typeid: int
    typename: str
    play: int  # 播放数
    video_review: int  # 弹幕数
    favorites: int  # 收藏数
    tag: str
    review: int  # 评论数


class VideoSearchPage(BaseModel):
    """视频搜索分页信息"""
    count: int
    pn: int
    ps: int


# ==================== 直播相关模型 ====================

class LiveRoomInfoResponse(BaseModel):
    """直播间信息响应"""
    code: int
    message: str
    msg: Optional[str] = None
    data: Optional['LiveRoomInfo'] = None


class LiveRoomInfo(BaseModel):
    """直播间信息"""
    uid: int
    room_id: int
    short_id: int
    attention: int  # 关注数
    online: int  # 观看人数
    is_portrait: bool
    description: str
    live_status: int  # 0:未开播 1:直播中 2:轮播中
    area_id: int
    parent_area_id: int
    parent_area_name: str
    old_area_id: int
    background: str
    title: str
    user_cover: str
    keyframe: str
    is_strict_room: bool
    live_time: str
    tags: str
    area_name: str


class LiveInfoResponse(BaseModel):
    """直播详情响应"""
    code: int
    message: str
    msg: Optional[str] = None
    data: Optional['LiveInfo'] = None


class LiveInfo(BaseModel):
    """直播详情"""
    room_info: Optional['LiveRoomInfo'] = None
    anchor_info: Optional[Dict[str, Any]] = None


# ==================== 用户相关模型 ====================

class UserInfoResponse(BaseModel):
    """用户信息响应"""
    code: int
    message: str
    ttl: int
    data: Optional['UserInfo'] = None


class UserInfo(BaseModel):
    """用户信息"""
    mid: int
    name: str
    sex: str
    face: str
    face_nft: int
    sign: str
    rank: int
    level: int
    jointime: int
    moral: int
    silence: int
    coins: int
    fans_badge: bool
    official: Optional[Dict[str, Any]] = None
    vip: Optional[Dict[str, Any]] = None
    pendant: Optional[Dict[str, Any]] = None
    nameplate: Optional[Dict[str, Any]] = None
    is_followed: bool
    top_photo: str
    live_room: Optional[Dict[str, Any]] = None


# ==================== 剧集相关模型 ====================

class SeasonInfoResponse(BaseModel):
    """剧集信息响应"""
    code: int
    message: str
    result: Optional['SeasonInfo'] = None


class SeasonInfo(BaseModel):
    """剧集信息"""
    season_id: int
    title: str
    cover: str
    evaluate: str
    new_ep: Optional[Dict[str, Any]] = None
    episodes: Optional[List['SeasonEpisode']] = None


class SeasonEpisode(BaseModel):
    """剧集分集信息"""
    aid: int
    bvid: str
    cid: int
    cover: str
    duration: int
    ep_id: int
    index: str
    long_title: str
    pub_time: int
    title: str


# ==================== 搜索相关模型 ====================

class SearchResponse(BaseModel):
    """搜索响应"""
    code: int
    message: str
    ttl: int
    data: Optional['SearchData'] = None


class SearchData(BaseModel):
    """搜索数据"""
    result: Optional[List[Dict[str, Any]]] = None
    pages: Optional[int] = None
    numResults: Optional[int] = None
    numPages: Optional[int] = None


# ==================== 导航栏/WBI相关模型 ====================

class NavInfoResponse(BaseModel):
    """导航栏信息响应（用于获取WBI密钥）"""
    code: int
    message: str
    ttl: int
    data: Optional['NavInfo'] = None


class NavInfo(BaseModel):
    """导航栏信息"""
    isLogin: bool
    wbi_img: Optional['WbiImages'] = None


class WbiImages(BaseModel):
    """WBI图片密钥"""
    img_url: str
    sub_url: str


# ==================== 异常类 ====================
# 异常类已移至 exceptions.py，这里保留以保持向后兼容
from .exceptions import BiliAPIException


# ==================== 延迟解析，避免类型检查出错 ====================
QRCodeGenerateResponse.model_rebuild()
QRCodePollResponse.model_rebuild()
DynamicResponse.model_rebuild()
CookieInfoResponse.model_rebuild()
CookieRefreshResponse.model_rebuild()
VideoInfoResponse.model_rebuild()
VideoSearchResult.model_rebuild()
LiveRoomInfoResponse.model_rebuild()
LiveInfoResponse.model_rebuild()
UserInfoResponse.model_rebuild()
SeasonInfoResponse.model_rebuild()
SearchResponse.model_rebuild()
NavInfoResponse.model_rebuild()
