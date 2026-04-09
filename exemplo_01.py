from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel


broker = RedisBroker()
app = FastStream(broker)

class Event(BaseModel):
    id: int | None = None
    message: str


@broker.subscriber("topic_a")
async def handler_a(event_model: str):
    print(f'handler_a: {event_model}')
    await broker.publish(event_model, 'topic_b')



@broker.subscriber("topic_b")
async def handler_b(event_model: str):
    print(f'handler_b: {event_model}')

