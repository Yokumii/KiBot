"""
KiBot 主入口文件

使用 FastAPI + Webhook 模式接收 NapCat 事件推送
"""
import asyncio
import uvicorn

from core.bot_core import Bot
from infra.logger import Logger


async def main():
    """主函数：初始化 Bot 并启动服务"""
    # 创建 Bot 实例
    bot = Bot.create()

    # 启动定时推送任务
    bot.start_pusher()

    # 配置 uvicorn 服务器
    config = uvicorn.Config(
        app=bot.webhook_server.get_app(),
        host=bot.settings.WEBHOOK_HOST,
        port=bot.settings.WEBHOOK_PORT,
        log_level="info",
        access_log=True,
    )

    server = uvicorn.Server(config)

    Logger.info("Main", f"Starting KiBot webhook server on {bot.settings.WEBHOOK_HOST}:{bot.settings.WEBHOOK_PORT}")
    Logger.info("Main", f"Webhook endpoint: http://{bot.settings.WEBHOOK_HOST}:{bot.settings.WEBHOOK_PORT}/webhook")
    Logger.info("Main", f"Health check: http://{bot.settings.WEBHOOK_HOST}:{bot.settings.WEBHOOK_PORT}/health")

    # 启动服务器
    await server.serve()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        Logger.info("Main", "Received shutdown signal, exiting gracefully...")
    except Exception as e:
        Logger.error("Main", f"Unexpected error: {e}")
        raise
