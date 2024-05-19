import asyncio
from unittest.mock import sentinel

import pytest

from assetsrates.pubsub import Subscription, publish


@pytest.mark.asyncio
async def test_pubsub():
    sub_a_1 = Subscription("channel_A")
    sub_a_2 = Subscription("channel_A")
    sub_b_1 = Subscription("channel_B")

    with sub_a_1, sub_a_2, sub_b_1:
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_1.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_2.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)

        publish("channel_A", sentinel.message_1)
        publish("channel_A", sentinel.message_2)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)

        msg_1 = await sub_a_1.get()
        msg_2 = await sub_a_2.get()

        assert msg_1 == msg_2 == sentinel.message_1

        msg_1 = await sub_a_1.get()
        msg_2 = await sub_a_2.get()

        assert msg_1 == msg_2 == sentinel.message_2

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_1.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_2.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)
