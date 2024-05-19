from __future__ import annotations

import asyncio
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING, Any, Self


if TYPE_CHECKING:
    from .storage import HistoryPoint


def publish(channel: str, msg: HistoryPoint) -> None:
    _get_channel(channel).publish(msg)


class Subscription(AbstractContextManager["Subscription"]):
    __slots__ = (
        "_channel",
        "_queue",
    )

    _channel: _Channel
    _queue: asyncio.Queue[HistoryPoint]

    def __init__(self, channel: str) -> None:
        # TODO: Ask about queue maxsize for subscribers
        self._queue = asyncio.Queue(maxsize=100)
        self._channel = _get_channel(channel)

    def __enter__(self) -> Self:
        self._channel.subscribe(self)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self._channel.unsubscribe(self)

    def put(self, msg: HistoryPoint) -> None:
        # TODO: Ask what to do if queue is full
        if not self._queue.full():
            self._queue.put_nowait(msg)

    async def get(self) -> HistoryPoint:
        return await self._queue.get()


_CHANNELS: dict[str, _Channel] = {}


class _Channel:
    __slots__ = (
        "_name",
        "_subscribers",
    )

    _name: str
    _subscribers: set[Subscription]

    def __init__(self, name: str) -> None:
        self._name = name
        self._subscribers = set()

    def subscribe(self, subscriber: Subscription) -> None:
        self._subscribers.add(subscriber)

    def unsubscribe(self, subscriber: Subscription) -> None:
        self._subscribers.remove(subscriber)

    def publish(self, msg: HistoryPoint) -> None:
        for subscriber in self._subscribers:
            subscriber.put(msg)


def _get_channel(name: str) -> _Channel:
    if name not in _CHANNELS:
        _CHANNELS[name] = _Channel(name)

    return _CHANNELS[name]
