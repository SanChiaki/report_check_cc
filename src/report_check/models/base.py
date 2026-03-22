from abc import ABC, abstractmethod
from enum import Enum
from typing import Any

class ModelType(Enum):
    TEXT = "text"
    MULTIMODAL = "multimodal"

class BaseModelAdapter(ABC):
    def __init__(self, config: dict[str, Any]):
        self.config = config

    @abstractmethod
    async def call_text_model(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def call_multimodal_model(self, prompt: str, image: bytes, **kwargs) -> str:
        pass

    @abstractmethod
    def supports_model_type(self, model_type: ModelType) -> bool:
        pass
