import asyncio
import logging
from contextlib import asynccontextmanager
from report_check.models.base import BaseModelAdapter

logger = logging.getLogger(__name__)


class ProviderConcurrencyState:
    def __init__(self, config: dict | None = None):
        config = config or {}
        self.total_semaphore = self._build_semaphore(config.get("max_concurrency"))
        self.text_semaphore = self._build_semaphore(config.get("text_max_concurrency"))
        self.multimodal_semaphore = self._build_semaphore(config.get("multimodal_max_concurrency"))
        self._counter_lock = asyncio.Lock()
        self.inflight_total = 0
        self.inflight_text = 0
        self.inflight_multimodal = 0

    @staticmethod
    def _build_semaphore(value) -> asyncio.Semaphore | None:
        if value is None:
            return None
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return None
        if limit <= 0:
            return None
        return asyncio.Semaphore(limit)


class ModelManager:
    def __init__(self, default_provider: str = "openai"):
        self.default_provider = default_provider
        self._adapters: dict[str, BaseModelAdapter] = {}
        self._provider_states: dict[str, ProviderConcurrencyState] = {}

    def register_adapter(self, name: str, adapter: BaseModelAdapter):
        self._adapters[name] = adapter
        self._provider_states[name] = ProviderConcurrencyState(adapter.config)

    def get_adapter(self, provider: str | None = None) -> BaseModelAdapter:
        provider = provider or self.default_provider
        if provider not in self._adapters:
            raise ValueError(f"Unknown provider: {provider}")
        return self._adapters[provider]

    async def call_text_model(self, prompt: str, provider: str | None = None, retry: int = 3, **kwargs) -> str:
        provider_name = provider or self.default_provider
        adapter = self.get_adapter(provider_name)
        return await self._with_retry(
            lambda: self._call_with_limits(
                provider_name,
                "text",
                adapter.call_text_model,
                prompt,
                **kwargs,
            ),
            retry,
        )

    async def call_multimodal_model(self, prompt: str, image: bytes, provider: str | None = None,
                                    retry: int = 3, extra_images: list[bytes] | None = None, **kwargs) -> str:
        provider_name = provider or self.default_provider
        adapter = self.get_adapter(provider_name)
        return await self._with_retry(
            lambda: self._call_with_limits(
                provider_name,
                "multimodal",
                adapter.call_multimodal_model,
                prompt,
                image=image,
                extra_images=extra_images,
                **kwargs,
            ),
            retry,
        )

    async def _with_retry(self, func, max_retries: int):
        for attempt in range(max_retries):
            try:
                return await func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Call failed (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(min(2**attempt, 10))

    async def _call_with_limits(self, provider: str, model_type: str, func, *args, **kwargs):
        async with self._acquire_limits(provider, model_type):
            return await func(*args, **kwargs)

    @asynccontextmanager
    async def _acquire_limits(self, provider: str, model_type: str):
        state = self._provider_states.get(provider)
        if state is None:
            yield
            return

        semaphores = []
        if model_type == "text":
            semaphores.append(state.text_semaphore)
        else:
            semaphores.append(state.multimodal_semaphore)
        semaphores.append(state.total_semaphore)

        acquired: list[asyncio.Semaphore] = []
        try:
            for semaphore in semaphores:
                if semaphore is not None:
                    await semaphore.acquire()
                    acquired.append(semaphore)

            async with state._counter_lock:
                state.inflight_total += 1
                if model_type == "text":
                    state.inflight_text += 1
                else:
                    state.inflight_multimodal += 1

            yield
        finally:
            async with state._counter_lock:
                state.inflight_total = max(0, state.inflight_total - 1)
                if model_type == "text":
                    state.inflight_text = max(0, state.inflight_text - 1)
                else:
                    state.inflight_multimodal = max(0, state.inflight_multimodal - 1)

            for semaphore in reversed(acquired):
                semaphore.release()

    def get_inflight_stats(self) -> dict[str, int]:
        return {
            "model_inflight": sum(state.inflight_total for state in self._provider_states.values()),
            "model_text_inflight": sum(state.inflight_text for state in self._provider_states.values()),
            "model_multimodal_inflight": sum(state.inflight_multimodal for state in self._provider_states.values()),
        }
