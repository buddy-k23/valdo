"""Authentication and host allowlist coverage for the webhook and API tester routes."""
from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.main import app

_REAL_ASYNC_CLIENT = httpx.AsyncClient


@pytest.fixture
def keyed(monkeypatch):
    """Configure a single admin key and return a client."""
    monkeypatch.setenv("API_KEYS", "dev-key:admin")
    return TestClient(app)


def _proxy(client, url):
    """POST a GET request config to the proxy as an authenticated caller."""
    return client.post(
        "/api/v1/api-tester/proxy",
        data={"config": json.dumps({"method": "GET", "url": url})},
        headers={"X-API-Key": "dev-key"},
    )


def _mock_transport_client(handler):
    """Return an AsyncClient factory that routes requests through ``handler``."""
    def factory(**kwargs):
        return _REAL_ASYNC_CLIENT(transport=httpx.MockTransport(handler), **kwargs)
    return factory


class TestRoutesRequireApiKey:
    @pytest.mark.parametrize(
        "method,path",
        [
            ("post", "/api/v1/webhook/validate"),
            ("get", "/api/v1/webhook/jobs/some-job"),
            ("post", "/api/v1/api-tester/proxy"),
            ("get", "/api/v1/api-tester/suites"),
        ],
    )
    def test_missing_key_returns_401(self, keyed, method, path):
        response = getattr(keyed, method)(path)

        assert response.status_code == 401

    def test_valid_key_reaches_api_tester(self, keyed, tmp_path, monkeypatch):
        monkeypatch.setattr("src.api.routers.api_tester.SUITES_DIR", tmp_path)

        response = keyed.get("/api/v1/api-tester/suites", headers={"X-API-Key": "dev-key"})

        assert response.status_code == 200


class TestProxyHostAllowlist:
    @pytest.fixture(autouse=True)
    def _api_key(self, monkeypatch):
        monkeypatch.setenv("API_KEYS", "dev-key:admin")

    def test_unlisted_host_rejected_before_any_request(self, monkeypatch):
        monkeypatch.setenv("API_TESTER_ALLOWED_HOSTS", "api.example.com")
        calls = []

        def handler(request):
            calls.append(request.url)
            return httpx.Response(200)

        monkeypatch.setattr(
            "src.api.routers.api_tester.httpx.AsyncClient", _mock_transport_client(handler)
        )

        response = _proxy(TestClient(app), "http://169.254.169.254/latest/meta-data/")

        assert response.status_code == 403
        assert calls == []

    def test_listed_host_is_proxied(self, monkeypatch):
        monkeypatch.setenv("API_TESTER_ALLOWED_HOSTS", "api.example.com")
        monkeypatch.setattr(
            "src.api.routers.api_tester.httpx.AsyncClient",
            _mock_transport_client(lambda request: httpx.Response(200, text="ok")),
        )

        response = _proxy(TestClient(app), "https://api.example.com/ping")

        assert response.status_code == 200
        assert response.json()["body"] == "ok"

    def test_redirect_to_unlisted_host_is_blocked(self, monkeypatch):
        monkeypatch.setenv("API_TESTER_ALLOWED_HOSTS", "api.example.com")
        calls = []

        def handler(request):
            calls.append(request.url.host)
            if request.url.host == "api.example.com":
                return httpx.Response(302, headers={"Location": "http://internal.local/secret"})
            return httpx.Response(200, text="secret")

        monkeypatch.setattr(
            "src.api.routers.api_tester.httpx.AsyncClient", _mock_transport_client(handler)
        )

        response = _proxy(TestClient(app), "https://api.example.com/start")

        assert response.status_code == 403
        assert calls == ["api.example.com"]

    def test_no_allowlist_keeps_existing_behaviour(self, monkeypatch):
        monkeypatch.delenv("API_TESTER_ALLOWED_HOSTS", raising=False)
        monkeypatch.setattr(
            "src.api.routers.api_tester.httpx.AsyncClient",
            _mock_transport_client(lambda request: httpx.Response(200, text="ok")),
        )

        response = _proxy(TestClient(app), "http://any-host.example/")

        assert response.status_code == 200
