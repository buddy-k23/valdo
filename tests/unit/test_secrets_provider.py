import json

from src.utils.secrets import (
    EnvSecretsProvider,
    get_secrets_provider,
    load_oracle_credentials,
    CyberArkSecretsProvider,
)


def test_env_provider_reads_oracle_creds(monkeypatch):
    monkeypatch.setenv("SECRETS_PROVIDER", "env")
    monkeypatch.setenv("ORACLE_USER", "u1")
    monkeypatch.setenv("ORACLE_PASSWORD", "p1")
    monkeypatch.setenv("ORACLE_DSN", "dsn1")

    creds = load_oracle_credentials()
    assert creds == {
        "ORACLE_USER": "u1",
        "ORACLE_PASSWORD": "p1",
        "ORACLE_DSN": "dsn1",
    }


def test_get_secrets_provider_default_env(monkeypatch):
    monkeypatch.delenv("SECRETS_PROVIDER", raising=False)
    assert isinstance(get_secrets_provider(), EnvSecretsProvider)


def test_cyberark_provider_uses_content_field(monkeypatch):
    monkeypatch.setenv("CYBERARK_CCP_URL", "https://vault.local")
    monkeypatch.setenv("CYBERARK_APP_ID", "cm3")
    monkeypatch.setenv("CYBERARK_SAFE", "safe1")
    monkeypatch.setenv("CYBERARK_OBJECT", "obj1")

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return json.dumps({"Content": "secret-from-cyberark"}).encode("utf-8")

    def _fake_urlopen(url, timeout=10):
        assert "AIMWebService/api/Accounts" in url
        assert "AppID=cm3" in url
        return _Resp()

    monkeypatch.setattr("src.utils.secrets.request.urlopen", _fake_urlopen)

    provider = CyberArkSecretsProvider()
    assert provider.get_secret("ORACLE_PASSWORD") == "secret-from-cyberark"
