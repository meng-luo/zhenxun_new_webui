"""管理服务"""
import nonebot
from datetime import datetime, timedelta
from tortoise.expressions import Q

from zhenxun.models.bag_user import BagUser
from zhenxun.models.chat_history import ChatHistory
from zhenxun.models.fg_request import FgRequest
from zhenxun.models.friend_user import FriendUser
from zhenxun.models.group_console import GroupConsole
from zhenxun.models.group_member_info import GroupInfoUser
from zhenxun.models.level_user import LevelUser
from zhenxun.models.sign_user import SignUser
from zhenxun.models.statistics import Statistics
from zhenxun.models.user_console import UserConsole
from zhenxun.services.log import logger
from zhenxun.utils.enum import RequestHandleType, RequestType
from zhenxun.utils.message import MessageUtils
from zhenxun.utils.platform import PlatformUtils

from ..models.manage import (
    FriendRequestResult,
    GroupDetail,
    GroupMember,
    GroupRequestResult,
    GroupStatistics,
    MemberDetail,
    FriendDetail,
    FriendTrend,
    FriendTrendPoint,
)
from ..models.system import Friend, Group


def convert_module_format(data: str | list[str]) -> str | list[str]:
    """在 `<aaa,<bbb,<ccc,` 和 `["aaa", "bbb", "ccc"]` 之间转换

    参数:
        data: 要转换的数据

    返回:
        str | list[str]: 根据输入类型返回转换后的数据
    """
    if isinstance(data, str):
        return [item.strip(",").strip("<") for item in data.split("<") if item.strip()]
    else:
        return "".join(f"<{item}," for item in data)


