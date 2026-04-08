"""Dynamic token fetcher for OpenAI-compatible API authentication.

Supports registering custom token fetcher functions that take account/password
and return an auth token. The token is cached with optional TTL.

Usage:
    from report_check.models.token_fetcher import register_token_fetcher

    @register_token_fetcher("my_auth")
    async def my_token_fetcher(account: str, password: str, **kwargs) -> str:
        # Call your auth endpoint
        return "your-dynamic-token"
"""

import logging
import time
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class TokenFetcherFunc(Protocol):
    async def __call__(self, account: str, password: str, **kwargs) -> str: ...


_registry: dict[str, TokenFetcherFunc] = {}


def register_token_fetcher(name: str = "default"):
    """Decorator to register a token fetcher function.

    Example:
        @register_token_fetcher("my_provider")
        async def fetch_token(account: str, password: str, **kwargs) -> str:
            async with httpx.AsyncClient() as client:
                resp = await client.post("https://auth.example.com/token", json={
                    "account": account,
                    "password": password,
                })
                resp.raise_for_status()
                return resp.json()["token"]
    """
    def decorator(func: TokenFetcherFunc) -> TokenFetcherFunc:
        _registry[name] = func
        logger.info(f"Registered token fetcher: {name}")
        return func
    return decorator


def get_token_fetcher(name: str = "default") -> TokenFetcherFunc:
    """Get a registered token fetcher by name."""
    if name not in _registry:
        raise ValueError(
            f"Token fetcher '{name}' not registered. "
            f"Available: {list(_registry.keys())}. "
            f"Use @register_token_fetcher('{name}') to register one."
        )
    return _registry[name]


class TokenCache:
    """Simple in-memory token cache with TTL."""

    def __init__(self, ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self._token: str | None = None
        self._expires_at: float = 0

    def get(self) -> str | None:
        if self._token and time.time() < self._expires_at:
            return self._token
        return None

    def set(self, token: str):
        self._token = token
        self._expires_at = time.time() + self.ttl_seconds

    def invalidate(self):
        self._token = None
        self._expires_at = 0
