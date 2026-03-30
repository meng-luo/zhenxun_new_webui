"""WebUI Next - 重构后的 WebUI 后端"""
import secrets

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse
import nonebot
from nonebot.log import default_filter, default_format
from nonebot.plugin import PluginMetadata

from zhenxun.configs.config import Config as gConfig
from zhenxun.configs.utils import PluginExtraData, RegisterConfig
from zhenxun.services.log import logger, logger_
from zhenxun.utils.enum import PluginType
from zhenxun.utils.manager.priority_manager import PriorityLifecycle

# 导入配置以注册 CORS 中间件
from . import config as _config  # noqa: F401
from .exceptions import APIException
from .responses import error_response
from .routers import (
    analytics_router,
    auth_router,
    config_router,
    dashboard_router,
    database_router,
    file_router,
    main_router,
    manage_router,
    plugin_router,
    store_router,
    system_router,
)
from .routers.websocket import ws_chat_router, ws_log_router, ws_status_router
from .services.log_service import LOG_STORAGE

__plugin_meta__ = PluginMetadata(
    name="WebUi Next",
    description="重构后的 WebUI API",
    usage='"""\n    """.strip(),',
    extra=PluginExtraData(
        author="HibiKier",
        version="0.2",
        plugin_type=PluginType.HIDDEN,
        configs=[
            RegisterConfig(
                module="web-ui",
                key="username",
                value="admin",
                help="前端管理用户名",
                type=str,
                default_value="admin",
            ),
            RegisterConfig(
                module="web-ui",
                key="password",
                value=None,
                help="前端管理密码",
                type=str,
                default_value=None,
            ),
            RegisterConfig(
                module="web-ui",
                key="secret",
                value=secrets.token_urlsafe(32),
                help="JWT 密钥",
                type=str,
                default_value=None,
            ),
        ],
    ).to_dict(),
)

driver = nonebot.get_driver()

gConfig.set_name("web-ui", "web-ui")

# HTTP API 路由 - 统一使用 /zhenxun/api/v1 前缀
BaseApiRouter = APIRouter(prefix="/zhenxun/api/v1")

BaseApiRouter.include_router(auth_router)
BaseApiRouter.include_router(analytics_router)
BaseApiRouter.include_router(dashboard_router)
BaseApiRouter.include_router(main_router)
BaseApiRouter.include_router(plugin_router)
BaseApiRouter.include_router(system_router)
BaseApiRouter.include_router(file_router)
BaseApiRouter.include_router(config_router)
BaseApiRouter.include_router(database_router)
BaseApiRouter.include_router(store_router)
BaseApiRouter.include_router(manage_router)

# WebSocket API 路由 - 统一使用 /zhenxun/ws/v1 前缀
WsApiRouter = APIRouter(prefix="/zhenxun/ws/v1")

WsApiRouter.include_router(ws_log_router)
WsApiRouter.include_router(ws_status_router)
WsApiRouter.include_router(ws_chat_router)


@PriorityLifecycle.on_startup(priority=0)
async def _():
    import asyncio
    import re

    try:
        # 存储任务引用的列表，防止任务被垃圾回收
        _tasks = []

        # ANSI 转义码正则表达式
        ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*m")

        async def log_sink(message: str):
            loop = None
            if not loop:
                try:
                    loop = asyncio.get_running_loop()
                except Exception as e:
                    logger.warning("Web Ui Next log_sink", e=e)
            if not loop:
                loop = asyncio.new_event_loop()
            # 去除 ANSI 转义码后存储
            clean_message = ANSI_ESCAPE_PATTERN.sub("", message.rstrip("\n"))
            # 存储任务引用到外部列表中
            _tasks.append(loop.create_task(LOG_STORAGE.add(clean_message)))

        logger_.add(
            log_sink, colorize=True, filter=default_filter, format=default_format
        )

        app: FastAPI = nonebot.get_app()

        # 注册全局异常处理器
        @app.exception_handler(APIException)
        async def api_exception_handler(request, exc: APIException):
            """处理 APIException 及其子类"""
            return JSONResponse(
                status_code=exc.code,
                content=error_response(
                    message=exc.message, code=exc.code, data=exc.data
                ).model_dump(),
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request, exc: Exception):
            """处理未预期的异常"""
            logger.error(f"Unexpected error: {exc!s}", "WebUiNext")
            return JSONResponse(
                status_code=500,
                content=error_response(
                    message=f"服务器内部错误：{exc!s}", code=500
                ).model_dump(),
            )

        app.include_router(BaseApiRouter)
        app.include_router(WsApiRouter)
        logger.info("<g>WebUI Next API 启动成功</g>", "WebUiNext")
    except Exception as e:
        logger.error("<g>WebUI Next API 启动失败</g>", "WebUiNext", e=e)
