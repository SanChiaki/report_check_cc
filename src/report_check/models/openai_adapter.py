import base64
from typing import Any
from openai import AsyncOpenAI
from report_check.models.base import BaseModelAdapter, ModelType

class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.client = AsyncOpenAI(api_key=config.get("api_key", ""), base_url=config.get("base_url"))
        self.text_model = config.get("text_model", "gpt-4o")
        self.multimodal_model = config.get("multimodal_model", "gpt-4o")

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        response = await self.client.chat.completions.create(
            model=self.text_model, messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1), max_tokens=kwargs.get("max_tokens", 2000))
        return response.choices[0].message.content

    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        response = await self.client.chat.completions.create(
            model=self.multimodal_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
            ]}],
            temperature=kwargs.get("temperature", 0.1), max_tokens=kwargs.get("max_tokens", 1000))
        return response.choices[0].message.content

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True
