"""Websocket handler."""

import logging
from collections.abc import AsyncGenerator
from typing import Any, Final

from aiohttp.web import Request, WebSocketResponse

from . import json
from .storage import (
    Asset,
    Point,
    get_asset_by_id,
    get_asset_history,
    get_available_assets,
)


log: logging.Logger = logging.getLogger(__name__)


ACTION_ASSETS: Final[str] = "assets"
ACTION_SUBSCRIBE: Final[str] = "subscribe"


async def ws_handler(request: Request) -> WebSocketResponse:
    """Handle new websocket connections."""
    ws = WebSocketResponse()
    await ws.prepare(request)

    log.debug("New websocket connection")

    async for action, msg in aiter_ws_messages(ws):
        # TODO: add exceptions handler
        if action == ACTION_ASSETS:
            await assets_handler(ws)

        elif action == ACTION_SUBSCRIBE:
            await subscribe_handler(ws, msg)

    log.debug("Websocket connection closed")

    return ws


async def aiter_ws_messages(
    ws: WebSocketResponse,
) -> AsyncGenerator[tuple[str, dict[str, Any]], None]:
    """Yield pairs of "action" and "message" fields from income messages.

    Perform validation for "action" value and check type of "message" value
    without validation of "message" content.
    """
    while not ws.closed:
        try:
            raw_message = await ws.receive_json(loads=json.loads)
            yield validate_raw_message(raw_message)

        except (TypeError, ValueError):
            # TODO: ask what to do on invalid message
            continue


def validate_raw_message(raw: Any) -> tuple[str, dict[str, Any]]:
    """Return pair of "action" and "message" fields from income message.

    Perform validation for "action" value and check type of "message" value
    without validation of "message" content.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid message body type: {type(raw)}")

    action = raw.get("action")

    if action not in (ACTION_SUBSCRIBE, ACTION_ASSETS):
        raise ValueError(f"Invalid action: {action!r}")

    message = raw.get("message")

    if not isinstance(message, dict):
        raise ValueError(f"Invalid 'message' fileld type: {type(message)}")

    return action, message


async def send_ws_message(ws: WebSocketResponse, msg: dict[str, Any]) -> None:
    await ws.send_json(msg, dumps=json.dumps)


async def assets_handler(ws: WebSocketResponse) -> None:
    """Handle for "assets" action."""
    log.debug("Send available assets")
    assets = await get_available_assets()
    resp_message = build_assets_message(assets)
    await send_ws_message(ws, resp_message)


async def subscribe_handler(
    ws: WebSocketResponse,
    msg: dict[str, Any],
) -> None:
    """Handle for "subscribe" action."""
    asset: Asset | None
    asset_id = msg.get("assetId")

    if isinstance(asset_id, int):
        asset = await get_asset_by_id(asset_id)

    if asset is None:
        # TODO: ask what to do if asset not found (and asset_id is invalid)
        return

    log.debug("Send history for %s", asset.name)
    history_points = await get_asset_history(asset)
    resp_message = build_asset_history_message(history_points)
    await send_ws_message(ws, resp_message)

    # TODO: add subscription for new points


def build_assets_message(assets: list[Asset]) -> dict[str, Any]:
    """Return outcome message in response to "assets" action."""
    return {
        "action": "assets",
        "message": {
            "assets": [i._asdict() for i in assets],
        },
    }


def build_asset_history_message(points: list[Point]) -> dict[str, Any]:
    """Return outcome message in first response to "subscribe" action."""
    return {
        "action": "asset_history",
        "message": {
            "points": [serialize_point(i) for i in points],
        },
    }


def build_point_message(point: Point) -> dict[str, Any]:
    """Return outcome message with notifications about asset update."""
    return {
        "action": "point",
        "message": {
            "assetId": 1,
            "assetName": "EURUSD",
            "time": 1453556718,
            "value": 1.079755,
        },
    }


def serialize_point(point: Point) -> dict[str, Any]:
    return {
        "assetId": point.asset.id,
        "assetName": point.asset.name,
        "time": point.timestamp,
        "value": point.value,
    }
