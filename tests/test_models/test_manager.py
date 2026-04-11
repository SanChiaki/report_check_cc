import asyncio
import pytest
from report_check.models.base import BaseModelAdapter, ModelType
from report_check.models.manager import ModelManager

class FakeAdapter(BaseModelAdapter):
    async def call_text_model(self, prompt: str, **kwargs) -> str:
        return "fake text response"
    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        return "fake multimodal response"
    def supports_model_type(self, model_type: ModelType) -> bool:
        return True

class TestModelManager:
    def test_register_and_get_adapter(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))
        adapter = manager.get_adapter("fake")
        assert isinstance(adapter, FakeAdapter)

    def test_get_default_adapter(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))
        adapter = manager.get_adapter()
        assert isinstance(adapter, FakeAdapter)

    def test_get_unknown_adapter_raises(self):
        manager = ModelManager(default_provider="fake")
        with pytest.raises(ValueError, match="Unknown provider"):
            manager.get_adapter("nonexistent")

    @pytest.mark.asyncio
    async def test_call_text_model(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))
        result = await manager.call_text_model("hello")
        assert result == "fake text response"

    @pytest.mark.asyncio
    async def test_call_multimodal_model(self):
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", FakeAdapter({}))
        result = await manager.call_multimodal_model("hello", b"image_data")
        assert result == "fake multimodal response"

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        adapter = FakeAdapter({})
        call_count = 0
        async def failing_then_success(prompt, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"
        adapter.call_text_model = failing_then_success
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", adapter)
        result = await manager.call_text_model("test", retry=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_provider_max_concurrency_limits_total_inflight_calls(self):
        adapter = FakeAdapter({"max_concurrency": 1})
        inflight = 0
        max_inflight = 0
        first_started = asyncio.Event()
        release = asyncio.Event()
        lock = asyncio.Lock()

        async def controlled_text(prompt, **kwargs):
            nonlocal inflight, max_inflight
            async with lock:
                inflight += 1
                max_inflight = max(max_inflight, inflight)
                first_started.set()
            await release.wait()
            async with lock:
                inflight -= 1
            return prompt

        adapter.call_text_model = controlled_text
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", adapter)

        first_call = asyncio.create_task(manager.call_text_model("first"))
        await asyncio.wait_for(first_started.wait(), timeout=1)
        second_call = asyncio.create_task(manager.call_text_model("second"))
        await asyncio.sleep(0.05)
        release.set()

        assert await first_call == "first"
        assert await second_call == "second"
        assert max_inflight == 1

    @pytest.mark.asyncio
    async def test_text_and_multimodal_limits_are_enforced_independently(self):
        adapter = FakeAdapter({
            "max_concurrency": 2,
            "text_max_concurrency": 1,
            "multimodal_max_concurrency": 1,
        })
        counters = {"text": 0, "multimodal": 0, "max_text": 0, "max_multimodal": 0, "max_total": 0}
        release = asyncio.Event()
        lock = asyncio.Lock()

        async def controlled_text(prompt, **kwargs):
            async with lock:
                counters["text"] += 1
                counters["max_text"] = max(counters["max_text"], counters["text"])
                counters["max_total"] = max(
                    counters["max_total"],
                    counters["text"] + counters["multimodal"],
                )
            await release.wait()
            async with lock:
                counters["text"] -= 1
            return prompt

        async def controlled_multimodal(prompt, image: bytes, **kwargs):
            async with lock:
                counters["multimodal"] += 1
                counters["max_multimodal"] = max(counters["max_multimodal"], counters["multimodal"])
                counters["max_total"] = max(
                    counters["max_total"],
                    counters["text"] + counters["multimodal"],
                )
            await release.wait()
            async with lock:
                counters["multimodal"] -= 1
            return prompt

        adapter.call_text_model = controlled_text
        adapter.call_multimodal_model = controlled_multimodal
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", adapter)

        text_one = asyncio.create_task(manager.call_text_model("text-1"))
        text_two = asyncio.create_task(manager.call_text_model("text-2"))
        multimodal_one = asyncio.create_task(manager.call_multimodal_model("mm-1", b"img"))
        await asyncio.sleep(0.05)
        release.set()

        await asyncio.gather(text_one, text_two, multimodal_one)
        assert counters["max_text"] == 1
        assert counters["max_multimodal"] == 1
        assert counters["max_total"] == 2

    @pytest.mark.asyncio
    async def test_retry_backoff_does_not_hold_provider_semaphore(self, monkeypatch):
        adapter = FakeAdapter({"max_concurrency": 1, "text_max_concurrency": 1})
        sleep_started = asyncio.Event()
        release_sleep = asyncio.Event()
        other_started = asyncio.Event()
        attempts = {"retrying": 0}

        async def controlled_text(prompt, **kwargs):
            if prompt == "retrying":
                attempts["retrying"] += 1
                if attempts["retrying"] == 1:
                    raise Exception("temporary failure")
                return "retried"

            other_started.set()
            return "other"

        async def fake_sleep(delay):
            sleep_started.set()
            await release_sleep.wait()

        adapter.call_text_model = controlled_text
        manager = ModelManager(default_provider="fake")
        manager.register_adapter("fake", adapter)
        monkeypatch.setattr("report_check.models.manager.asyncio.sleep", fake_sleep)

        retrying_call = asyncio.create_task(manager.call_text_model("retrying", retry=2))
        await asyncio.wait_for(sleep_started.wait(), timeout=1)

        other_call = asyncio.create_task(manager.call_text_model("other", retry=1))
        await asyncio.wait_for(other_started.wait(), timeout=1)
        release_sleep.set()

        assert await other_call == "other"
        assert await retrying_call == "retried"
