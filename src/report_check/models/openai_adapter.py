import base64
import logging
from typing import Any

import httpx
from openai import AsyncOpenAI

from report_check.models.base import BaseModelAdapter, ModelType
from report_check.models.token_fetcher import TokenCache, get_token_fetcher

logger = logging.getLogger(__name__)


def _normalize_base_url(base_url: str | None) -> str | None:
    """标准化 base_url，确保以 /v1 结尾"""
    if not base_url:
        return None
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"
    return base_url


def _create_auth_httpx_client(
    auth_mode: str,
    base_url: str | None,
    api_key: str = "",
    account: str = "",
    password: str = "",
    token_fetcher_name: str = "default",
    token_ttl: int = 300,
) -> tuple[httpx.AsyncClient, TokenCache | None]:
    """Create an httpx.AsyncClient with the appropriate auth configuration.

    Returns:
        (client, cache) — cache is None for api_key mode, TokenCache for dynamic_token mode.
    """
    headers = {"Content-Type": "application/json"}
    normalized_url = _normalize_base_url(base_url)
    cache = None

    if auth_mode == "api_key":
        headers["Authorization"] = f"Bearer {api_key}"
        client = httpx.AsyncClient(base_url=normalized_url, headers=headers)

    elif auth_mode == "dynamic_token":
        if not account or not password:
            raise ValueError(
                "dynamic_token auth requires 'account' and 'password' in config"
            )
        fetcher = get_token_fetcher(token_fetcher_name)
        cache = TokenCache(ttl_seconds=token_ttl)

        async def auth_hook(request: httpx.Request):
            token = cache.get()
            if token is None:
                try:
                    token = await fetcher(account=account, password=password)
                    cache.set(token)
                except Exception as e:
                    logger.error(f"Failed to fetch dynamic token: {e}")
                    raise
            request.headers["Authorization"] = f"{token}"

        async def response_hook(response: httpx.Response):
            if response.status_code == 401:
                logger.warning("Received 401, invalidating dynamic token cache")
                cache.invalidate()

        client = httpx.AsyncClient(
            base_url=normalized_url,
            headers=headers,
            event_hooks={"request": [auth_hook], "response": [response_hook]},
        )

    else:
        raise ValueError(f"Unknown auth_mode: {auth_mode}. Use 'api_key' or 'dynamic_token'.")

    return client, cache


class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)

        # Resolve auth config (per-client with fallback to top-level)
        default_auth_mode = config.get("auth_mode", "api_key")
        default_fetcher = config.get("token_fetcher", "default")
        default_ttl = config.get("token_ttl", 300)

        text_auth_mode = config.get("text_auth_mode", default_auth_mode)
        multimodal_auth_mode = config.get("multimodal_auth_mode", default_auth_mode)

        # Build text client
        text_kwargs = self._build_auth_kwargs(config, text_auth_mode, "text_")
        text_kwargs.setdefault("token_fetcher_name", default_fetcher)
        text_kwargs.setdefault("token_ttl", default_ttl)
        self.text_client, self._text_cache = _create_auth_httpx_client(**text_kwargs)
        self.text_client_openai = AsyncOpenAI(
            # Newer OpenAI SDKs require a non-empty api_key even when auth is
            # fully handled by the injected httpx client.
            api_key=self._sdk_api_key_placeholder(text_kwargs),
            base_url=text_kwargs.get("base_url"),  # Use the base_url from config
            http_client=self.text_client,
        )

        # Build multimodal client
        mm_kwargs = self._build_auth_kwargs(config, multimodal_auth_mode, "multimodal_")
        mm_kwargs.setdefault("token_fetcher_name", default_fetcher)
        mm_kwargs.setdefault("token_ttl", default_ttl)
        self.multimodal_client, self._mm_cache = _create_auth_httpx_client(**mm_kwargs)
        self.multimodal_client_openai = AsyncOpenAI(
            api_key=self._sdk_api_key_placeholder(mm_kwargs),
            base_url=mm_kwargs.get("base_url"),
            http_client=self.multimodal_client,
        )

        self.text_model = config.get("text_model", "gpt-4o")
        self.multimodal_model = config.get("multimodal_model", "gpt-4o")

    def _build_auth_kwargs(self, config: dict, auth_mode: str, prefix: str) -> dict:
        """Build kwargs for _create_auth_httpx_client based on auth_mode and prefix."""
        if auth_mode == "api_key":
            return {
                "auth_mode": "api_key",
                "api_key": config.get(f"{prefix}api_key") or config.get("api_key", ""),
                "base_url": config.get(f"{prefix}base_url") or config.get("base_url"),
            }
        elif auth_mode == "dynamic_token":
            return {
                "auth_mode": "dynamic_token",
                "base_url": config.get(f"{prefix}base_url") or config.get("base_url"),
                "account": config.get(f"{prefix}account") or config.get("account", ""),
                "password": config.get(f"{prefix}password") or config.get("password", ""),
                "token_fetcher_name": config.get(
                    f"{prefix}token_fetcher", config.get("token_fetcher", "default")
                ),
                "token_ttl": config.get(f"{prefix}token_ttl", config.get("token_ttl", 300)),
            }
        else:
            raise ValueError(f"Unknown auth_mode: {auth_mode}")

    @staticmethod
    def _sdk_api_key_placeholder(auth_kwargs: dict[str, Any]) -> str:
        """Return a non-empty api_key for the OpenAI SDK constructor.

        The actual request auth is handled by the injected httpx client, but
        the SDK still validates that api_key is present.
        """
        return auth_kwargs.get("api_key") or "unused-api-key"

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        response = await self.text_client_openai.chat.completions.create(
            model=self.text_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 2000),
            stream=False,
        )
        return response.choices[0].message.content

    async def call_multimodal_model(
        self,
        prompt: str,
        image: bytes,
        image_format: str = "png",
        extra_images: list[bytes] | None = None,
        **kwargs,
    ) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        mime_type = (
            f"image/{image_format}"
            if image_format in ("png", "jpeg", "jpg", "gif", "webp")
            else "image/png"
        )
        if image_format == "jpg":
            mime_type = "image/jpeg"

        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
        ]

        for extra in (extra_images or []):
            extra_b64 = base64.b64encode(extra).decode("utf-8")
            content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{extra_b64}"}}
            )

        response = await self.multimodal_client_openai.chat.completions.create(
            model=self.multimodal_model,
            messages=[{"role": "user", "content": content}],
            temperature=kwargs.get("temperature", 0.1),
            max_tokens=kwargs.get("max_tokens", 1000),
            stream=False,
        )
        return response.choices[0].message.content

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True

    async def close(self):
        """Close underlying httpx clients."""
        await self.text_client.aclose()
        await self.multimodal_client.aclose()
