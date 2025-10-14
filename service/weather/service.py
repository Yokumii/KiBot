import time
from pathlib import Path
from typing import Optional

from .models import WeatherResponse, WarningResponse, StormResponse
from .client import QWeatherClient
from .typhoon_renderer import TyphoonRenderer


class WeatherService:
    def __init__(self):
        self.client = QWeatherClient()
        self.typhoon_renderer = TyphoonRenderer()

    async def check_location(self, city: str) -> bool:
        location = await self.client.get_location(city)
        if not location:
            return False
        return True

    async def get_now(self, city: str) -> Optional[WeatherResponse]:
        location = await self.client.get_location(city)
        if not location:
            return None
        now = await self.client.get_now_weather(location.id)
        return WeatherResponse(location=location, now=now)

    async def get_today(self, city: str) -> Optional[WeatherResponse]:
        location = await self.client.get_location(city)
        if not location:
            return None
        today_forecast = await self.client.get_today_forecast(location.id)
        if today_forecast is None:
            return None
        return WeatherResponse(
            location=location,
            daily=[today_forecast]
        )

    async def get_warning(self, city: str) -> Optional[WarningResponse]:
        location = await self.client.get_location(city)
        if not location:
            return None
        warnings = await self.client.get_warning_info(location.id)
        if warnings is None:
            return None
        return WarningResponse(
            location=location,
            warningInfo=warnings
        )

    async def get_storm(self) -> Optional[list[list[StormResponse]]]:
        storms = await self.client.get_active_storm_list()
        resp: list[list[StormResponse]] = []
        if not storms:
            return None
        for storm in storms:
            storm_info = await self.client.get_now_storm_info(storm.id)
            if storm_info is None:
                continue
            storm_info_now, storm_info_track = storm_info
            storm_resp_item_now = StormResponse(
                storm=storm,
                stormInfo=storm_info_now
            )
            storm_resp_items = [StormResponse(
                storm=storm,
                stormInfo=storm_info
            ) for storm_info in storm_info_track]
            storm_resp_items.append(storm_resp_item_now)
            resp.append(storm_resp_items[::-1])
        if not resp:
            return None
        return resp

    def render_storm(self, storm: list[StormResponse]) -> str:
        if not storm:
            return ""

        typhoon_id = storm[0].storm.id  # 获取台风编号
        # 生成时间戳
        timestamp = int(time.time())
        output_dir = Path("cache/typhoon_images")
        # typhoon_ID_timestamp.png
        output_path = str(output_dir / f"typhoon_{typhoon_id}_{timestamp}.png")

        render_success = self.typhoon_renderer.render_to_file(
            storm_data=storm,
            output_path=output_path
        )

        if render_success:
            # 转为绝对路径返回
            return str(Path(output_path).resolve())
        else:
            return ""
