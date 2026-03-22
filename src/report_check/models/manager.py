import asyncio
import logging
from report_check.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self, default_provider: str = "openai"):
        self.default_provider = default_provider
        self._adapters: dict[str, BaseModelAdapter] = {}

    def register_adapter(self, name: str, adapter: BaseModelAdapter):
        self._adapters[name] = adapter

    def get_adapter(self, provider: str | None = None) -> BaseModelAdapter:
        provider = provider or self.default_provider
        if provider not in self._adapters:
            raise ValueError(f"Unknown provider: {provider}")
        return self._adapters[provider]

    async def call_text_model(self, prompt: str, provider: str | None = None, retry: int = 3, **kwargs) -> str:
        adapter = self.get_adapter(provider)
        return await self._with_retry(adapter.call_text_model, retry, prompt, **kwargs)

    async def call_multimodal_model(self, prompt: str, image: bytes, provider: str | None = None, retry: int = 3, **kwargs) -> str:
        adapter = self.get_adapter(provider)
        return await self._with_retry(adapter.call_multimodal_model, retry, prompt, image=image, **kwargs)

    async def _with_retry(self, func, max_retries: int, *args, **kwargs):
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Call failed (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(min(2**attempt, 10))
