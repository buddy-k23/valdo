"""Secrets provider abstraction for environment and vault-backed credentials."""

from __future__ import annotations

from abc import ABC, abstractmethod
import json
import os
from typing import Dict, Optional
from urllib import parse, request


class SecretsProvider(ABC):
    """Interface for retrieving secrets by key."""

    @abstractmethod
    def get_secret(self, key: str) -> str:
        """Return a secret value for key or raise KeyError/RuntimeError."""


class EnvSecretsProvider(SecretsProvider):
    """Read secrets from environment variables (backward-compatible default)."""

    def get_secret(self, key: str) -> str:
        value = os.getenv(key)
        if value is None or value == "":
            raise KeyError(f"Missing required secret: {key}")
        return value


class CyberArkSecretsProvider(SecretsProvider):
    """Fetch secrets from CyberArk CCP REST API."""

    def __init__(self, ccp_url: Optional[str] = None, app_id: Optional[str] = None):
        self.ccp_url = (ccp_url or os.getenv("CYBERARK_CCP_URL", "")).rstrip("/")
        self.app_id = app_id or os.getenv("CYBERARK_APP_ID", "")
        if not self.ccp_url:
            raise ValueError("CYBERARK_CCP_URL is required for cyberark provider")
        if not self.app_id:
            raise ValueError("CYBERARK_APP_ID is required for cyberark provider")

    def get_secret(self, key: str) -> str:
        safe = os.getenv("CYBERARK_SAFE", "")
        obj = os.getenv("CYBERARK_OBJECT", "")
        if not safe or not obj:
            raise ValueError("CYBERARK_SAFE and CYBERARK_OBJECT are required for cyberark provider")

        params = {
            "AppID": self.app_id,
            "Safe": safe,
            "Object": obj,
            "Reason": f"cm3-batch/{key}",
        }
        query = parse.urlencode(params)
        url = f"{self.ccp_url}/AIMWebService/api/Accounts?{query}"
        with request.urlopen(url, timeout=10) as resp:  # nosec B310 (controlled URL from env)
            payload = json.loads(resp.read().decode("utf-8"))

        candidate = payload.get(key)
        if candidate:
            return candidate

        content = payload.get("Content")
        if content:
            return content

        raise KeyError(f"CyberArk secret not found for requested key: {key}")


class HashiCorpVaultSecretsProvider(SecretsProvider):
    """Placeholder provider for future Vault integration."""

    def get_secret(self, key: str) -> str:
        raise NotImplementedError("HashiCorp Vault provider not configured in this environment")


class AzureKeyVaultSecretsProvider(SecretsProvider):
    """Placeholder provider for future Azure Key Vault integration."""

    def get_secret(self, key: str) -> str:
        raise NotImplementedError("Azure Key Vault provider not configured in this environment")


def get_secrets_provider(provider_name: Optional[str] = None) -> SecretsProvider:
    """Return a provider instance based on SECRETS_PROVIDER (default: env)."""
    name = (provider_name or os.getenv("SECRETS_PROVIDER", "env")).strip().lower()
    if name == "env":
        return EnvSecretsProvider()
    if name == "cyberark":
        return CyberArkSecretsProvider()
    if name in {"hashicorp", "vault"}:
        return HashiCorpVaultSecretsProvider()
    if name in {"azure_keyvault", "azure", "akv"}:
        return AzureKeyVaultSecretsProvider()
    raise ValueError(f"Unsupported SECRETS_PROVIDER: {name}")


def load_oracle_credentials(provider: Optional[SecretsProvider] = None) -> Dict[str, str]:
    """Resolve Oracle credentials using configured provider without logging values."""
    resolver = provider or get_secrets_provider()
    return {
        "ORACLE_USER": resolver.get_secret("ORACLE_USER"),
        "ORACLE_PASSWORD": resolver.get_secret("ORACLE_PASSWORD"),
        "ORACLE_DSN": resolver.get_secret("ORACLE_DSN"),
    }
