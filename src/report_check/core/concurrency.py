import asyncio
from contextlib import asynccontextmanager
from typing import Awaitable, Callable
from urllib.parse import urlparse


class EndpointConcurrencyState:
    def __init__(self, max_concurrency: int | None):
        self.semaphore = self._build_semaphore(max_concurrency)
        self._counter_lock = asyncio.Lock()
        self.inflight = 0

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

    @asynccontextmanager
    async def acquire(self):
        if self.semaphore is not None:
            await self.semaphore.acquire()

        async with self._counter_lock:
            self.inflight += 1

        try:
            yield
        finally:
            async with self._counter_lock:
                self.inflight = max(0, self.inflight - 1)
            if self.semaphore is not None:
                self.semaphore.release()


class ExternalApiLimiter:
    def __init__(
        self,
        default_max_concurrency: int | None = None,
        by_endpoint: dict[str, int] | None = None,
    ):
        self._default_state = EndpointConcurrencyState(default_max_concurrency)
        self._endpoint_states = {
            str(key): EndpointConcurrencyState(value)
            for key, value in (by_endpoint or {}).items()
        }

    def resolve_key(self, api_config: dict) -> str | None:
        name = api_config.get("name")
        endpoint = str(api_config.get("endpoint", "") or "")
        host = urlparse(endpoint).netloc or None

        if name is not None and str(name) in self._endpoint_states:
            return str(name)
        if host is not None and host in self._endpoint_states:
            return host
        if name:
            return str(name)
        return host

    @asynccontextmanager
    async def acquire(self, api_config: dict):
        key = self.resolve_key(api_config)
        state = self._endpoint_states.get(key) if key else None
        if state is None:
            state = self._default_state

        async with state.acquire():
            yield


class TaskExecutionContext:
    def __init__(self):
        self._rendered_pages_cache: dict[str, list[bytes]] = {}
        self._render_tasks: dict[str, asyncio.Task[list[bytes]]] = {}
        self._render_lock = asyncio.Lock()

    def _get_render_key(self, report_data) -> str:
        file_path = None
        if hasattr(report_data, "metadata"):
            file_path = report_data.metadata.get("file_path")

        source_type = getattr(report_data, "source_type", "unknown")
        if file_path:
            return f"{source_type}:{file_path}"
        return f"{source_type}:{id(report_data)}"

    async def get_rendered_pages(
        self,
        report_data,
        render_func: Callable[[], Awaitable[list[bytes]]],
    ) -> tuple[list[bytes], bool]:
        key = self._get_render_key(report_data)

        async with self._render_lock:
            cached_pages = self._rendered_pages_cache.get(key)
            if cached_pages is not None:
                return cached_pages, True

            render_task = self._render_tasks.get(key)
            created = False
            if render_task is None:
                render_task = asyncio.create_task(render_func())
                self._render_tasks[key] = render_task
                created = True

        try:
            pages = await render_task
        except Exception:
            if created:
                async with self._render_lock:
                    if self._render_tasks.get(key) is render_task:
                        self._render_tasks.pop(key, None)
            raise

        if created:
            async with self._render_lock:
                self._rendered_pages_cache[key] = pages
                if self._render_tasks.get(key) is render_task:
                    self._render_tasks.pop(key, None)

        return pages, not created
