import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("FLAG_DATABASE_URL", "postgresql://user:pass@localhost/testdb")
    monkeypatch.setenv("AUTH_SERVICE_URL", "http://auth:8001")


@pytest.fixture()
def app_module():
    mock_pool = MagicMock()
    with patch("psycopg2.pool.SimpleConnectionPool", return_value=mock_pool):
        if "app" in sys.modules:
            del sys.modules["app"]
        import app as flag_app

        yield flag_app


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


class TestHealthEndpoints:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}

    def test_flags_health(self, client):
        resp = client.get("/flags/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestAuthMiddleware:
    def test_missing_auth_header_returns_401(self, client):
        resp = client.post("/flags", json={"name": "test"})
        assert resp.status_code == 401
        assert "Authorization" in resp.get_json()["error"]

    def test_invalid_key_returns_401(self, client, monkeypatch):
        mock_resp = MagicMock()
        mock_resp.status_code = 403
        monkeypatch.setattr("requests.get", MagicMock(return_value=mock_resp))
        resp = client.post(
            "/flags",
            json={"name": "test"},
            headers={"Authorization": "Bearer bad-key"},
        )
        assert resp.status_code == 401

    def test_auth_timeout_returns_504(self, client, monkeypatch):
        import requests as req_lib

        monkeypatch.setattr(
            "requests.get", MagicMock(side_effect=req_lib.exceptions.Timeout())
        )
        resp = client.post(
            "/flags",
            json={"name": "test"},
            headers={"Authorization": "Bearer key"},
        )
        assert resp.status_code == 504

    def test_auth_connection_error_returns_503(self, client, monkeypatch):
        import requests as req_lib

        monkeypatch.setattr(
            "requests.get",
            MagicMock(side_effect=req_lib.exceptions.ConnectionError()),
        )
        resp = client.post(
            "/flags",
            json={"name": "test"},
            headers={"Authorization": "Bearer key"},
        )
        assert resp.status_code == 503


class TestCreateFlag:
    def test_missing_name_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.post(
            "/flags",
            json={"description": "no name"},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400

    def test_create_success(self, client, monkeypatch, mock_pool):
        _mock_auth_success(monkeypatch)
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = {
            "name": "dark_mode",
            "description": "",
            "is_enabled": False,
        }
        mock_conn.cursor.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn

        resp = client.post(
            "/flags",
            json={"name": "dark_mode"},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["name"] == "dark_mode"


class TestUpdateFlag:
    def test_empty_body_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.put(
            "/flags/test",
            data="",
            content_type="application/json",
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400

    def test_no_valid_fields_returns_400(self, client, monkeypatch):
        _mock_auth_success(monkeypatch)
        resp = client.put(
            "/flags/test",
            json={"unknown_field": "value"},
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 400


class TestDeleteFlag:
    def test_not_found_returns_404(self, client, monkeypatch, mock_pool):
        _mock_auth_success(monkeypatch)
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_cur.rowcount = 0
        mock_conn.cursor.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn

        resp = client.delete(
            "/flags/nonexistent",
            headers={"Authorization": "Bearer valid"},
        )
        assert resp.status_code == 404
