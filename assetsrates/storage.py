"""Provides any storage-related functional."""

from __future__ import annotations

import logging
import os
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Final, NamedTuple

from asyncpg import Pool, Record
from asyncpg import create_pool as _create_pool
from asyncpg.pool import PoolConnectionProxy

from .pubsub import publish


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

    try:
        try:
            _connection_pool = await _create_pool(PG_URL)

        except Exception as e:
            log.error("Could not connect to %s: %s", PG_URL, e)
            raise

        # ignore: Incompatible types in "yield"
        yield _connection_pool  # type: ignore[misc]

    finally:
        if _connection_pool is not None:
            await _connection_pool.close()

        _connection_pool = None


@asynccontextmanager
async def acquire_connection() -> (
    AsyncGenerator[PoolConnectionProxy[Record], None]
):
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
    async with acquire_connection() as conn:
        for point in points:
            await conn.execute(
                "INSERT INTO history_points (asset_id, timestamp, value) VALUES ($1, to_timestamp($2), $3);",
                point.asset.id,
                point.timestamp,
                point.value,
            )

            publish(point.asset.symbol, point)
            log.debug('New history point for "%s" asset', point.asset.symbol)


async def get_asset_history(asset: Asset) -> list[HistoryPoint]:
    from_ts = time.time() - HISTORY_RANGE

    async with acquire_connection() as conn:
        records = await conn.fetch(
            "SELECT timestamp, value FROM history_points WHERE asset_id=$1 AND timestamp>=to_timestamp($2);",
            asset.id,
            from_ts,
        )

    return [HistoryPoint(asset=asset, **i) for i in records]
