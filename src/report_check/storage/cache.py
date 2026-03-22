import hashlib


class ResultCache:
    def __init__(self):
        self._cache: dict[str, dict] = {}

    def get_cache_key(self, image_data: bytes, requirement: str) -> str:
        image_hash = hashlib.md5(image_data).hexdigest()
        req_hash = hashlib.md5(requirement.encode()).hexdigest()
        return f"{image_hash}:{req_hash}"

    def get(self, key: str) -> dict | None:
        return self._cache.get(key)

    def set(self, key: str, value: dict):
        self._cache[key] = value

    def clear(self):
        self._cache.clear()
