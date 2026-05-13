import json
import time
from typing import Optional, Any


class MemoryCache:
    def __init__(self, default_ttl: int = 300):
        self._store = {}
        self.default_ttl = default_ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self._store:
            return None
        data, expiry = self._store[key]
        if time.time() > expiry:
            del self._store[key]
            return None
        return data

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        expiry = time.time() + (ttl or self.default_ttl)
        self._store[key] = (value, expiry)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


cache = MemoryCache()
