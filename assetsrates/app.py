import asyncio
from collections.abc import AsyncGenerator

from aiohttp.web import Application
from aiohttp.web import get as route_get

from . import ratescrawler, storage, websockets


def create_app(argv: list[str] | None = None) -> Application:
    """Create new aiohttp app.

    Args:
        argv: does nothing. Needs only for compability with aiohttp.web script.
    """

    app = Application()
    app.cleanup_ctx.append(init_db)
    app.cleanup_ctx.append(ratescrawler_task)
    app.add_routes([route_get("/", websockets.ws_handler)])
    return app


async def init_db(app: Application) -> AsyncGenerator[None, None]:
    """Application startup/cleanup handler for DB connection initialization."""
    async with storage.create_pool() as db_pool:
        app["db_pool"] = db_pool
        yield


async def ratescrawler_task(app: Application) -> AsyncGenerator[None, None]:
    """Application startup/cleanup handler for running ratescrawler task."""
    app["ratescrawler_task"] = asyncio.create_task(ratescrawler.crawl())

    yield

    app["ratescrawler_task"].cancel()
    await app["ratescrawler_task"]
