import base64
from typing import Any
from openai import AsyncOpenAI
from report_check.models.base import BaseModelAdapter, ModelType

def _normalize_base_url(base_url: str | None) -> str | None:
    """标准化 base_url，确保以 /v1 结尾"""
    if not base_url:
        return None
    base_url = base_url.rstrip("/")
    if not base_url.endswith("/v1"):
        base_url = base_url + "/v1"
    return base_url

class OpenAIAdapter(BaseModelAdapter):
    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        # 分别配置文本模型和多模态模型的 base_url
        text_base_url = config.get("text_base_url") or config.get("base_url")
        multimodal_base_url = config.get("multimodal_base_url") or config.get("base_url")

        self.text_client = AsyncOpenAI(
            api_key=config.get("api_key", ""),
            base_url=_normalize_base_url(text_base_url)
        )
        self.multimodal_client = AsyncOpenAI(
            api_key=config.get("api_key", ""),
            base_url=_normalize_base_url(multimodal_base_url)
        )

        self.text_model = config.get("text_model", "gpt-4o")
        self.multimodal_model = config.get("multimodal_model", "gpt-4o")

    async def call_text_model(self, prompt: str, **kwargs) -> str:
        response = await self.text_client.chat.completions.create(
            model=self.text_model, messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", 0.1), max_tokens=kwargs.get("max_tokens", 2000))
        return response.choices[0].message.content

    async def call_multimodal_model(self, prompt: str, image: bytes, image_format: str = "png",
                                    extra_images: list[bytes] | None = None, **kwargs) -> str:
        image_b64 = base64.b64encode(image).decode("utf-8")
        mime_type = f"image/{image_format}" if image_format in ("png", "jpeg", "jpg", "gif", "webp") else "image/png"
        if image_format == "jpg":
            mime_type = "image/jpeg"

        content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_b64}"}},
        ]

        # Append extra images (e.g. for signature comparison)
        for extra in (extra_images or []):
            extra_b64 = base64.b64encode(extra).decode("utf-8")
            content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{extra_b64}"}})

        response = await self.multimodal_client.chat.completions.create(
            model=self.multimodal_model,
            messages=[{"role": "user", "content": content}],
            temperature=kwargs.get("temperature", 0.1), max_tokens=kwargs.get("max_tokens", 1000))
        return response.choices[0].message.content

    def supports_model_type(self, model_type: ModelType) -> bool:
        return True
