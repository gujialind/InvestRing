# ============================================================================
# 集成测试：平台管理 (test_platforms.py)
# ============================================================================

import pytest
from tests.factories import create_platform


class TestPlatformCRUD:
    """平台 CRUD API 测试"""

    def test_list_platforms(self, client, admin_headers):
        """获取平台列表"""
        resp = client.get("/api/platforms", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_create_platform(self, client, admin_headers):
        """创建平台"""
        resp = client.post(
            "/api/platforms",
            json={"code": "NEW_PLAT", "name": "新平台", "platform_type": "券商"},
            headers=admin_headers,
        )
        assert resp.status_code in (200, 201)
        assert resp.json()["code"] == "NEW_PLAT"

    def test_create_duplicate_platform_fails(self, client, admin_headers, test_db):
        """创建重复平台应失败"""
        create_platform(test_db, code="DUP_PLAT")
        resp = client.post(
            "/api/platforms",
            json={"code": "DUP_PLAT", "name": "重复"},
            headers=admin_headers,
        )
        assert resp.status_code in (400, 409)

    def test_get_platform_detail(self, client, admin_headers, test_db):
        """获取平台详情"""
        create_platform(test_db, code="DET_PLAT", name="详情平台")
        resp = client.get("/api/platforms/DET_PLAT", headers=admin_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] == "DET_PLAT"

    def test_viewer_cannot_create_platform(self, client, viewer_headers):
        """viewer 不能创建平台"""
        resp = client.post(
            "/api/platforms",
            json={"code": "V_PLAT", "name": "X"},
            headers=viewer_headers,
        )
        assert resp.status_code == 403
