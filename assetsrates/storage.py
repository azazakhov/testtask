"""Provides any storage-related functional.

WARNING:
    Current implementation uses "dumpb" in-memory storage
    and does not provide any data persistence.
"""

import logging
from collections import defaultdict, deque
from decimal import Decimal
from typing import Final, NamedTuple

from .pubsub import publish


log: logging.Logger = logging.getLogger(__name__)


class Asset(NamedTuple):
    id: int
    name: str


class HistoryPoint(NamedTuple):
    """Asset's history point."""

    asset: Asset
    timestamp: int
    value: Decimal


# 30 minutes - new history point is created every second.
_ASSETS_HISTORY: Final[int] = 30 * 60
_STORAGE: dict[Asset, deque[HistoryPoint]] = defaultdict(
    lambda: deque(maxlen=_ASSETS_HISTORY)
)

_DEFAULT_ASETS = (
    Asset(1, "EURUSD"),
    Asset(2, "USDJPY"),
    Asset(3, "GBPUSD"),
    Asset(4, "AUDUSD"),
    Asset(5, "USDCAD"),
)

# create default assets
for _asset in _DEFAULT_ASETS:
    _STORAGE[_asset]


async def get_available_assets() -> list[Asset]:
    return list(_STORAGE.keys())


async def get_asset_by_id(id: int) -> Asset | None:
    for asset in await get_available_assets():
        if asset.id == id:
            return asset

    return None


async def save_points(points: list[HistoryPoint]) -> None:
    for point in points:
        log.debug('New history point for "%s" asset', point.asset.name)
        _STORAGE[point.asset].appendleft(point)
        publish(point.asset.name, point)


async def get_asset_history(asset: Asset) -> list[HistoryPoint]:
    return list(_STORAGE[asset])
