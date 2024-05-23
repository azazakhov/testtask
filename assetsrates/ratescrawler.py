import asyncio
import logging
import os
import time
from decimal import Decimal
from typing import Any, Final

from aiohttp import ClientError, ClientSession

from . import json
from .storage import Asset, HistoryPoint, get_available_assets, save_points


log = logging.getLogger(__name__)


RATES_URL: Final[str] = os.environ.get("RATES_URL") or ""
assert RATES_URL, "RATES_URL env var is not set"

REQUEST_PERIOD: Final[int] = 1


async def crawl() -> None:
    if not RATES_URL:
        log.error("RATES_URL env var is not set, ratescrawler is not started")
        return

    log.info("Start ratescrawler task")

    try:
        async with ClientSession() as session:
            while True:
                ts = time.time()

                try:
                    log.debug("New request to %s", RATES_URL)
                    raw_data = await _make_request(session, RATES_URL)
                    assets = await get_available_assets()
                    points = parse_raw(raw_data, int(ts), assets)

                    if points:
                        await save_points(points)

                except ClientError:
                    log.exception("Error in request %s:", RATES_URL)

                except Exception:
                    log.exception("Unexpected exception:")

                sleep_time = ts - time.time() + REQUEST_PERIOD
                log.debug("Sleep for %f", sleep_time)
                await asyncio.sleep(sleep_time)

    except asyncio.CancelledError:
        pass

    log.info("Finish ratescrawler task")


def parse_raw(raw: bytes, ts: int, assets: list[Asset]) -> list[HistoryPoint]:
    """Parse raw response bytes to Points list and return it."""
    # TODO: add validation and errors handling

    raw_json = raw.strip().removeprefix(b"null(").removesuffix(b");")
    data: dict[str, list[dict[str, Any]]] = json.loads(raw_json)
    rates = data.get("Rates", [])

    result: list[HistoryPoint] = []

    symbol_to_asset = {i.symbol: i for i in assets}

    for rate in rates:
        symbol = rate.get("Symbol")

        if symbol in symbol_to_asset:
            # TODO: check Bid and Ask valies before converting to Decimal
            bid = Decimal(str(rate.get("Bid") or 0.0))
            ask = Decimal(str(rate.get("Ask") or 0.0))
            value = (bid + ask) / 2

            point = HistoryPoint(
                asset=symbol_to_asset[symbol],
                timestamp=ts,
                value=value,
            )

            result.append(point)

    return result


async def _make_request(session: ClientSession, url: str) -> bytes:
    async with session.get(url) as resp:
        resp.raise_for_status()
        return await resp.read()
