import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from adapter.napcat.http_api import NapCatHttpClient
from core.pusher.bangumi_scheduler import BangumiScheduler
from core.pusher.bilibili_scheduler import BilibiliScheduler
from core.pusher.weather_scheduler import WeatherScheduler
from infra.logger import logger
from service.bangumi.service import BangumiService
from service.bilibili.service import BiliService
from service.llm.chat import LLMService
from service.weather.service import WeatherService


class Handler:
    def __init__(self, client):
        self.client: NapCatHttpClient = client
        self.llm_svc: LLMService = LLMService()
        self.weather_svc: WeatherService = WeatherService()
        self.weather_scheduler = WeatherScheduler(self.client)
        self.bangumi_svc: BangumiService = BangumiService()
        self.bangumi_scheduler: BangumiScheduler = BangumiScheduler(self.client)
        self.bilibili_scheduler: BilibiliScheduler = BilibiliScheduler(self.client)
        self.bilibili_svc: BiliService = BiliService()

    async def reply_handler(self, group_id, msg, user_id):
        # resp = await self.llm_svc.chat(msg)
        # resp = await self.llm_svc.chat_with_memory(msg, group_id, user_id)
        resp = await self.llm_svc.agent_chat(msg, group_id, user_id)
        reply: str = resp.reply
        await self.client.send_group_msg(group_id, reply)

    async def weather_handler(self, group_id, msg: str):
        """
            /天气 [城市]         -> 实时天气
            /天气 预警 [城市]     -> 预警信息
            /天气 台风           -> 实时台风信息
            /天气 订阅 [城市]     -> 添加订阅城市
            /天气 取消订阅 [城市]  -> 删除订阅城市
        """
        default_msg = "天气服务由 和风天气 提供。\n"
        parts = msg.strip().split(maxsplit=1)
        if not parts or not parts[0]:
            logger.warn("Handler", "未指定城市")
            await self.client.send_group_msg(group_id, default_msg + "请指定城市，例如：/天气 北京")
            return

        # 判断是否以“预警”开头
        if parts[0] == "预警":
            if len(parts) == 1 or not parts[1].strip():
                await self.client.send_group_msg(group_id, default_msg + "请指定城市，例如：/天气 预警 北京")
                return
            city = parts[1].strip()
            warn_resp = await self.weather_svc.get_warning(city)
            if not warn_resp or not warn_resp.warningInfo:
                await self.client.send_group_msg(group_id, f"⚠️ 暂无「{city}」的预警信息")
                return
            alerts = "\n".join([f"⚠️ {w.title}\n{w.text}" for w in warn_resp.warningInfo])
            reply = f"🚨 {city} 气象预警\n{alerts}"
        elif parts[0] == "台风":
            storm_resp = await self.weather_svc.get_storm()
            if not storm_resp:
                await self.client.send_group_msg(group_id, "⚠️🌀 当前西北太平洋无活跃热带气旋/台风")
                return

            def parse_serial(st_id: str) -> int | None:
                pattern = re.compile(r'^NP_\d{2}(\d{2})$')
                m = pattern.match(st_id)
                return int(m.group(1)) if m else None

            cyclone_level_map = {
                "TD": "热带低压",
                "TS": "热带风暴",
                "STS": "强热带风暴",
                "TY": "台风",
                "STY": "强台风",
                "SuperTY": "超强台风",
            }

            lines = []
            for idx, item in enumerate(storm_resp, 1):
                s, info = item[0].storm, item[0].stormInfo
                storm_id = parse_serial(s.id)
                # 如果move360为空，则省略括号部分
                move_dir = f"{info.moveDir}" if not info.move360 else f"{info.moveDir}({info.move360}°)"
                lines.append(
                    f"{idx}. {s.name}（{s.year}年第{storm_id}号台风）\n"
                    f"   类型：{cyclone_level_map.get(info.type, '未知')}\n"
                    f"   位置：{info.lat}°N {info.lon}°E\n"
                    f"   气压：{info.pressure} hPa\n"
                    f"   风速：{info.windSpeed} m/s\n"
                    f"   移速：{info.moveSpeed} m/s {move_dir}"
                )
            reply = f"🌀 当前西北太平洋共有{len(storm_resp)}个活跃台风\n" + "\n".join(lines)
            await self.client.send_group_msg(group_id, reply)

            # 绘制台风路径图
            await self.client.send_group_msg(group_id, "希酱正在努力绘制台风路径图，请稍等哦~")

            executor = ThreadPoolExecutor(max_workers=2)

            def _render_sync(storm_data) -> str | None:
                try:
                    return self.weather_svc.render_storm(storm_data)
                except Exception as e:
                    logger.error("Weather", f"绘制台风路径时出现错误：{e}")
                    return None

            futures = [
                asyncio.get_running_loop().run_in_executor(executor, _render_sync, single_storm)
                for single_storm in storm_resp
            ]

            img_paths = await asyncio.gather(*futures)

            for single_storm, img_path in zip(storm_resp, img_paths):
                typhoon_name = single_storm[0].storm.name
                if img_path:
                    logger.info("Weather", f"台风「{typhoon_name}」路径已绘制，保存于{img_path}")
                    await self.client.send_group_image_msg(group_id, img_path)
                else:
                    logger.warn("Weather", f"台风「{typhoon_name}」路径绘制失败")

            return
        elif parts[0] == "订阅":
            if len(parts) == 1 or not parts[1].strip():
                await self.client.send_group_msg(group_id, default_msg + "请指定城市，例如：/天气 订阅 北京")
                return
            cities = [city.strip() for city in parts[1].strip().split()]
            for city in cities:
                if not await self.weather_svc.check_location(city):
                    await self.client.send_group_msg(group_id, f"⚠️ 未找到城市「{city}」或接口异常")
                    return
            self.weather_scheduler.subscribe(str(group_id), *cities)
            subscribed_cities = list(set(self.weather_scheduler.subscriptions.get(str(group_id), [])))
            reply = f"✅ 已成功订阅以下城市的天气更新：\n{', '.join(cities)}\n当前订阅列表：\n{', '.join(subscribed_cities)}"
        elif parts[0] == "取消订阅":
            if len(parts) == 1 or not parts[1].strip():
                await self.client.send_group_msg(group_id, default_msg + "请指定城市，例如：/天气 取消订阅 北京")
                return
            cities = [city.strip() for city in parts[1].strip().split()]
            for city in cities:
                self.weather_scheduler.unsubscribe(str(group_id), city)
            subscribed_cities = self.weather_scheduler.subscriptions.get(str(group_id), [])
            if subscribed_cities:
                reply = f"✅ 当前剩余订阅列表：\n{', '.join(subscribed_cities)}"
            else:
                reply = "✅ 当前没有订阅任何城市"
        else:
            city = parts[0]
            resp = await self.weather_svc.get_now(city)
            if not resp:
                logger.warn("Handler", "未找到城市")
                await self.client.send_group_msg(group_id, f"⚠️ 未找到城市「{city}」或接口异常")
                return
            reply = (
                f"🌤️ {resp.location.name} 实时天气\n"
                f"温度：{resp.now.temp}°C（体感 {resp.now.feelsLike}°C）\n"
                f"天气：{resp.now.text}\n"
                f"湿度：{resp.now.humidity}%\n"
                f"风力：{resp.now.windDir} {resp.now.windScale} 级"
            )

        await self.client.send_group_msg(group_id, reply)
    
    async def bangumi_handler(self, group_id, msg: str):
        default_msg = "番剧服务由 Bangumi 提供。\n"
        """统一处理番剧相关命令"""
        if msg.startswith("查询今日番剧放送") or msg.startswith("今日放送"):
            # 查询今日放送
            await self._handle_today_anime(group_id)
        elif msg.startswith("订阅每日番剧放送") or msg.startswith("订阅"):
            # 订阅番剧推送
            await self._handle_subscribe(group_id)
        elif msg.startswith("取消订阅每日番剧放送") or msg.startswith("取消订阅"):
            # 取消订阅番剧推送
            await self._handle_unsubscribe(group_id)
        else:
            logger.warn("Handler", "番剧指令输入不合法")
            await self.client.send_group_msg(group_id, default_msg + "请输入正确的指令，例如：/番剧 今日放送")

    async def _handle_today_anime(self, group_id):
        """处理今日放送查询"""
        anime_list = await self.bangumi_svc.get_today_anime()
        if not anime_list:
            await self.client.send_group_msg(group_id, "📺 今日暂无动画放送信息")
            return
        
        reply = "📺 今日放送\n\n"
        for anime in anime_list:
            name = anime.name_cn if anime.name_cn else anime.name
            score = f"🌟 {anime.rating.score}" if anime.rating.score > 0 else ""
            reply += f"🎬 {name} {score}\n"
            reply += f"🔗 {anime.url}\n\n"
        
        await self.client.send_group_msg(group_id, reply)

    async def _handle_subscribe(self, group_id):
        """处理订阅番剧推送"""
        self.bangumi_scheduler.subscribe(str(group_id))
        await self.client.send_group_msg(group_id, "✅ 本群已订阅每日番剧推送！每天早上8点会推送今日放送的动画信息。")

    async def _handle_unsubscribe(self, group_id):
        """处理取消订阅番剧推送"""
        self.bangumi_scheduler.unsubscribe(str(group_id))
        await self.client.send_group_msg(group_id, "❌ 本群已取消订阅每日番剧推送。")

    async def bilibili_handler(self, group_id, msg: str):
        """统一处理B站相关命令"""
        default_msg = "B站服务。API服务为 https://socialsisteryi.github.io/bilibili-API-collect/ 项目收集而来的野生 API ，请勿滥用！\n"
        
        parts = msg.strip().split(maxsplit=1)
        if len(parts) == 0:
            await self.client.send_group_msg(group_id, default_msg + "请输入正确的指令，例如：/b站 订阅 123456")
            return
        
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        if command == "订阅":
            if not args or not args.strip():
                await self.client.send_group_msg(group_id, "❌ 请指定UP主UID，例如：/b站 订阅 123456")
                return
            
            up_uid = args.strip().split()[0]
            if not up_uid.isdigit():
                await self.client.send_group_msg(group_id, "❌ 请输入正确的UP主UID")
                return
            
            await self._handle_bilibili_subscribe(group_id, up_uid)
            
        elif command == "取消订阅":
            if not args or not args.strip():
                await self.client.send_group_msg(group_id, "❌ 请指定UP主UID，例如：/b站 取消订阅 123456")
                return
            
            up_uid = args.strip().split()[0]
            if not up_uid.isdigit():
                await self.client.send_group_msg(group_id, "❌ 请输入正确的UP主UID")
                return
            
            await self._handle_bilibili_unsubscribe(group_id, up_uid)
            
        elif command == "查看订阅":
            await self._handle_bilibili_list_subscriptions(group_id)
            
        elif command == "检查":
            if not args or not args.strip():
                await self.client.send_group_msg(group_id, "❌ 请指定UP主UID，例如：/b站 检查 123456")
                return
            
            up_uid = args.strip().split()[0]
            if not up_uid.isdigit():
                await self.client.send_group_msg(group_id, "❌ 请输入正确的UP主UID")
                return
            
            await self._handle_bilibili_check_dynamics(group_id, up_uid)
        
        elif command == "搜索":
            if not args or not args.strip():
                await self.client.send_group_msg(group_id, "❌ 请指定搜索类型和关键词，例如：/b站 搜索 用户 关键词")
                return
            
            await self._handle_bilibili_search(group_id, args.strip())
        
        elif command == "信息":
            if not args or not args.strip():
                await self.client.send_group_msg(group_id, "❌ 请指定信息类型和ID，例如：/b站 信息 视频 BV1234567890")
                return
            
            await self._handle_bilibili_info(group_id, args.strip())
            
        else:
            await self.client.send_group_msg(group_id, default_msg + "支持的命令：订阅、取消订阅、查看订阅、检查、搜索、信息")

    async def _handle_bilibili_subscribe(self, group_id, up_uid: str):
        """处理订阅UP主动态推送"""
        from service.bilibili.subscription import TaskType
        
        group_id_str = str(group_id)
        
        # 检查是否已订阅
        task = self.bilibili_scheduler.manager.get_task(
            TaskType.DYNAMIC,
            target_id=up_uid,
            group_id=group_id_str
        )
        if task:
            await self.client.send_group_msg(group_id, f"⚠️ 本群已订阅UP主 {up_uid} 的动态推送")
            return
        
        # 添加订阅
        self.bilibili_scheduler.manager.add_subscription(
            TaskType.DYNAMIC,
            target_id=up_uid,
            group_id=group_id_str
        )
        await self.client.send_group_msg(group_id,
                                         f"✅ 本群已订阅UP主 {up_uid} 的动态推送！\n每5分钟会自动检查新动态并推送。")

    async def _handle_bilibili_unsubscribe(self, group_id, up_uid: str):
        """处理取消订阅UP主动态推送"""
        from service.bilibili.subscription import TaskType
        
        group_id_str = str(group_id)
        
        # 检查是否已订阅
        task = self.bilibili_scheduler.manager.get_task(
            TaskType.DYNAMIC,
            target_id=up_uid,
            group_id=group_id_str
        )
        if not task:
            await self.client.send_group_msg(group_id, f"⚠️ 本群未订阅UP主 {up_uid} 的动态推送")
            return
        
        # 移除订阅
        success = self.bilibili_scheduler.manager.remove_subscription(
            TaskType.DYNAMIC,
            target_id=up_uid,
            group_id=group_id_str
        )
        if success:
            await self.client.send_group_msg(group_id, f"❌ 本群已取消订阅UP主 {up_uid} 的动态推送")

    async def _handle_bilibili_list_subscriptions(self, group_id):
        """处理查看订阅列表"""
        from service.bilibili.subscription import TaskType
        
        group_id_str = str(group_id)
        tasks = self.bilibili_scheduler.manager.get_tasks_by_group(group_id_str)
        
        # 只显示动态类型的订阅
        dynamic_tasks = [task for task in tasks if task.task_type == TaskType.DYNAMIC]
        
        if not dynamic_tasks:
            await self.client.send_group_msg(group_id, "📢 本群暂无订阅的UP主")
            return
        
        reply = "📢 本群订阅的UP主：\n"
        for task in dynamic_tasks:
            reply += f"• {task.target_id}\n"
        
        await self.client.send_group_msg(group_id, reply)

    async def _handle_bilibili_check_dynamics(self, group_id, up_uid: str):
        """处理手动检查UP主动态"""
        from service.bilibili.subscription import TaskType
        
        await self.client.send_group_msg(group_id, "🔍 正在检查UP主动态...")
        
        try:
            group_id_str = str(group_id)
            task = self.bilibili_scheduler.manager.get_task(
                TaskType.DYNAMIC,
                target_id=up_uid,
                group_id=group_id_str
            )
            
            if not task:
                await self.client.send_group_msg(group_id, f"❌ 本群未订阅UP主 {up_uid} 的动态推送")
                return
            
            # 手动触发检查任务（临时清除last_item_id以强制检查所有新动态）
            original_last_item_id = task.last_item_id
            task.last_item_id = None
            
            try:
                await self.bilibili_scheduler.scheduler._check_dynamic_task(task)
                await self.client.send_group_msg(group_id, "📢 检查完毕：已发送新动态（如有）")
            finally:
                # 如果任务没有被更新，恢复原来的值
                # 注意：_check_dynamic_task 内部会调用 update_last_check，会自动保存
                # 如果检查失败没有更新，则恢复原值
                if task.last_item_id is None and original_last_item_id:
                    task.last_item_id = original_last_item_id
                    # 通过更新任务来触发保存
                    self.bilibili_scheduler.manager.update_last_check(task.task_id, original_last_item_id)
        except Exception as e:
            logger.warn("Handler", f"检查UP主 {up_uid} 动态时出错: {e}")
            await self.client.send_group_msg(group_id, "❌ 检查动态时出现错误")
    
    async def _handle_bilibili_search(self, group_id, args: str):
        """处理B站搜索"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self.client.send_group_msg(group_id, "❌ 请指定搜索类型和关键词\n例如：/b站 搜索 用户 关键词")
            return
        
        search_type = parts[0].lower()
        keyword = parts[1]
        
        await self.client.send_group_msg(group_id, f"🔍 正在搜索「{keyword}」...")
        
        try:
            if search_type in ["用户", "user"]:
                results = await self.bilibili_svc.search_service.search_user(keyword, limit=5)
                reply = self.bilibili_svc.search_service.format_user_results(results)
            elif search_type in ["番剧", "bangumi", "bgm"]:
                results = await self.bilibili_svc.search_service.search_bangumi(keyword, limit=5)
                reply = self.bilibili_svc.search_service.format_bangumi_results(results)
            elif search_type in ["视频", "video"]:
                results = await self.bilibili_svc.search_service.search_video(keyword, limit=5)
                reply = self.bilibili_svc.search_service.format_video_results(results)
            else:
                await self.client.send_group_msg(group_id, "❌ 不支持的搜索类型\n支持的类型：用户、番剧、视频")
                return
            
            await self.client.send_group_msg(group_id, reply)
        except Exception as e:
            logger.warn("Handler", f"搜索失败: {e}")
            await self.client.send_group_msg(group_id, "❌ 搜索时出现错误")
    
    async def _handle_bilibili_info(self, group_id, args: str):
        """处理B站信息查询"""
        parts = args.split(maxsplit=1)
        if len(parts) < 2:
            await self.client.send_group_msg(group_id, "❌ 请指定信息类型和ID\n例如：/b站 信息 视频 BV1234567890")
            return
        
        info_type = parts[0].lower()
        info_id = parts[1].strip()
        
        await self.client.send_group_msg(group_id, f"🔍 正在查询信息...")
        
        try:
            if info_type in ["视频", "video"]:
                # 判断是aid还是bvid
                if info_id.startswith("BV"):
                    message = await self.bilibili_svc.parser.parse_video(bvid=info_id)
                elif info_id.startswith("av") or info_id.isdigit():
                    aid = int(info_id.replace("av", ""))
                    message = await self.bilibili_svc.parser.parse_video(aid=aid)
                else:
                    await self.client.send_group_msg(group_id, "❌ 无效的视频ID")
                    return
            elif info_type in ["动态", "dynamic"]:
                message = await self.bilibili_svc.parser.parse_dynamic(info_id)
            elif info_type in ["直播", "live", "room"]:
                room_id = int(info_id)
                message = await self.bilibili_svc.parser.parse_live(room_id)
            elif info_type in ["用户", "user"]:
                uid = int(info_id)
                message = await self.bilibili_svc.parser.parse_user(uid)
            elif info_type in ["剧集", "season"]:
                season_id = int(info_id)
                message = await self.bilibili_svc.parser.parse_season(season_id)
            else:
                await self.client.send_group_msg(group_id, "❌ 不支持的信息类型\n支持的类型：视频、动态、直播、用户、剧集")
                return
            
            if message:
                await self.client.send_group_msg(group_id, message)
            else:
                await self.client.send_group_msg(group_id, "❌ 未找到相关信息")
        except Exception as e:
            logger.warn("Handler", f"查询信息失败: {e}")
            await self.client.send_group_msg(group_id, "❌ 查询信息时出现错误")
    
    async def parse_bilibili_links(self, group_id, text: str):
        """自动解析消息中的B站链接"""
        try:
            links = self.bilibili_svc.parser.find_links(text)
            if not links:
                return
            
            # 去重（避免重复解析）
            seen = set()
            for link_type, link_id, matched_text in links:
                key = (link_type, link_id)
                if key in seen:
                    continue
                seen.add(key)
                
                # 解析链接
                message = await self.bilibili_svc.parser.parse(link_type, link_id)
                if message:
                    await self.client.send_group_msg(group_id, message)
        except Exception as e:
            logger.warn("Handler", f"解析B站链接失败: {e}")

    async def help_handler(self, group_id, help_cmd: str):
        """处理帮助请求，根据指定的模块返回详细帮助信息"""
        greet_msg = (
            "你好呀！😉👋我是你的好伙伴希酱\n"
            "不知道希酱能为你做什么？请看……\n"
        )
        # 基础帮助信息
        base_help = (
            "📝 KiBot 帮助中心\n"
            "使用格式：@我 + /命令 [参数]\n"
            "可用功能：天气、番剧、B站、帮助\n"
            "示例：@我 /天气 北京  或  @我 /帮助 天气\n\n"
        )

        # 天气模块帮助
        weather_help = (
            "🌤️ 天气命令\n"
            "/天气 [城市]         → 查询指定城市实时天气\n"
            "/天气 预警 [城市]     → 查询指定城市气象预警\n"
            "/天气 台风           → 查询西北太平洋活跃台风\n"
            "/天气 订阅 [城市]     → 订阅指定城市天气推送（每日7:30）\n"
            "/天气 取消订阅 [城市]  → 取消指定城市天气订阅\n"
            "示例：\n"
            "  /天气 上海\n"
            "  /天气 预警 上海\n"
            "  /天气 订阅 上海 北京\n"
        )

        # 番剧模块帮助
        bangumi_help = (
            "📺 番剧命令\n"
            "/番剧 今日放送       → 查询今日动画放送信息\n"
            "/番剧 订阅           → 订阅每日番剧推送（每天8:00）\n"
            "/番剧 取消订阅       → 取消每日番剧推送\n"
        )

        # B站模块帮助
        bilibili_help = (
            "📺 B站命令\n"
            "/b站 订阅 [UP主UID]      → 订阅指定UP主动态推送（每5分钟检查）\n"
            "/b站 取消订阅 [UP主UID]  → 取消指定UP主动态订阅\n"
            "/b站 查看订阅            → 查看本群订阅的所有UP主\n"
            "/b站 检查 [UP主UID]      → 手动检查指定UP主最新动态\n"
            "/b站 搜索 [类型] [关键词] → 搜索用户/番剧/视频\n"
            "   类型：用户、番剧、视频\n"
            "/b站 信息 [类型] [ID]    → 查询视频/动态/直播/用户/剧集信息\n"
            "   类型：视频、动态、直播、用户、剧集\n"
            "\n"
            "💡 自动解析：消息中包含B站链接时会自动解析并发送信息\n"
            "   支持：BV号、AV号、动态链接、直播间链接、用户空间链接等\n"
        )

        if not help_cmd:
            # 无指定模块，返回基础帮助+模块列表
            full_help = greet_msg + base_help + (
                "🔍 查看模块详情：\n"
                "  /帮助 天气   → 查看天气功能详细说明\n"
                "  /帮助 番剧   → 查看番剧功能详细说明\n"
                "  /帮助 B站    → 查看B站功能详细说明\n"
                "\n"
                "如果想要和我聊天的话，直接@我就可以啦！\n"
                "大家和我说的每一句话，我都会努力记住的！😊"
            )
        elif help_cmd == "天气":
            full_help = base_help + weather_help
        elif help_cmd in ["番剧", "动画"]:
            full_help = base_help + bangumi_help
        elif help_cmd in ["B站", "b站", "哔哩哔哩"]:
            full_help = base_help + bilibili_help
        else:
            full_help = base_help + f"❓ 未找到「{help_cmd}」模块的帮助信息\n请输入正确的模块名称"

        await self.client.send_group_msg(group_id, full_help)
