from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RateLimit:
    requests_per_minute: int = 30
    burst: int = 5


@dataclass
class AuthConfig:
    type: str = "none"          # none | cookie | bearer | basic
    cookie_env: str = ""        # имя env-переменной с cookie-строкой
    token_env: str = ""         # имя env-переменной с токеном
    username_env: str = ""
    password_env: str = ""


@dataclass
class SourceConfig:
    id: str
    name: str
    type: str                   # playcover_json | html_catalog | static_mirror
    catalog_url: str
    adapter: str
    enabled: bool = True
    priority: int = 50
    timeout_sec: int = 20
    retries: int = 2
    auth: AuthConfig = field(default_factory=AuthConfig)
    rate_limit: RateLimit = field(default_factory=RateLimit)
    options: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SourceConfig":
        auth_raw = d.get("auth") or {}
        rate_raw = d.get("rateLimit") or {}
        return cls(
            id=d["id"],
            name=d["name"],
            type=d["type"],
            catalog_url=d["catalogUrl"],
            adapter=d["adapter"],
            enabled=d.get("enabled", True),
            priority=d.get("priority", 50),
            timeout_sec=d.get("timeoutSec", 20),
            retries=d.get("retries", 2),
            auth=AuthConfig(
                type=auth_raw.get("type", "none"),
                cookie_env=auth_raw.get("cookieEnv", ""),
                token_env=auth_raw.get("tokenEnv", ""),
                username_env=auth_raw.get("usernameEnv", ""),
                password_env=auth_raw.get("passwordEnv", ""),
            ),
            rate_limit=RateLimit(
                requests_per_minute=rate_raw.get("requestsPerMinute", 30),
                burst=rate_raw.get("burst", 5),
            ),
            options=d.get("options") or {},
        )
