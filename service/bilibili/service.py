import json
import os
from datetime import datetime
from typing import Optional, Tuple

from infra.logger import logger
from .client import BiliClient
from .models import BiliCookie
from .api.login import LoginAPI
from .api.dynamic import DynamicAPI
from .api.video import VideoAPI
from .api.live import LiveAPI
from .api.season import SeasonAPI
from .api.search import SearchAPI
from .api.user import UserAPI
from .parser import BilibiliParser
from .search_service import BilibiliSearchService
from .utils.cookie_refresher import CookieRefresher
from .utils.qrcode_generator import QRCodeGenerator


class BiliService:
    def __init__(self):
        self.client = BiliClient()
        self.login_api = LoginAPI(self.client)
        self.dynamic_api = DynamicAPI(self.client)
        self.video_api = VideoAPI(self.client)
        self.live_api = LiveAPI(self.client)
        self.season_api = SeasonAPI(self.client)
        self.search_api = SearchAPI(self.client)
        self.user_api = UserAPI(self.client)
        self.cookie_file = "cache/bilibili_cookies.json"
        self.qr_generator = QRCodeGenerator()
        # Cookie刷新器使用BiliClient以支持限流等功能
        self.cookie_refresher = CookieRefresher(self.client)
        
        # 初始化解析器和搜索服务
        async def _get_cookies():
            """获取Cookie的包装函数"""
            result = await self.get_valid_cookies()
            return result[0] if result else None
        
        self.parser = BilibiliParser(
            dynamic_api=self.dynamic_api,
            video_api=self.video_api,
            live_api=self.live_api,
            season_api=self.season_api,
            user_api=self.user_api,
            get_cookies=_get_cookies
        )
        self.search_service = BilibiliSearchService(
            search_api=self.search_api,
            user_api=self.user_api,
            season_api=self.season_api,
            video_api=self.video_api,
            get_cookies=_get_cookies
        )

    async def generate_login_qrcode(self) -> Optional[Tuple[str, str]]:
        """
        生成登录二维码
        """
        return await self.login_api.generate_qrcode()

    async def wait_for_qrcode_login(self, qrcode_key: str, timeout: int = 180) -> Optional[Tuple[BiliCookie, str]]:
        """
        等待扫码登录完成
        """
        return await self.login_api.wait_for_login(qrcode_key, timeout)

    def save_cookies(self, cookies: BiliCookie, refresh_token: str = "") -> bool:
        """
        保存Cookie到文件
        """
        try:
            os.makedirs("cache", exist_ok=True)
            cookie_data = {
                "DedeUserID": cookies.DedeUserID,
                "DedeUserID__ckMd5": cookies.DedeUserID__ckMd5,
                "SESSDATA": cookies.SESSDATA,
                "bili_jct": cookies.bili_jct,
                "refresh_token": refresh_token,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(self.cookie_file, "w", encoding="utf-8") as f:
                json.dump(cookie_data, f, ensure_ascii=False, indent=2)
            
            return True
        except Exception as e:
            logger.warn("BiliService", f"保存Cookie失败: {e}")
            return False

    def load_cookies(self) -> Optional[Tuple[BiliCookie, str]]:
        """
        从文件加载Cookie和refresh_token
        """
        try:
            if not os.path.exists(self.cookie_file):
                return None
            
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                cookie_data = json.load(f)
            
            cookies = BiliCookie(
                DedeUserID=cookie_data["DedeUserID"],
                DedeUserID__ckMd5=cookie_data["DedeUserID__ckMd5"],
                SESSDATA=cookie_data["SESSDATA"],
                bili_jct=cookie_data["bili_jct"]
            )
            
            refresh_token = cookie_data.get("refresh_token", "")
            
            return cookies, refresh_token
        except Exception as e:
            logger.warn("BiliService", f"加载Cookie失败: {e}")
            return None

    def display_qrcode(self, qr_url: str, show_terminal: bool = True, save_image: bool = False):
        """
        显示二维码
        """
        if show_terminal:
            terminal_qr = self.qr_generator.generate_terminal_qr(qr_url)
            if terminal_qr:
                logger.info("BiliService", "请在B站APP中扫描以下二维码：")
                print("\n" + "="*50)
                print(terminal_qr)
                print("="*50 + "\n")
            else:
                logger.info("BiliService", f"请访问以下链接进行登录：{qr_url}")
        
        if save_image:
            # 保存二维码图片，这里再调用时选择不存了，图片存服务器上也没必要
            if self.qr_generator.save_qr_image(qr_url, "bilibili_login_qr.png"):
                logger.info("BiliService", "二维码图片已保存为 bilibili_login_qr.png")
            else:
                logger.warn("BiliService", "二维码图片保存失败")

    async def login_with_qrcode(self, show_terminal_qr: bool = True, save_qr_image: bool = False) \
            -> Optional[Tuple[BiliCookie, str]]:
        """
        扫码登录流程
        """
        qr_result = await self.generate_login_qrcode()
        if not qr_result:
            return None
        
        qr_url, qrcode_key = qr_result
        
        self.display_qrcode(qr_url, show_terminal_qr, save_qr_image)
        
        # 等待用户扫码登录，直接获取Cookie和refresh_token
        result = await self.wait_for_qrcode_login(qrcode_key)
        if not result:
            return None
        
        cookies, refresh_token = result
        
        if self.save_cookies(cookies, refresh_token):
            logger.info("BiliService", "Cookie和refresh_token保存成功！")
        else:
            logger.warn("BiliService", "Cookie和refresh_token保存失败！")
        
        return cookies, refresh_token

    async def get_valid_cookies(self) -> Optional[Tuple[BiliCookie, str]]:
        """
        获取有效的Cookie（包含自动刷新）
        """
        result = self.load_cookies()
        if not result:
            return None
        
        cookies, refresh_token = result
        
        refresh_result = await self.cookie_refresher.refresh_cookies_if_needed(cookies, refresh_token)
        if refresh_result:
            new_cookies, new_refresh_token = refresh_result
            if self.save_cookies(new_cookies, new_refresh_token):
                logger.info("BiliService", "Cookie刷新后已保存")
            return new_cookies, new_refresh_token
        
        return cookies, refresh_token

    async def ensure_valid_cookies(self) -> Optional[Tuple[BiliCookie, str]]:
        """
        确保Cookie有效，如果无效则重新登录
        """
        result = await self.get_valid_cookies()
        if result:
            return result
        
        logger.info("BiliService", "Cookie无效，需要重新登录")
        return await self.login_with_qrcode()
