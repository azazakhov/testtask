from unittest.mock import patch

import pytest

from assetsrates.app import create_app


@pytest.fixture
def patch_rates_request():
    with patch("assetsrates.ratescrawler.make_request") as patched:
        patched.return_value = b"{}"
        yield patched


@pytest.fixture
def cli(patch_rates_request, event_loop, aiohttp_client):
    app = create_app()
    cli = event_loop.run_until_complete(aiohttp_client(app))

    yield cli

    event_loop.run_until_complete(cli.close())


@pytest.mark.asyncio
async def test_assetsrates(patch_rates_request, cli):
    async with cli.ws_connect("/") as ws:
        await ws.send_str('{"action":"assets","message":{}}')
        resp = await ws.receive_str()
        assert resp == (
            '{"action":"assets","message":{"assets":['
            '{"id":1,"name":"EURUSD"},'
            '{"id":2,"name":"USDJPY"},'
            '{"id":3,"name":"GBPUSD"},'
            '{"id":4,"name":"AUDUSD"},'
            '{"id":5,"name":"USDCAD"}]}}'
        )
