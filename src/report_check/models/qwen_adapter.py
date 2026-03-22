import base64
from typing import Any
import httpx
from report_check.models.base import BaseModelAdapter, ModelType

class QwenAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.base_url = config.get("base_url", "")
        self.api_key = config.get("api_key", "")
        self.text_model = config.get("text_model", "qwen-turbo")
        self.multimodal_model = config.get("multimodal_model", "qwen-vl-plus")

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/v1/chat/completions",
                json={"model": self.text_model, "messages": [{"role": "user", "content": prompt}],
                       "temperature": kwargs.get("temperature", 0.1), "max_tokens": kwargs.get("max_tokens", 2000)},
                headers=self._headers())
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{self.base_url}/v1/chat/completions",
                json={"model": self.multimodal_model,
                      "messages": [{"role": "user", "content": [
                          {"type": "text", "text": prompt},
                          {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}}
                      ]}],
                      "temperature": kwargs.get("temperature", 0.1), "max_tokens": kwargs.get("max_tokens", 1000)},
                headers=self._headers())
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True
