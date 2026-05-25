import json
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _env_vars(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("AWS_SQS_URL", "")
    monkeypatch.setenv("DYNAMODB_ENDPOINT_URL", "http://localhost:8000")
    monkeypatch.setenv("DYNAMODB_CREATE_TABLE", "0")
    monkeypatch.setenv("DYNAMODB_USE_DUMMY_CREDS", "1")


@pytest.fixture()
def app_module():
    mock_session = MagicMock()
    mock_dynamo = MagicMock()
    mock_session.return_value.client.return_value = mock_dynamo

    with patch("boto3.Session", mock_session):
        if "app" in sys.modules:
            del sys.modules["app"]
        import app as analytics_app

        yield analytics_app


@pytest.fixture()
def client(app_module):
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.get_json() == {"status": "ok"}


class TestProcessMessage:
    def test_valid_message(self, app_module):
        body = {
            "user_id": "u1",
            "flag_name": "dark_mode",
            "result": True,
            "timestamp": "2026-01-01T00:00:00Z",
        }
        message = {
            "MessageId": "msg-1",
            "Body": json.dumps(body),
            "ReceiptHandle": "rh-1",
        }
        app_module.dynamodb_client.reset_mock()
        app_module.process_message(message)
        app_module.dynamodb_client.put_item.assert_called_once()
        call_kwargs = app_module.dynamodb_client.put_item.call_args
        item = call_kwargs.kwargs.get("Item") or call_kwargs[1].get("Item")
        assert item["user_id"] == {"S": "u1"}
        assert item["flag_name"] == {"S": "dark_mode"}
        assert item["result"] == {"BOOL": True}

    def test_invalid_json_does_not_raise(self, app_module):
        message = {
            "MessageId": "msg-bad",
            "Body": "not-json",
            "ReceiptHandle": "rh-2",
        }
        app_module.dynamodb_client.reset_mock()
        app_module.process_message(message)
        app_module.dynamodb_client.put_item.assert_not_called()


class TestEnsureDynamoDBTable:
    def test_skips_when_create_disabled(self, app_module):
        app_module.DYNAMODB_CREATE_TABLE = False
        app_module.dynamodb_client.reset_mock()
        app_module.ensure_dynamodb_table()
        app_module.dynamodb_client.describe_table.assert_not_called()
