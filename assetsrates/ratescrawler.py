import asyncio
import logging
import os
import time
from typing import Any, Final

from aiohttp import ClientError, ClientSession

from . import json
from .storage import Asset, Point, get_available_assets, save_points


log = logging.getLogger(__name__)


RATES_URL: Final[str] = os.environ.get("RATES_URL") or ""
assert RATES_URL, "RATES_URL env var is not set"


async def crawl() -> None:
    if not RATES_URL:
        log.error("RATES_URL env var is not set, ratecrawler is not started")
        return

    log.info("Start ratecrawler task")
    async with ClientSession() as session:
        while True:
            try:
                ts = time.time()

                raw_data = await make_request(session, RATES_URL)
                assets = await get_available_assets()
                points = parse_raw(raw_data, int(ts), assets)

                if points:
                    await save_points(points)

                await asyncio.sleep(ts - time.time() + 1)

            except ClientError:
                log.exception("Error in request %s:", RATES_URL)

            except asyncio.CancelledError:
                break

            except Exception:
                log.exception("Unexpected exception:")

    log.info("Finish ratecrawler task")


async def make_request(session: ClientSession, url: str) -> bytes:
    log.debug("New request to %s", RATES_URL)
    async with session.get(RATES_URL) as resp:
        resp.raise_for_status()
        return await resp.read()


def parse_raw(raw: bytes, ts: int, assets: list[Asset]) -> list[Point]:
    """Parse raw response bytes to Points list and return it."""
    # TODO: add errors handling

    raw_json = raw.strip().removeprefix(b"null(").removesuffix(b");")
    data: dict[str, list[dict[str, Any]]] = json.loads(raw_json)
    rates = data.get("Rates", [])

    result: list[Point] = []

    symbol_to_asset = {i.name: i for i in assets}

    for rate in rates:
        symbol = rate.get("Symbol")

        if symbol in symbol_to_asset:
            bid: float = rate.get("Bid") or 0.0
            ask: float = rate.get("Ask") or 0.0
            value = (bid + ask) / 2

            point = Point(
                asset=symbol_to_asset[symbol],
                timestamp=ts,
                value=value,
            )

            result.append(point)

    return result
