from faststream import FastStream
from faststream.redis import RedisBroker
from pydantic import BaseModel


broker = RedisBroker()
app = FastStream(broker)

class Event(BaseModel):
    id: int | None = None
    message: str



@broker.subscriber("test")
async def handler(trace_id: int, message: Event):
    print(message)
    return message

