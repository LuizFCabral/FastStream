from asyncio import sleep
from faststream import FastStream, Logger
from faststream.redis import RedisBroker


broker = RedisBroker()
app = FastStream(broker)


@broker.subscriber("topic_a")
@broker.publisher("topic_b")
@broker.publisher("topic_c")
async def handler_a(message, logger: Logger):
    logger.warning('topic_a')
    await sleep(2)
    return message


@broker.subscriber("topic_b")
@broker.publisher("topic_c")
async def handler_b(message: str, logger: Logger):
    logger.warning('topic_b')
    await sleep(2)
    return message


@broker.subscriber("topic_c")
@broker.publisher("topic_a")
async def handler_c(message: str, logger: Logger):
    logger.warning('topic_c')
    await sleep(2)
    return message

