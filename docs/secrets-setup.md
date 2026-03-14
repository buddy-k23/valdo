# Secrets provider setup

CM3 Batch Automations supports pluggable secrets providers via `SECRETS_PROVIDER`.

## Providers

- `env` (default): reads `ORACLE_USER`, `ORACLE_PASSWORD`, `ORACLE_DSN` directly from environment variables.
- `cyberark`: fetches Oracle credentials from CyberArk Central Credential Provider (CCP).
- `hashicorp`, `azure_keyvault`: placeholders for future integrations.

## Environment provider (default)

```bash
SECRETS_PROVIDER=env
ORACLE_USER=CM3INT
ORACLE_PASSWORD=***
ORACLE_DSN=localhost:1521/FREEPDB1
```

## CyberArk provider

```bash
SECRETS_PROVIDER=cyberark
CYBERARK_CCP_URL=https://cyberark.internal.bank.com
CYBERARK_APP_ID=cm3-batch-automations
CYBERARK_SAFE=CM3-Batch-Dev
CYBERARK_OBJECT=Oracle-DEV-Credentials
```

`OracleConnection.from_env()` resolves secrets through the configured provider. Secret *values* must never be logged; only key names and provider metadata are safe to log.
