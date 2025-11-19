from adapter.napcat.models import GroupMessage
from infra.config.settings import Settings
from infra.logger import Logger
from adapter.napcat.webhook_server import WebhookServer
from adapter.napcat.http_api import NapCatHttpClient
from .pusher.pusher import Pusher
from .router import Router
from .handler import Handler


class Bot:
    def __init__(self, settings, info, router, http_client, webhook_server, handler, pusher):
        self.settings = settings
        self.info = info
        self.router = router
        self.http_client = http_client
        self.webhook_server = webhook_server
        self.handler = handler
        self.pusher = pusher

    @classmethod
    def create(cls) -> "Bot":
        settings = Settings()
        http_client = NapCatHttpClient(settings.NAPCAT_HTTP, settings.NAPCAT_HTTP_AUTH_TOKEN)
        login_info = http_client.get_login_info_sync()
        router = Router(login_info["user_id"])
        handler = Handler(http_client)
        pusher = Pusher(http_client, handler)

        # 创建消息处理回调函数
        async def on_msg(msg: GroupMessage):
            Logger.info("Message received", f"[{msg.group_id}:{msg.sender.nickname}({msg.user_id})] {msg.raw_message}")
            await router.dispatch(msg, handler)

        # 创建 Webhook 服务器
        webhook_server = WebhookServer(
            secret_token=settings.NAPCAT_WEBHOOK_SECRET,
            message_handler=on_msg
        )

        return cls(settings, login_info, router, http_client, webhook_server, handler, pusher)

    def start_pusher(self):
        """启动定时推送任务"""
        Logger.info("BotCore", "NapCat登录账号: {}({})".format(self.info["nickname"], self.info["user_id"]))
        self.pusher.start()
        Logger.info("BotCore", "Pusher started")
