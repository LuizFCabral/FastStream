import pytest
from faststream.redis import TestRedisBroker
from exemplo_00 import handler, broker

@pytest.mark.asyncio
async def test_handler():
    assert await handler('teste') == 'teste'

@pytest.mark.asyncio
async def test_handler_integration():
    async with TestRedisBroker(broker) as br:
        response = await br.request("mensagem teste", channel="test")
        assert response.body.decode() == "mensagem teste"