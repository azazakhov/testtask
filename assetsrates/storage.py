"""Provides any storage-related functional."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator, Callable
from contextlib import (
    AbstractAsyncContextManager,
    asynccontextmanager,
    nullcontext,
)
from decimal import Decimal
from functools import partial
from typing import TYPE_CHECKING, Final, NamedTuple, TypeAlias

from asyncpg import Pool, Record
from asyncpg import create_pool as _create_pool
from asyncpg.pool import PoolConnectionProxy

from . import json


if TYPE_CHECKING:
    # ignore UP040:
    # Type alias uses `TypeAlias` annotation instead of the `type` keyword
    Connection: TypeAlias = PoolConnectionProxy[Record]  # noqa: UP040


log: logging.Logger = logging.getLogger(__name__)


class Asset(NamedTuple):
    id: int
    symbol: str


class HistoryPoint(NamedTuple):
    """Asset's history point."""

    asset: Asset
    timestamp: int
    value: Decimal


PG_URL: Final[str] = os.environ.get("PG_URL") or "postgres://postgres@postgres"
HISTORY_RANGE: Final[int] = 1800  # last 30 minutes


_connection_pool: Pool[Record] | None = None


@asynccontextmanager
async def create_pool() -> AsyncGenerator[Pool[Record], None]:
    global _connection_pool

    # TODO: hide credetials from logs
    log.debug("Connect to database: %s", PG_URL)

    try:
        try:
            _connection_pool = await _create_pool(PG_URL)

        except Exception as e:
            log.error("Could not connect to %s: %s", PG_URL, e)
            raise

        assert _connection_pool, "DB connection pool is not inited"
        yield _connection_pool

    finally:
        if _connection_pool is not None:
            await _connection_pool.close()

        _connection_pool = None
        log.debug("Connections to database are closed")


@asynccontextmanager
async def acquire_connection() -> AsyncGenerator[Connection, None]:
    assert _connection_pool, "DB connection pool is not inited"

    async with _connection_pool.acquire() as conn:
        yield conn


async def get_available_assets() -> list[Asset]:
    async with acquire_connection() as conn:
        records = await conn.fetch("SELECT id, symbol FROM assets;")

    return [Asset(**i) for i in records]


async def get_asset_by_id(id: int) -> Asset | None:
    async with acquire_connection() as conn:
        record = await conn.fetchrow(
            "SELECT id, symbol FROM assets WHERE id=$1;",
            id,
        )

    if record is not None:
        return Asset(**record)

    return None


async def save_points(points: list[HistoryPoint]) -> None:
    sql = """
        INSERT INTO history_points (asset_id, timestamp, value)
        VALUES ($1, to_timestamp($2), $3);
    """

    async with acquire_connection() as conn:
        for point in points:
            await conn.execute(
                sql,
                point.asset.id,
                point.timestamp,
                point.value,
            )

            await conn.execute(
                "SELECT pg_notify($1, $2);",
                point.asset.symbol,
                _dump_history_point(point),
            )

            log.debug('New history point for "%s" asset', point.asset.symbol)


async def get_asset_history(asset: Asset) -> list[HistoryPoint]:
    from_ts = time.time() - HISTORY_RANGE

    sql = """
        SELECT date_part('epoch', timestamp)::integer as timestamp, value
        FROM history_points
        WHERE asset_id=$1 AND timestamp>=to_timestamp($2);
    """

    async with acquire_connection() as conn:
        records = await conn.fetch(
            sql,
            asset.id,
            from_ts,
        )

    return [HistoryPoint(asset=asset, **i) for i in records]


class SubscriptionManager:
    __slots__ = (
        "_channels",
        "_connection",
    )

    _channels: set[str]
    _connection: Connection | None

    log = logging.getLogger(f"{__name__}.SubscriptionManager")

    def __init__(self) -> None:
        self._channels = set()
        self._connection = None

    @asynccontextmanager
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str, HistoryPoint], None],
    ) -> AsyncGenerator[None, None]:
        _callback = partial(self._subscribe_callback, callback=callback)
        new_channel = channel not in self._channels

        async with self._acquire() as conn:
            try:
                if new_channel:
                    self.log.debug("Subscribe to channel: %s", channel)
                    await conn.add_listener(channel, _callback)
                    self._channels.add(channel)

                yield

            finally:
                if new_channel:
                    await conn.remove_listener(channel, _callback)
                    self._channels.remove(channel)
                    self.log.debug("Unubscribe from channel: %s", channel)

    def _subscribe_callback(
        self,
        connection: Connection,
        pid: int,
        channel: str,
        payload: str,
        callback: Callable[[str, HistoryPoint], None],
    ) -> None:
        callback(channel, _load_history_point(payload))

    @asynccontextmanager
    async def _acquire(self) -> AsyncGenerator[Connection, None]:
        acquire_ctx: AbstractAsyncContextManager[Connection]
        reset_conn = False

        if self._connection is None:
            acquire_ctx = acquire_connection()
            reset_conn = True
            self.log.debug("Acquire connection")

        else:
            acquire_ctx = nullcontext(self._connection)

        try:
            async with acquire_ctx as self._connection:
                yield self._connection

        finally:
            if reset_conn:
                self._connection = None
                self.log.debug("Release connection")


subscription_manager: Final[SubscriptionManager] = SubscriptionManager()


def _dump_history_point(point: HistoryPoint) -> str:
    return json.dumps(
        (
            point.asset.id,
            point.asset.symbol,
            point.timestamp,
            str(point.value),
        ),
    )


def _load_history_point(payload: str) -> HistoryPoint:
    id, symbol, timestamp, value = json.loads(payload)
    return HistoryPoint(Asset(id, symbol), timestamp, Decimal(value))