class ManageService:
    """管理服务"""

    @staticmethod
    async def send_message(
        bot_id: str | None = None,
        user_id: str | None = None,
        group_id: str | None = None,
        message: str = "",
    ) -> bool:
        """发送消息

        参数:
            bot_id: Bot ID
            user_id: 用户 ID
            group_id: 群组 ID
            message: 消息内容

        返回:
            bool: 是否发送成功
        """
        try:
            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if not bots:
                    return False
                bot = list(bots.values())[0]

            # 构建消息
            message_obj = MessageUtils.build_message(message)

            # 获取目标
            target = PlatformUtils.get_target(
                user_id=user_id, group_id=group_id
            )

            if not target:
                return False

            # 发送消息
            await message_obj.send(target=target, bot=bot)
            return True
        except Exception as e:
            logger.error(f"发送消息失败：{e}", "ManageService:send_message")
            return False

    @staticmethod
    async def get_friend_list(bot_id: str | None = None) -> list[Friend]:
        """获取好友列表

        参数:
            bot_id: Bot ID

        返回:
            list[Friend]: 好友列表
        """
        if bot_id:
            bot = nonebot.get_bot(bot_id)
        else:
            bots = nonebot.get_bots()
            if not bots:
                return []
            bot = list(bots.values())[0]

        friend_list, _ = await PlatformUtils.get_friend_list(bot)
        result = []
        for f in friend_list:
            # QQ 头像 URL，使用 referrerpolicy="no-referrer" 防止防盗链
            ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={f.user_id}&s=640"
            result.append(
                Friend(
                    user_id=str(f.user_id),
                    nickname=f.user_name or "",
                    ava_url=ava_url,
                )
            )
        return result

    @staticmethod
    async def get_group_list(bot_id: str | None = None) -> list[Group]:
        """获取群组列表

        参数:
            bot_id: Bot ID

        返回:
            list[Group]: 群组列表
        """
        if bot_id:
            bot = nonebot.get_bot(bot_id)
        else:
            bots = nonebot.get_bots()
            if not bots:
                return []
            bot = list(bots.values())[0]

        group_list, _ = await PlatformUtils.get_group_list(bot)
        result = []
        for g in group_list:
            # 使用 https://p.qlogo.cn 支持 no-referer 防盗链
            ava_url = f"http://p.qlogo.cn/gh/{g.group_id}/{g.group_id}/640/"
            result.append(
                Group(
                    group_id=str(g.group_id),
                    group_name=g.group_name or "",
                    ava_url=ava_url,
                )
            )
        return result

    @staticmethod
    async def leave_group(bot_id: str | None = None, group_id: str | None = None) -> bool:
        """退群

        参数:
            bot_id: Bot ID
            group_id: 群组 ID

        返回:
            bool: 是否成功
        """
        try:
            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if not bots:
                    return False
                bot = list(bots.values())[0]

            if not group_id:
                return False

            await bot.set_group_leave(group_id=int(group_id))
            # 删除群组数据
            await GroupConsole.filter(group_id=group_id).delete()
            return True
        except Exception as e:
            logger.error(f"退群失败：{e}", "ManageService:leave_group")
            return False

    @staticmethod
    async def delete_friend(bot_id: str | None = None, user_id: str | None = None) -> bool:
        """移除好友

        参数:
            bot_id: Bot ID
            user_id: 用户 ID

        返回:
            bool: 是否成功
        """
        try:
            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if not bots:
                    return False
                bot = list(bots.values())[0]

            if not user_id:
                return False

            await bot.delete_friend(user_id=int(user_id))
            return True
        except Exception as e:
            logger.error(f"移除好友失败：{e}", "ManageService:delete_friend")
            return False

    @staticmethod
    async def get_group_detail(
        bot_id: str | None = None, group_id: str | None = None
    ) -> GroupDetail | None:
        """获取群组详情

        参数:
            bot_id: Bot ID
            group_id: 群组 ID

        返回:
            GroupDetail | None: 群组详情
        """
        try:
            if not group_id:
                return None

            # 获取群组数据
            group = await GroupConsole.get_or_none(group_id=group_id)
            if not group:
                return None

            # 获取群成员数量
            member_count = 0
            max_member_count = 0
            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if bots:
                    bot = list(bots.values())[0]
                    group_list, _ = await PlatformUtils.get_group_list(bot)
                    for g in group_list:
                        if str(g.group_id) == group_id:
                            member_count = g.member_count or 0
                            max_member_count = g.max_member_count or 0
                            break

            # 使用 http://p.qlogo.cn 支持 no-referer 防盗链
            ava_url = f"http://p.qlogo.cn/gh/{group_id}/{group_id}/640/"

            return GroupDetail(
                group_id=group_id,
                group_name=group.group_name or "",
                ava_url=ava_url,
                member_count=member_count,
                max_member_count=max_member_count,
                level=group.level,
                status=group.status,
                is_super=group.is_super,
                block_task=bool(group.block_task),
                block_plugin=bool(group.block_plugin),
            )
        except Exception as e:
            logger.error(f"获取群组详情失败：{e}", "ManageService:get_group_detail")
            return None

    @staticmethod
    async def update_group(request) -> bool:
        """更新群组设置

        参数:
            request: UpdateGroupRequest

        返回:
            bool: 是否成功
        """
        try:
            group = await GroupConsole.get_or_none(group_id=request.group_id)
            if not group:
                return False

            update_fields = []
            if request.status is not None:
                group.status = request.status
                update_fields.append("status")
            if request.level is not None:
                group.level = request.level
                update_fields.append("level")
            if request.is_super is not None:
                group.is_super = request.is_super
                update_fields.append("is_super")
            if request.block_task is not None:
                # 获取所有任务模块
                task_modules = await GroupConsole._get_task_modules(default_status=False)
                if request.block_task:
                    # 禁用所有任务
                    group.block_task = convert_module_format(task_modules)
                else:
                    # 启用所有任务
                    group.block_task = ""
                update_fields.append("block_task")
            if request.block_plugin is not None:
                # 获取所有插件模块
                plugin_modules = await GroupConsole._get_plugin_modules(
                    default_status=False
                )
                if request.block_plugin:
                    # 禁用所有插件
                    group.block_plugin = convert_module_format(plugin_modules)
                else:
                    # 启用所有插件
                    group.block_plugin = ""
                update_fields.append("block_plugin")

            if update_fields:
                await group.save(update_fields=update_fields)
            return True
        except Exception as e:
            logger.error(f"更新群组设置失败：{e}", "ManageService:update_group")
            return False

    @staticmethod
    async def get_group_members(
        bot_id: str | None = None, group_id: str | None = None
    ) -> list[GroupMember]:
        """获取群成员列表

        参数:
            bot_id: Bot ID
            group_id: 群组 ID

        返回:
            list[GroupMember]: 群成员列表
        """
        try:
            if not group_id:
                return []

            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if not bots:
                    return []
                bot = list(bots.values())[0]

            # 获取群成员列表
            member_list = await bot.get_group_member_list(group_id=int(group_id))
            result = []
            for m in member_list:
                user_id = str(m.get("user_id", ""))
                result.append(
                    GroupMember(
                        user_id=user_id,
                        nickname=m.get("nickname", ""),
                        remark=m.get("card", "") or m.get("nickname", ""),
                        ava_url=f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640",
                        role=m.get("role", "member"),
                    )
                )
            return result
        except Exception as e:
            logger.error(f"获取群成员列表失败：{e}", "ManageService:get_group_members")
            return []

    @staticmethod
    async def get_member_detail(
        group_id: str | None = None, user_id: str | None = None
    ) -> MemberDetail | None:
        """获取成员详情

        参数:
            group_id: 群组 ID
            user_id: 用户 ID

        返回:
            MemberDetail | None: 成员详情
        """
        try:
            if not group_id or not user_id:
                return None

            # 获取用户信息（从群成员信息中获取昵称）
            user_info = await GroupInfoUser.get_or_none(user_id=user_id, group_id=group_id)
            nickname = user_info.user_name if user_info else ""
            ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

            # 获取金币
            gold = await BagUser.get_gold(user_id, group_id)

            # 获取好感度/权限等级
            favorability = await LevelUser.get_user_level(user_id, group_id)

            return MemberDetail(
                user_id=user_id,
                nickname=nickname,
                remark="",
                ava_url=ava_url,
                gold=gold,
                favorability=favorability,
                is_banned=False,
            )
        except Exception as e:
            logger.error(f"获取成员详情失败：{e}", "ManageService:get_member_detail")
            return None

    @staticmethod
    async def update_member(request) -> bool:
        """更新成员数据

        参数:
            request: UpdateMemberRequest

        返回:
            bool: 是否成功
        """
        try:
            if request.gold is not None:
                # 计算需要增加/减少的金币数
                current_gold = await BagUser.get_gold(request.user_id, request.group_id)
                diff = request.gold - current_gold
                if diff > 0:
                    await BagUser.add_gold(request.user_id, request.group_id, diff)
                elif diff < 0:
                    await BagUser.spend_gold(request.user_id, request.group_id, abs(diff))
            if request.favorability is not None:
                await LevelUser.set_level(
                    request.user_id, request.group_id, request.favorability
                )
            if request.is_banned is not None:
                # 处理禁用逻辑（如果有相关模型）
                pass
            return True
        except Exception as e:
            logger.error(f"更新成员数据失败：{e}", "ManageService:update_member")
            return False

    @staticmethod
    async def get_group_plugins(group_id: str | None = None) -> list[dict]:
        """获取群功能开关列表

        参数:
            group_id: 群组 ID

        返回:
            list[dict]: 插件列表
        """
        try:
            if not group_id:
                return []

            group = await GroupConsole.get_or_none(group_id=group_id)
            if not group:
                return []

            # 获取所有插件
            from zhenxun.models.plugin_info import PluginInfo
            from zhenxun.utils.enum import PluginType

            plugins = await PluginInfo.filter(
                plugin_type__in=[PluginType.NORMAL, PluginType.DEPENDANT]
            ).all()

            # 解析禁用的插件和任务模块
            block_plugin_set = set(convert_module_format(group.block_plugin or ""))
            block_task_set = set(convert_module_format(group.block_task or ""))

            result = []
            for p in plugins:
                module = p.module
                is_blocked = module in block_plugin_set
                result.append(
                    {
                        "module": module,
                        "plugin_name": p.name,
                        "is_blocked": is_blocked,
                        "is_task": False,
                    }
                )

            # 获取所有任务
            from zhenxun.models.task_info import TaskInfo

            tasks = await TaskInfo.all()
            for t in tasks:
                module = t.module
                is_blocked = module in block_task_set
                result.append(
                    {
                        "module": module,
                        "plugin_name": t.name,
                        "is_blocked": is_blocked,
                        "is_task": True,
                    }
                )

            return result
        except Exception as e:
            logger.error(f"获取群功能开关列表失败：{e}", "ManageService:get_group_plugins")
            return []

    @staticmethod
    async def toggle_group_plugin(request) -> bool:
        """切换群功能开关

        参数:
            request: TogglePluginRequest

        返回:
            bool: 是否成功
        """
        try:
            if request.is_task:
                if request.action == "block":
                    await GroupConsole.set_block_task(request.group_id, request.module)
                else:
                    await GroupConsole.set_unblock_task(request.group_id, request.module)
            else:
                if request.action == "block":
                    await GroupConsole.set_block_plugin(
                        request.group_id, request.module
                    )
                else:
                    await GroupConsole.set_unblock_plugin(
                        request.group_id, request.module
                    )
            return True
        except Exception as e:
            logger.error(f"切换群功能开关失败：{e}", "ManageService:toggle_group_plugin")
            return False

    @staticmethod
    async def get_group_statistics(
        bot_id: str | None = None, group_id: str | None = None
    ) -> GroupStatistics | None:
        """获取群数据统计

        参数:
            bot_id: Bot ID
            group_id: 群组 ID

        返回:
            GroupStatistics | None: 统计数据
        """
        try:
            if not group_id:
                return None

            group = await GroupConsole.get_or_none(group_id=group_id)
            if not group:
                return None

            # 这里需要从数据库获取发言统计和插件调用统计
            # 简化实现，返回默认值
            return GroupStatistics(
                group_id=group_id,
                group_name=group.group_name or "",
                chat_count=0,
                call_count=0,
                member_count=0,
                active_members=0,
            )
        except Exception as e:
            logger.error(f"获取群数据统计失败：{e}", "ManageService:get_group_statistics")
            return None

    @staticmethod
    async def get_request_list(bot_id: str | None = None) -> dict:
        """获取请求列表

        参数:
            bot_id: Bot ID

        返回:
            dict: 包含 friend 和 group 请求列表的字典
        """
        try:
            # 获取未处理的好友请求
            friend_requests = await FgRequest.filter(
                request_type=RequestType.FRIEND,
                handle_type__isnull=True
            ).order_by("-id")

            # 获取未处理的群请求
            group_requests = await FgRequest.filter(
                request_type=RequestType.GROUP,
                handle_type__isnull=True
            ).order_by("-id")

            friend_result = []
            for req in friend_requests:
                if bot_id and req.bot_id != bot_id:
                    continue
                ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={req.user_id}&s=640"
                friend_result.append(
                    FriendRequestResult(
                        bot_id=req.bot_id,
                        oid=req.id,
                        id=str(req.user_id),
                        flag=req.flag,
                        nickname=req.nickname,
                        comment=req.comment,
                        ava_url=ava_url,
                        type="friend",
                    )
                )

            group_result = []
            for req in group_requests:
                if bot_id and req.bot_id != bot_id:
                    continue
                ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={req.user_id}&s=640"
                group_result.append(
                    GroupRequestResult(
                        bot_id=req.bot_id,
                        oid=req.id,
                        id=str(req.user_id),
                        flag=req.flag,
                        nickname=req.nickname,
                        comment=req.comment,
                        ava_url=ava_url,
                        type="group",
                        invite_group=req.group_id or "",
                        group_name=None,
                    )
                )

            return {"friend": friend_result, "group": group_result}
        except Exception as e:
            logger.error(f"获取请求列表失败：{e}", "ManageService:get_request_list")
            return {"friend": [], "group": []}

    @staticmethod
    async def handle_request(
        bot_id: str | None = None,
        request_id: int | None = None,
        action: str = "approve"
    ) -> bool:
        """处理请求

        参数:
            bot_id: Bot ID
            request_id: 请求 ID
            action: 操作类型 (approve/refused/ignore)

        返回:
            bool: 是否成功
        """
        try:
            if not request_id:
                return False

            req = await FgRequest.get_or_none(id=request_id)
            if not req:
                return False

            if bot_id and req.bot_id != bot_id:
                return False

            # 获取 bot
            if bot_id:
                bot = nonebot.get_bot(bot_id)
            else:
                bots = nonebot.get_bots()
                if not bots:
                    return False
                bot = list(bots.values())[0]

            # 根据操作类型处理
            if action == "approve":
                await FgRequest.approve(bot, request_id)
            elif action == "refused":
                await FgRequest.refused(bot, request_id)
            elif action == "ignore":
                await FgRequest.ignore(request_id)
            else:
                return False

            return True
        except Exception as e:
            logger.error(f"处理请求失败：{e}", "ManageService:handle_request")
            return False

    @staticmethod
    async def clear_request(request_type: str) -> bool:
        """清空请求

        参数:
            request_type: 请求类型 (friend/group)

        返回:
            bool: 是否成功
        """
        try:
            if request_type == "friend":
                await FgRequest.filter(
                    request_type=RequestType.FRIEND,
                    handle_type__isnull=True
                ).update(handle_type=RequestHandleType.EXPIRE)
            elif request_type == "group":
                await FgRequest.filter(
                    request_type=RequestType.GROUP,
                    handle_type__isnull=True
                ).update(handle_type=RequestHandleType.EXPIRE)
            else:
                return False
            return True
        except Exception as e:
            logger.error(f"清空请求失败：{e}", "ManageService:clear_request")
            return False

    @staticmethod
    async def get_friend_detail(user_id: str | None = None) -> FriendDetail | None:
        """获取好友详情

        参数:
            user_id: 用户 ID

        返回:
            FriendDetail | None: 好友详情
        """
        try:
            if not user_id:
                return None

            # 获取用户信息
            user_console = await UserConsole.get_or_none(user_id=user_id)

            # 获取签到数据（好感度）
            sign_user = await SignUser.get_or_none(user_id=user_id)

            # 构建头像 URL
            ava_url = f"http://q1.qlogo.cn/g?b=qq&nk={user_id}&s=640"

            return FriendDetail(
                user_id=user_id,
                nickname=user_console.user_id if user_console else user_id,
                ava_url=ava_url,
                gold=user_console.gold if user_console else 0,
                favorability=float(sign_user.impression) if sign_user else 0.0,
            )
        except Exception as e:
            logger.error(f"获取好友详情失败：{e}", "ManageService:get_friend_detail")
            return None

    @staticmethod
    async def update_friend(request) -> bool:
        """更新好友数据

        参数:
            request: UpdateFriendRequest

        返回:
            bool: 是否成功
        """
        try:
            user_id = request.user_id

            # 更新金币
            if request.gold is not None:
                user_console = await UserConsole.get_user(user_id)
                current_gold = user_console.gold
                diff = request.gold - current_gold
                if diff > 0:
                    await UserConsole.add_gold(user_id, diff, "web_ui_edit")
                elif diff < 0:
                    from zhenxun.utils.enum import GoldHandle
                    await UserConsole.reduce_gold(
                        user_id, abs(diff), GoldHandle.PLUGIN, "web_ui_edit"
                    )

            # 更新好感度
            if request.favorability is not None:
                sign_user = await SignUser.get_user(user_id)
                sign_user.impression = request.favorability
                await sign_user.save(update_fields=["impression"])

            return True
        except Exception as e:
            logger.error(f"更新好友数据失败：{e}", "ManageService:update_friend")
            return False

    @staticmethod
    async def get_friend_trend(
        user_id: str | None = None, days: int = 7
    ) -> FriendTrend:
        """获取好友趋势数据

        参数:
            user_id: 用户 ID
            days: 天数

        返回:
            FriendTrend: 趋势数据
        """
        try:
            if not user_id:
                return FriendTrend()

            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)

            data_points = []
            total_chat = 0
            total_call = 0

            for i in range(days):
                day_start = start_time + timedelta(days=i)
                day_end = day_start + timedelta(days=1)

                # 查询私聊消息数（group_id 为空）
                chat_count = await ChatHistory.filter(
                    user_id=user_id,
                    group_id__isnull=True,
                    create_time__gte=day_start,
                    create_time__lt=day_end,
                ).count()

                # 查询私聊插件调用数
                call_count = await Statistics.filter(
                    user_id=user_id,
                    group_id__isnull=True,
                    create_time__gte=day_start,
                    create_time__lt=day_end,
                ).count()

                data_points.append(
                    FriendTrendPoint(
                        date=day_start.strftime("%m-%d"),
                        chat_count=chat_count,
                        call_count=call_count,
                    )
                )

                total_chat += chat_count
                total_call += call_count

            return FriendTrend(
                data=data_points,
                total_chat=total_chat,
                total_call=total_call,
            )
        except Exception as e:
            logger.error(f"获取好友趋势失败：{e}", "ManageService:get_friend_trend")
            return FriendTrend()
