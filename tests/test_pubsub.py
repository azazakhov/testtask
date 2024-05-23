import asyncio
from unittest.mock import AsyncMock, call, patch, sentinel

import pytest

from assetsrates.pubsub import channels


@pytest.mark.asyncio
@patch("assetsrates.pubsub.subscription_manager")
async def test_pubsub(subscription_manager_mock):
    subscription_manager_mock.subscribe.return_value = AsyncMock()

    async with (
        channels.subscribe("channel_A") as sub_a_1,
        channels.subscribe("channel_A") as sub_a_2,
        channels.subscribe("channel_B") as sub_b_1,
    ):
        # Channels are empty
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_1.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_2.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)

        # New messages to channel_A
        channels.publish("channel_A", sentinel.message_1)
        channels.publish("channel_A", sentinel.message_2)

        # channel_B is still empty
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)

        # Messages for different subscribers are equal
        msg_1 = await sub_a_1.get()
        msg_2 = await sub_a_2.get()
        assert msg_1 == msg_2 == sentinel.message_1

        msg_1 = await sub_a_1.get()
        msg_2 = await sub_a_2.get()
        assert msg_1 == msg_2 == sentinel.message_2

        # Channels are empty now
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_1.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_a_2.get(), 0.01)

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sub_b_1.get(), 0.01)

    # Check storage.subscription_manager calls
    assert subscription_manager_mock.subscribe.mock_calls == [
        call("channel_A", channels.publish),
        call().__aenter__(),
        call("channel_A", channels.publish),
        call().__aenter__(),
        call("channel_B", channels.publish),
        call().__aenter__(),
        call().__aexit__(None, None, None),
        call().__aexit__(None, None, None),
        call().__aexit__(None, None, None),
    ]
