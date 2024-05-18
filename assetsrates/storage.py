import logging
from collections import defaultdict, deque
from typing import Final, NamedTuple


log: logging.Logger = logging.getLogger(__name__)


class Asset(NamedTuple):
    id: int
    name: str


class Point(NamedTuple):
    asset: Asset
    # TODO: Ask about "timestamp" type - int or foat?
    timestamp: int
    # TODO: Ask about "value" type - foat of Decimal?
    value: float


# 30 minutes - new history point is created every second.
_ASSETS_HISTORY: Final[int] = 30 * 60
_STORAGE: dict[Asset, deque[Point]] = defaultdict(
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


async def save_points(points: list[Point]) -> None:
    for point in points:
        log.debug("New point for %s asset", point.asset.name)
        _STORAGE[point.asset].appendleft(point)


async def get_asset_history(asset: Asset) -> list[Point]:
    return list(_STORAGE[asset])
