import asyncio
import json
import websockets
from typing import Awaitable, Callable

from infra.logger import Logger
from .models import GroupMessage

Handler = Callable[[GroupMessage], Awaitable[None]]


class NapCatWsClient:
    def __init__(self, ws_url: str, handler: Handler):
        self._url = ws_url
        self._handler = handler

    async def start(self):
        while True:
            try:
                async with websockets.connect(self._url) as ws:
                    Logger.info("WebSocket", "{} Connected".format(self._url))
                    async for raw in ws:
                        await self._dispatch(raw)
            except Exception as e:
                print(f"[WS] reconnecting... ({e})")
                await asyncio.sleep(5)

    async def _dispatch(self, raw: str):
        data = json.loads(raw)
        if data.get("post_type") == "message" and data.get("message_type") == "group":
            await self._handler(GroupMessage.model_validate(data))
