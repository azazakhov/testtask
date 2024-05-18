import asyncio
from collections.abc import AsyncGenerator

from aiohttp.web import Application
from aiohttp.web import get as route_get

from . import ratescrawler, websockets


def create_app(argv: list[str]) -> Application:
    app = Application()
    app.cleanup_ctx.append(ratescrawler_task)
    app.add_routes([route_get("/", websockets.ws_handler)])
    return app


async def ratescrawler_task(app: Application) -> AsyncGenerator[None, None]:
    """Application startup/cleanup handler for running ratescrawler task."""
    app["ratescrawler_task"] = asyncio.create_task(ratescrawler.crawl())
    yield
