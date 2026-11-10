"""
Priority Queue Manager with Request Abandonment Handling for THE RELAY.
Uses heap-based priority ordering and explicit TTL eviction.
"""

import asyncio
import heapq
import time
from dataclasses import dataclass, field
from typing import Any, List, Optional

@dataclass(order=True)
class QueuedItem:
    priority: int  # Lower integer = higher priority (0 = P0, 1 = P1, 2 = P2)
    arrival_time: float = field(compare=False)
    ttl_seconds: float = field(compare=False)
    request_id: str = field(compare=False)
    payload: Any = field(compare=False)
    future: Optional[asyncio.Future] = field(default=None, compare=False)

    def is_expired(self) -> bool:
        return (time.time() - self.arrival_time) > self.ttl_seconds

class RequestQueueManager:
    def __init__(self, max_capacity: int = 50, default_ttl_sec: float = 15.0):
        self.max_capacity = max_capacity
        self.default_ttl_sec = default_ttl_sec
        self._heap: List[QueuedItem] = []
        self.peak_queue_length = 0
        self.abandoned_count = 0

    @property
    def qsize(self) -> int:
        return len(self._heap)

    def is_full(self) -> bool:
        return len(self._heap) >= self.max_capacity

    async def enqueue(
        self,
        request_id: str,
        payload: Any,
        priority: int = 1,
        ttl_seconds: Optional[float] = None
    ) -> asyncio.Future:
        """Enqueues a request item with priority and timeout deadline."""
        if self.is_full():
            raise asyncio.QueueFull("Queue capacity exceeded. Admission rejected.")

        loop = asyncio.get_running_loop()
        future = loop.create_future()
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl_sec

        item = QueuedItem(
            priority=priority,
            arrival_time=time.time(),
            ttl_seconds=ttl,
            request_id=request_id,
            payload=payload,
            future=future
        )

        heapq.heappush(self._heap, item)
        if len(self._heap) > self.peak_queue_length:
            self.peak_queue_length = len(self._heap)

        return future

    async def dequeue_next(self) -> Optional[QueuedItem]:
        """Dequeues the highest priority available item, filtering out abandoned requests."""
        while self._heap:
            item = heapq.heappop(self._heap)
            if item.is_expired():
                self.abandoned_count += 1
                if item.future and not item.future.done():
                    item.future.set_exception(
                        TimeoutError(f"Request {item.request_id} abandoned: exceeded client waiting timeout.")
                    )
                continue
            return item
        return None
