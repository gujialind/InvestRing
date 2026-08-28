# ============================================================================
# 回归测试：全路由鉴权覆盖扫描（issue #256 配套防漏挂检查）
# ============================================================================
# market_data router 曾漏挂鉴权依赖（CWE-306）且无声通过所有门禁。
# 本测试遍历 app 全部路由：/api/* 端点必须（直接或间接）挂
# get_current_user / get_current_admin；确需公开的端点必须显式加入
# PUBLIC_API_PATHS 白名单，强制「公开即显式决策」。
# ============================================================================

from fastapi.routing import APIRoute

from app.main import app
from app.dependencies import get_current_user, get_current_admin

# 合法公开端点白名单：新增公开端点必须有意识地加入此列表
PUBLIC_API_PATHS = {
    "/api/auth/login",
}

AUTH_DEPS = {get_current_user, get_current_admin}


def _collect_dep_funcs(dependant) -> set:
    """递归收集 dependant 树上全部依赖函数（含子依赖）"""
    funcs = set()
    if dependant.call is not None:
        funcs.add(dependant.call)
    for sub in dependant.dependencies:
        funcs |= _collect_dep_funcs(sub)
    return funcs


class TestRouteAuthCoverage:
    """issue #256: 防止新 router 漏挂鉴权依赖"""

    def test_all_api_routes_require_auth(self):
        missing = []
        for route in app.routes:
            if not isinstance(route, APIRoute):
                continue
            if not route.path.startswith("/api/"):
                continue  # / 、/health、docs 等非业务路径不检查
            if route.path in PUBLIC_API_PATHS:
                continue
            if not (_collect_dep_funcs(route.dependant) & AUTH_DEPS):
                missing.append(f"{sorted(route.methods)} {route.path}")

        assert not missing, (
            "以下 /api 端点未挂鉴权依赖（get_current_user/get_current_admin）：\n  "
            + "\n  ".join(missing)
            + "\n确需公开的端点请显式加入 PUBLIC_API_PATHS 白名单"
        )

    def test_login_is_only_public_endpoint(self):
        """白名单自身体检：白名单内路径必须真实存在"""
        api_paths = {
            route.path for route in app.routes
            if isinstance(route, APIRoute) and route.path.startswith("/api/")
        }
        unknown = PUBLIC_API_PATHS - api_paths
        assert not unknown, f"白名单含不存在的端点：{unknown}"
