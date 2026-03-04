from __future__ import annotations

import json
import os
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from src.models.source_config import AuthConfig

_UA = "open-ipa-library-catalog/2.0"

# Ключевые слова для детекции Cloudflare/challenge страниц
_CHALLENGE_MARKERS = ("just a moment", "cf_chl", "cloudflare", "enable javascript")

# Ключевые слова для детекции login-wall
_AUTH_MARKERS = ("sign in", "log in", "login required", "unauthorized", "please login")


class NetworkError(Exception):
    """Сетевая ошибка (таймаут, DNS, соединение)."""


class HttpStatusError(Exception):
    """Сервер вернул ненормальный HTTP-статус."""

    def __init__(self, status: int, url: str) -> None:
        super().__init__(f"HTTP {status} from {url}")
        self.status = status
        self.url = url


class JsonParseError(Exception):
    """Тело ответа не является валидным JSON."""


class HtmlChallengeError(Exception):
    """Сервер вернул Cloudflare-challenge или иную HTML-заглушку."""


class AuthRequiredError(Exception):
    """Сервер вернул страницу авторизации."""


def _detect_html_problem(content: str, url: str) -> None:
    """Бросает HtmlChallengeError или AuthRequiredError если контент — не JSON."""
    lower = content.lower()
    for marker in _CHALLENGE_MARKERS:
        if marker in lower:
            snippet = " ".join(content.strip().split())[:120]
            raise HtmlChallengeError(
                f"response is HTML Cloudflare challenge from {url} (snippet: {snippet})"
            )
    for marker in _AUTH_MARKERS:
        if marker in lower:
            snippet = " ".join(content.strip().split())[:120]
            raise AuthRequiredError(
                f"response is HTML login-wall from {url} (snippet: {snippet})"
            )
    if content.lstrip().startswith("<"):
        snippet = " ".join(content.strip().split())[:120]
        raise HtmlChallengeError(
            f"response is HTML, not JSON from {url} (snippet: {snippet})"
        )
    raise JsonParseError(f"response is not valid JSON from {url}")


def _build_headers(auth: AuthConfig | None, extra: dict[str, str] | None = None) -> dict[str, str]:
    headers: dict[str, str] = {
        "User-Agent": _UA,
        "Accept": "application/json,text/html,*/*",
    }
    if auth and auth.type == "cookie" and auth.cookie_env:
        cookie = os.getenv(auth.cookie_env, "")
        if cookie:
            headers["Cookie"] = cookie
    if auth and auth.type == "bearer" and auth.token_env:
        token = os.getenv(auth.token_env, "")
        if token:
            headers["Authorization"] = f"Bearer {token}"
    if extra:
        headers.update(extra)
    return headers


class HttpClient:
    """Единый HTTP-клиент с таймаутами, ретраями и детекцией challenge/HTML/auth."""

    def __init__(
        self,
        timeout: int = 20,
        retries: int = 2,
        retry_delay: float = 1.0,
        auth: AuthConfig | None = None,
    ) -> None:
        self.timeout = timeout
        self.retries = retries
        self.retry_delay = retry_delay
        self.auth = auth

    def fetch_text(self, url: str, extra_headers: dict[str, str] | None = None) -> str:
        """Загружает текст по URL. Возбуждает NetworkError / HttpStatusError при сбое."""
        headers = _build_headers(self.auth, extra_headers)
        req = Request(url, headers=headers)
        last_exc: Exception | None = None

        for attempt in range(self.retries + 1):
            if attempt > 0:
                time.sleep(self.retry_delay * attempt)
            try:
                with urlopen(req, timeout=self.timeout) as resp:
                    status = getattr(resp, "status", None)
                    if status is not None and (status < 200 or status >= 300):
                        raise HttpStatusError(status, url)
                    return resp.read().decode("utf-8", errors="replace")
            except HTTPError as exc:
                raise HttpStatusError(exc.code, url) from exc
            except (URLError, TimeoutError, OSError) as exc:
                last_exc = exc

        raise NetworkError(f"Failed to reach {url} after {self.retries + 1} attempts: {last_exc}")

    def fetch_json(self, url: str, extra_headers: dict[str, str] | None = None) -> Any:
        """Загружает и парсит JSON. Детектирует HTML-ответы и challenge-страницы."""
        content = self.fetch_text(url, extra_headers)
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            _detect_html_problem(content, url)

    def fetch_html(self, url: str, extra_headers: dict[str, str] | None = None) -> str:
        """Загружает HTML-страницу. Детектирует challenge и login-wall."""
        content = self.fetch_text(url, extra_headers)
        lower = content.lower()
        for marker in _CHALLENGE_MARKERS:
            if marker in lower:
                snippet = " ".join(content.strip().split())[:120]
                raise HtmlChallengeError(
                    f"HTML challenge detected at {url} (snippet: {snippet})"
                )
        for marker in _AUTH_MARKERS:
            if marker in lower:
                snippet = " ".join(content.strip().split())[:120]
                raise AuthRequiredError(
                    f"Login wall detected at {url} (snippet: {snippet})"
                )
        return content
