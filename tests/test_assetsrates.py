import asyncio
import json
from decimal import Decimal
from itertools import chain, repeat
from unittest.mock import patch

import pytest

from assetsrates import storage
from assetsrates.app import create_app


@pytest.fixture
def patch_rates_request():
    with patch("assetsrates.ratescrawler._make_request") as patched:
        patched.side_effect = repeat(b"{}")
        yield patched


@pytest.fixture
def cli(patch_rates_request, event_loop, aiohttp_client):
    app = create_app()
    cli = event_loop.run_until_complete(aiohttp_client(app))

    yield cli

    event_loop.run_until_complete(cli.close())


ASSETS_RESPONSE = {
    "action": "assets",
    "message": {
        "assets": [
            {"id": 1, "name": "EURUSD"},
            {"id": 2, "name": "USDJPY"},
            {"id": 3, "name": "GBPUSD"},
            {"id": 4, "name": "AUDUSD"},
            {"id": 5, "name": "USDCAD"},
        ]
    },
}

RATES_UPDATE_1 = {
    "Rates": [
        {
            "Symbol": "EURUSD",
            "Bid": 0.2,
            "Ask": 0.4,
        },
        {
            "Symbol": "USDJPY",
            "Bid": 2,
            "Ask": 4,
        },
    ]
}

RATES_UPDATE_2 = {
    "Rates": [
        {
            "Symbol": "EURUSD",
            "Bid": 0.4,
            "Ask": 0.5,
        },
        {
            "Symbol": "USDJPY",
            "Bid": 4,
            "Ask": 5,
        },
    ]
}

RATES_UPDATE_3 = {
    "Rates": [
        {
            "Symbol": "EURUSD",
            "Bid": 0.5,
            "Ask": 0.7,
        },
        {
            "Symbol": "USDJPY",
            "Bid": 5,
            "Ask": 7,
        },
    ]
}


@pytest.mark.asyncio
async def test_assetsrates(patch_rates_request, cli):
    async with cli.ws_connect("/") as ws:
        # No initial messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)

        # Get assets
        await ws.send_str(json.dumps({"action": "assets", "message": {}}))
        resp = json.loads(await ws.receive_str())
        assert resp == ASSETS_RESPONSE

        # No additional messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)

        # Subscribe for updates for asset_id=1
        await ws.send_str(
            json.dumps({"action": "subscribe", "message": {"assetId": 1}})
        )
        resp = json.loads(await ws.receive_str())
        assert resp == {"action": "asset_history", "message": {"points": []}}

        # Current history is empty for asset_id=1
        history = await storage.get_asset_history(storage.Asset(1, "EURUSD"))
        assert len(history) == 0

        # Patch response from rates external source - send first update
        patch_rates_request.side_effect = chain(
            [json.dumps(RATES_UPDATE_1).encode()],
            repeat(b"{}"),
        )

        # Wait for update
        resp = json.loads(await asyncio.wait_for(ws.receive_str(), 1.1))

        # No additional messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)

        # Now history has one entry
        history = await storage.get_asset_history(storage.Asset(1, "EURUSD"))
        assert len(history) == 1
        assert history[0].asset == storage.Asset(1, "EURUSD")
        assert history[0].timestamp
        assert history[0].value == Decimal("0.3")

        # Сheck notification message
        assert resp == {
            "action": "point",
            "message": {
                "assetId": 1,
                "assetName": "EURUSD",
                "time": history[0].timestamp,
                "value": 0.3,
            },
        }

        # Get assets - ws still responds on requests.
        await ws.send_str(json.dumps({"action": "assets", "message": {}}))
        resp = json.loads(await ws.receive_str())
        assert resp == ASSETS_RESPONSE

        # No additional messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)

        # Patch response from rates external source - send second update
        patch_rates_request.side_effect = chain(
            [json.dumps(RATES_UPDATE_2).encode()],
            repeat(b"{}"),
        )

        # Wait for update
        resp = json.loads(await asyncio.wait_for(ws.receive_str(), 1.1))

        # Two entry in history data
        history = await storage.get_asset_history(storage.Asset(1, "EURUSD"))
        assert len(history) == 2
        assert history[0].asset == storage.Asset(1, "EURUSD")
        assert history[0].timestamp
        assert history[0].value == Decimal("0.45")

        # Сheck notification message
        assert resp == {
            "action": "point",
            "message": {
                "assetId": 1,
                "assetName": "EURUSD",
                "time": history[0].timestamp,
                "value": 0.45,
            },
        }

        # Two entry in history data for asset_id=2
        history = await storage.get_asset_history(storage.Asset(2, "USDJPY"))
        assert len(history) == 2

        # Subscribe to another asset
        await ws.send_str(
            json.dumps({"action": "subscribe", "message": {"assetId": 2}})
        )

        resp = json.loads(await ws.receive_str())
        assert resp == {
            "action": "asset_history",
            "message": {
                "points": [
                    {
                        "assetId": 2,
                        "assetName": "USDJPY",
                        "time": history[0].timestamp,
                        "value": 4.5,
                    },
                    {
                        "assetId": 2,
                        "assetName": "USDJPY",
                        "time": history[1].timestamp,
                        "value": 3.0,
                    },
                ]
            },
        }

        # No additional messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)

        # Patch response from rates external source - send third update
        patch_rates_request.side_effect = chain(
            [json.dumps(RATES_UPDATE_3).encode()],
            repeat(b"{}"),
        )

        # Wait for update
        resp = json.loads(await asyncio.wait_for(ws.receive_str(), 1.1))

        # Three entry in history data for asset_id=2
        history = await storage.get_asset_history(storage.Asset(2, "USDJPY"))
        assert len(history) == 3

        # Check notification message
        assert resp == {
            "action": "point",
            "message": {
                "assetId": 2,
                "assetName": "USDJPY",
                "time": history[0].timestamp,
                "value": 6.0,
            },
        }

        # No additional messages
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws.receive_str(), 0.01)
