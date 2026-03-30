"""仪表盘路由"""
from fastapi import APIRouter

from ..dependencies import AuthenticatedUser
from ..models.dashboard import DashboardResult, DetailedStatistics
from ..responses import APIResponse, success_response
from ..services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["仪表盘"])


@router.get("", response_model=APIResponse[DashboardResult], summary="获取仪表盘数据")
async def get_dashboard(user: AuthenticatedUser) -> APIResponse[DashboardResult]:
    """获取仪表盘完整数据"""
    result = await DashboardService.get_dashboard()
    return success_response(data=result)


@router.get(
    "/statistics",
    response_model=APIResponse[DetailedStatistics],
    summary="获取详细统计数据",
)
async def get_detailed_statistics(
    user: AuthenticatedUser,
) -> APIResponse[DetailedStatistics]:
    """获取详细统计数据"""
    result = await DashboardService.get_detailed_statistics()
    return success_response(data=result)
