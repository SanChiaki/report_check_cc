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
