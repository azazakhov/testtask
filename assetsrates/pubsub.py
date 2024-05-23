from __future__ import annotations

from asyncio import Queue
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import (
    asynccontextmanager,
)
from typing import Final

from .storage import HistoryPoint, subscription_manager


# TODO: Ask about queue maxsize for subscribers
SUBSCRIBER_QUEUE_MAXSIZE = 100


class ChannelsManager:
    __slots__ = ("_subscriptions",)

    _subscriptions: dict[str, set[Queue[HistoryPoint]]]

    def __init__(self) -> None:
        self._subscriptions = defaultdict(set)

    @asynccontextmanager
    async def subscribe(
        self,
        channel: str,
    ) -> AsyncGenerator[Queue[HistoryPoint], None]:
        subscription: Queue[HistoryPoint] = Queue(
            maxsize=SUBSCRIBER_QUEUE_MAXSIZE,
        )

        self._subscriptions[channel].add(subscription)

        try:
            async with subscription_manager.subscribe(
                channel,
                self.publish,
            ):
                yield subscription

        finally:
            self._subscriptions[channel].remove(subscription)

            if not self._subscriptions[channel]:
                del self._subscriptions[channel]

    def publish(self, channel: str, point: HistoryPoint) -> None:
        for subscription in self._subscriptions[channel]:
            # TODO: Ask what to do if queue is full
            if not subscription.full():
                subscription.put_nowait(point)


channels: Final[ChannelsManager] = ChannelsManager()
