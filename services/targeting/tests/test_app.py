import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("TARGETING_DATABASE_URL", "postgresql://user:pass@localhost/testdb")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth:8001")


@pytest.fixture()
def app_module():
    mock_pool = MagicMock()
    with patch("psycopg2.pool.SimpleConnectionPool", return_value=mock_pool):
        if "app" in sys.modules:
            del sys.modules["app"]
        import app as targeting_app

        yield targeting_app


@pytest.fixture()
def client(app_module):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def mock_pool(app_module):
    return app_module.pool


def _mock_auth_success(monkeypatch):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    monkeypatch.setattr("requests.get", MagicMock(return_value=mock_resp))


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestAuthMiddleware:
    def test_missing_auth_header_returns_401(self, client):
        resp = client.post("/rules", json={"flag_name": "x", "rules": {}})
        assert resp.status_code == 401

    def test_invalid_key_returns_401(self, client, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        monkeypatch.setattr("requests.get", MagicMock(return_value=mock_resp))
        resp = client.post(
            "/rules",
            json={"flag_name": "x", "rules": {}},
            headers={"Authorization": "Bearer bad"},
        )
        assert resp.status_code == 401

    def test_auth_timeout_returns_504(self, client, monkeypatch):
        import requests as req_lib

        monkeypatch.setattr(
            "requests.get", MagicMock(side_effect=req_lib.exceptions.Timeout())
        )
        resp = client.post(
            "/rules",
            json={"flag_name": "x", "rules": {}},
            headers={"Authorization": "Bearer key"},
        )
        assert resp.status_code == 504


class TestCreateRule:
    def test_missing_fields_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.post(
            "/rules",
            json={"flag_name": "x"},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400

    def test_create_success(self, client, monkeypatch, mock_pool):
        _mock_auth_success(monkeypatch)
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            "flag_name": "dark_mode",
            "is_enabled": True,
            "rules": {"country": "BR"},
        }
        mock_conn.cursor.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn

        resp = client.post(
            "/rules",
            json={"flag_name": "dark_mode", "rules": {"country": "BR"}},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["flag_name"] == "dark_mode"


class TestUpdateRule:
    def test_empty_body_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.put(
            "/rules/test",
            data="",
            content_type="application/json",
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400

    def test_no_valid_fields_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.put(
            "/rules/test",
            json={"unknown_field": "value"},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400


class TestDeleteRule:
    def test_not_found_returns_404(self, client, monkeypatch, mock_pool):
        _mock_auth_success(monkeypatch)
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 0
        mock_conn.cursor.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn

        resp = client.delete(
            "/rules/nonexistent",
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 404


class TestGetRule:
    def test_not_found_returns_404(self, client, monkeypatch, mock_pool):
        _mock_auth_success(monkeypatch)
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = None
        mock_conn.cursor.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn

        resp = client.get(
            "/rules/nonexistent",
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 404
