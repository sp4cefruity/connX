"""
A small bounded in-memory cache: entries expire after `ttl_s` and, once
`max_entries` is reached, the least recently used entry is evicted.

Per-process only (lost on restart, not shared between workers). That is enough
to keep repeat searches and repeat routes off the free-tier provider quotas
(ADR 0005). `clock` is injectable so tests don't need to sleep.
"""
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Generic, Hashable, TypeVar

V = TypeVar("V")


class TTLCache(Generic[V]):
    def __init__(
        self,
        ttl_s: float,
        max_entries: int,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._clock = clock
        self._data: OrderedDict[Hashable, tuple[float, V]] = OrderedDict()

    def get(self, key: Hashable) -> V | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if self._clock() - stored_at >= self.ttl_s:
            del self._data[key]
            return None
        self._data.move_to_end(key)
        return value

    def set(self, key: Hashable, value: V) -> None:
        self._data[key] = (self._clock(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
