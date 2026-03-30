"""主页服务"""
from datetime import datetime, timedelta

from zhenxun.models.chat_history import ChatHistory
from zhenxun.models.group_console import GroupConsole
from zhenxun.models.statistics import Statistics

from ..models.system import BotStatus
from ..utils.formatters import format_uptime


class MainService:
    """主页服务"""

    @staticmethod
    async def get_bot_status() -> BotStatus:
        """获取 Bot 状态"""
        import nonebot

        bots = nonebot.get_bots()
        is_running = len(bots) > 0

        # 获取 Bot 信息
        self_id: str | None = None
        nickname: str | None = None
        ava_url: str | None = None

        if bots:
            bot = list(bots.values())[0]
            self_id = getattr(bot, "self_id", None)
            try:
                bot_info = await bot.get_login_info()
                nickname = bot_info.get("nickname")
                ava_url = bot_info.get("face_url")
            except Exception:
                pass

            # 如果没有头像 URL，使用 QQ 头像默认地址
            if not ava_url and self_id:
                ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={self_id}&s=640"

        # 获取运行时长
        uptime = 0
        start_time = datetime.now()
        try:
            from zhenxun.models.bot_connect_log import BotConnectLog

            latest_connect = await BotConnectLog.filter(type=1).order_by("-connect_time").first()
            if latest_connect and latest_connect.connect_time:
                start_time = latest_connect.connect_time
                uptime = int((datetime.now() - start_time).total_seconds())
        except Exception:
            pass

        # 获取群组和好友数量
        group_count = 0
        try:
            group_count = await GroupConsole.all().count()
        except Exception:
            pass

        return BotStatus(
            self_id=self_id,
            nickname=nickname,
            ava_url=ava_url,
            is_running=is_running,
            uptime=uptime,
            uptime_formatted=format_uptime(uptime),
            group_count=group_count,
            friend_count=0,
            message_count=0,
            start_time=start_time,
        )

    @staticmethod
    async def get_chat_statistics(bot_id: str | None = None) -> dict:
        """获取聊天统计"""
        now = datetime.now()
        query = ChatHistory.all()
        if bot_id:
            query = query.filter(bot_id=bot_id)

        return {
            "all": await query.count(),
            "day": await query.filter(create_time__gte=now.replace(hour=0, minute=0, second=0)).count(),
            "week": await query.filter(create_time__gte=now - timedelta(days=7)).count(),
            "month": await query.filter(create_time__gte=now - timedelta(days=30)).count(),
            "year": await query.filter(create_time__gte=now - timedelta(days=365)).count(),
        }

    @staticmethod
    async def get_plugin_statistics(bot_id: str | None = None) -> dict:
        """获取插件调用统计"""
        now = datetime.now()
        query = Statistics.all()
        if bot_id:
            query = query.filter(bot_id=bot_id)

        return {
            "all": await query.count(),
            "day": await query.filter(create_time__gte=now.replace(hour=0, minute=0, second=0)).count(),
            "week": await query.filter(create_time__gte=now - timedelta(days=7)).count(),
            "month": await query.filter(create_time__gte=now - timedelta(days=30)).count(),
            "year": await query.filter(create_time__gte=now - timedelta(days=365)).count(),
        }

    @staticmethod
    async def get_active_groups(
        start_time: str | None = None,
        end_time: str | None = None,
        date_type: str = "week",
        bot_id: str | None = None,
    ) -> list[dict]:
        """获取活跃群组

        参数:
            start_time: 起始时间 (ISO 8601 格式)，可选
            end_time: 结束时间 (ISO 8601 格式)，可选
            date_type: 日期类型 (day/week/month/year)，当未提供 start_time/end_time 时使用
            bot_id: Bot ID

        返回:
            list[dict]: 活跃群组列表
        """
        query = ChatHistory.all()
        if bot_id:
            query = query.filter(bot_id=bot_id)

        # 如果提供了 start_time 和 end_time，使用自定义时间范围
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
                query = query.filter(create_time__gte=start_dt, create_time__lte=end_dt)
            except ValueError:
                # 如果解析失败，回退到 date_type
                pass
        else:
            # 使用 date_type
            now = datetime.now()
            if date_type == "day":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
                )
            elif date_type == "week":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=7, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )
            elif date_type == "month":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=30, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )
            elif date_type == "year":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=365, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )

        # 按群组分组统计
        from tortoise.functions import Count

        data_list = (
            await query.annotate(count=Count("id"))
            .filter(group_id__not_isnull=True)
            .group_by("group_id")
            .order_by("-count")
            .limit(10)
            .values_list("group_id", "count")
        )

        # 获取群组名称
        id2name = {}
        if data_list:
            group_ids = [x[0] for x in data_list]
            groups = await GroupConsole.filter(group_id__in=group_ids).all()
            for group in groups:
                id2name[group.group_id] = group.group_name

        result = []
        for group_id, count in data_list:
            result.append(
                {
                    "group_id": group_id,
                    "name": id2name.get(group_id) or str(group_id),
                    "chat_num": count,
                    "ava_img": f"http://p.qlogo.cn/gh/{group_id}/{group_id}/640/",
                }
            )

        return result

    @staticmethod
    async def get_hot_plugins(
        start_time: str | None = None,
        end_time: str | None = None,
        date_type: str = "week",
        bot_id: str | None = None,
    ) -> list[dict]:
        """获取热门插件

        参数:
            start_time: 起始时间 (ISO 8601 格式)，可选
            end_time: 结束时间 (ISO 8601 格式)，可选
            date_type: 日期类型 (day/week/month/year)，当未提供 start_time/end_time 时使用
            bot_id: Bot ID

        返回:
            list[dict]: 热门插件列表
        """
        from tortoise.functions import Count

        from zhenxun.models.plugin_info import PluginInfo

        query = Statistics.all()
        if bot_id:
            query = query.filter(bot_id=bot_id)

        # 如果提供了 start_time 和 end_time，使用自定义时间范围
        if start_time and end_time:
            try:
                start_dt = datetime.fromisoformat(start_time)
                end_dt = datetime.fromisoformat(end_time)
                query = query.filter(create_time__gte=start_dt, create_time__lte=end_dt)
            except ValueError:
                # 如果解析失败，回退到 date_type
                pass
        else:
            # 使用 date_type
            now = datetime.now()
            if date_type == "day":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second)
                )
            elif date_type == "week":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=7, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )
            elif date_type == "month":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=30, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )
            elif date_type == "year":
                query = query.filter(
                    create_time__gte=now
                    - timedelta(
                        days=365, hours=now.hour, minutes=now.minute, seconds=now.second
                    )
                )

        # 按插件名分组统计
        data_list = (
            await query.annotate(count=Count("id"))
            .filter(plugin_name__not_isnull=True)
            .group_by("plugin_name")
            .order_by("-count")
            .limit(10)
            .values_list("plugin_name", "count")
        )

        # 获取插件名称
        module2name = {}
        if data_list:
            modules = [x[0] for x in data_list]
            plugins = await PluginInfo.filter(module__in=modules).all()
            module2name = {p.module: p.name for p in plugins}

        result = []
        for plugin_name, count in data_list:
            result.append(
                {
                    "plugin_name": module2name.get(plugin_name) or plugin_name,
                    "call_count": count,
                }
            )

        return result
