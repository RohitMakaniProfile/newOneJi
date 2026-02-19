from __future__ import annotations

import asyncio
import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from typing import Any, AsyncIterator, Deque, DefaultDict, Dict, List, Optional, Tuple


# -----------------------------
# Event model
# -----------------------------

@dataclass(frozen=True)
class EventMeta:
    """
    id: monotonic integer (string-encoded for SSE compatibility)
    ts_ms: unix epoch milliseconds
    source: component name (runner/tool/store/http/etc.)
    correlation_id: typically run_id (or request_id)
    """
    id: str
    ts_ms: int
    source: str
    correlation_id: Optional[str] = None

    @staticmethod
    def new(
        *,
        event_id: int,
        source: str,
        correlation_id: Optional[str] = None,
        ts_ms: Optional[int] = None,
    ) -> "EventMeta":
        return EventMeta(
            id=str(event_id),
            ts_ms=int(ts_ms if ts_ms is not None else time.time() * 1000),
            source=source,
            correlation_id=correlation_id,
        )


@dataclass(frozen=True)
class EventEnvelope:
    meta: EventMeta
    type: str
    data: Dict[str, Any]

    def to_sse(self) -> str:
        """
        SSE format with `id:` so clients can resume using Last-Event-ID.
        """
        payload = json.dumps(
            {"meta": asdict(self.meta), "type": self.type, "data": self.data},
            ensure_ascii=False,
        )
        # NOTE: id line is important for resuming.
        return f"id: {self.meta.id}\nevent: {self.type}\ndata: {payload}\n\n"


# -----------------------------
# Pub/Sub Bus with history
# -----------------------------

class EventBus:
    """
    In-memory pub/sub with:
      - per-topic monotonic event ids
      - per-topic bounded history for replay
      - per-subscriber bounded queues (drop-oldest)
    Topics are strings like: "session:{id}" or "global".
    """

    def __init__(
        self,
        *,
        subscriber_queue_size: int = 256,
        history_size: int = 1024,
    ):
        self._subs: DefaultDict[str, List[asyncio.Queue[EventEnvelope]]] = defaultdict(list)
        self._seq: DefaultDict[str, int] = defaultdict(int)
        self._history: DefaultDict[str, Deque[EventEnvelope]] = defaultdict(lambda: deque(maxlen=history_size))

        self._subscriber_queue_size = int(subscriber_queue_size)
        self._history_size = int(history_size)

        # one lock for topology + id assignment consistency
        self._lock = asyncio.Lock()

    async def publish(
        self,
        topic: str,
        *,
        type: str,
        data: Dict[str, Any],
        source: str,
        correlation_id: Optional[str] = None,
        ts_ms: Optional[int] = None,
    ) -> EventEnvelope:
        """
        Publish a new event to topic.
        Assigns a monotonic ID per topic and fans out to subscribers.
        Returns the produced envelope.
        """
        async with self._lock:
            self._seq[topic] += 1
            eid = self._seq[topic]
            env = EventEnvelope(
                meta=EventMeta.new(
                    event_id=eid,
                    source=source,
                    correlation_id=correlation_id,
                    ts_ms=ts_ms,
                ),
                type=type,
                data=data,
            )

            # persist into in-memory history (bounded)
            self._history[topic].append(env)

            # snapshot queues while holding lock
            queues = list(self._subs.get(topic, []))

        # Fanout without holding lock
        for q in queues:
            self._put_drop_oldest(q, env)

        return env

    async def subscribe(
        self,
        topic: str,
        *,
        since_id: Optional[int] = None,
        replay: bool = True,
    ) -> "EventSubscription":
        """
        Create a subscription.
        If replay=True and since_id is provided, it will replay events with id > since_id
        from the in-memory history buffer (best effort).
        """
        q: asyncio.Queue[EventEnvelope] = asyncio.Queue(maxsize=self._subscriber_queue_size)

        # register
        async with self._lock:
            self._subs[topic].append(q)

            # compute replay snapshot under lock for ordering correctness
            replay_events: List[EventEnvelope] = []
            if replay and since_id is not None:
                replay_events = [e for e in self._history.get(topic, []) if int(e.meta.id) > int(since_id)]

        # enqueue replay outside lock
        for e in replay_events:
            self._put_drop_oldest(q, e)

        return EventSubscription(bus=self, topic=topic, queue=q)

    async def _unsubscribe(self, topic: str, queue: asyncio.Queue[EventEnvelope]) -> None:
        async with self._lock:
            if topic in self._subs:
                try:
                    self._subs[topic].remove(queue)
                except ValueError:
                    pass

    @staticmethod
    def _put_drop_oldest(q: asyncio.Queue[EventEnvelope], env: EventEnvelope) -> None:
        """
        Backpressure strategy:
          - if subscriber queue full => drop oldest => push newest
          - keeps UI responsive for streaming
        """
        if q.full():
            try:
                _ = q.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            q.put_nowait(env)
        except asyncio.QueueFull:
            # if still full, drop newest (rare)
            pass


class EventSubscription:
    """
    Public subscription API.
    You should NOT touch internal queue from outside.
    """

    def __init__(self, *, bus: EventBus, topic: str, queue: asyncio.Queue[EventEnvelope]):
        self._bus = bus
        self._topic = topic
        self._queue = queue
        self._closed = False

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._bus._unsubscribe(self._topic, self._queue)

    async def next(self, *, timeout: Optional[float] = None) -> Optional[EventEnvelope]:
        """
        Await the next event.
        Returns None on timeout.
        """
        if self._closed:
            return None
        try:
            if timeout is None:
                return await self._queue.get()
            return await asyncio.wait_for(self._queue.get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def events(self) -> AsyncIterator[EventEnvelope]:
        """
        Async iterator over events until cancelled/closed.
        """
        try:
            while not self._closed:
                env = await self._queue.get()
                yield env
        finally:
            await self.close()

    async def __aenter__(self) -> "EventSubscription":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()
