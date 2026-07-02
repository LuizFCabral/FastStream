# FastStream — Examples with Redis

This repository contains practical, hands-on examples of using [FastStream](https://faststream.airt.ai/) with **Redis** as the message broker. The examples are intentionally small and focused, designed to teach — file by file — the core mechanics of building asynchronous, event-driven services with FastStream.

---

## 📋 Table of Contents

1. [What is FastStream?](#-what-is-faststream)
2. [What is Redis and why use it as a broker?](#-what-is-redis-and-why-use-it-as-a-broker)
3. [Requirements](#-requirements)
4. [Project Structure](#-project-structure)
5. [Installation](#-installation)
6. [Running Redis](#-running-redis)
7. [How to Run the Examples](#-how-to-run-the-examples)
   - [`exemplo_00.py` — Basic subscriber with Pydantic](#exemplo_00py--basic-subscriber-with-pydantic)
   - [`exemplo_01.py` — Chaining messages between topics](#exemplo_01py--chaining-messages-between-topics)
   - [`exemplo_02.py` — Multiple publishers and subscribers (cycle)](#exemplo_02py--multiple-publishers-and-subscribers-cycle)
8. [Running the Tests](#-running-the-tests)
9. [Deep Dive: How FastStream Works](#-deep-dive-how-faststream-works)
10. [Deep Dive: How Redis Pub/Sub Works in This Project](#-deep-dive-how-redis-pubsub-works-in-this-project)
11. [Useful Commands](#-useful-commands)
12. [Additional Resources](#-additional-resources)

---

## 💡 What is FastStream?

[FastStream](https://faststream.airt.ai/) is a modern Python framework, built on top of [`asyncio`](https://docs.python.org/3/library/asyncio.html), for producing services that **produce, consume, and process messages** through a message broker. It is the spiritual successor of [`propan`](https://github.com/lancetnik/propan) and is maintained by the same team.

FastStream is designed to feel as natural as writing a regular Python function, while hiding all the complexity of broker protocols, connection management, retries, and serialization behind clean, declarative decorators.

### Core mental model

FastStream's mental model is built around three concepts:

| Concept | What it is | Example in this repo |
| --- | --- | --- |
| **Broker** | The transport layer that talks to Redis/Kafka/etc. | `RedisBroker()` |
| **Subscriber** | An async function that consumes messages from a channel/topic. | `@broker.subscriber("test")` |
| **Publisher** | Something that sends messages to a channel/topic. | `@broker.publisher("topic_b")` or `broker.publish(...)` |

The `FastStream` application object (e.g. `app = FastStream(broker)`) is the **runtime container** that ties everything together: it knows the broker, the subscribers, the publishers, and is what you actually launch with the CLI.

---

## 🧠 What is Redis and why use it as a broker?

[Redis](https://redis.io/) (Remote Dictionary Server) is an **in-memory data store**, widely used as a cache, a database, and — relevant to this project — as a **lightweight message broker** via its built-in **Pub/Sub** mechanism.

### What is Redis Pub/Sub?

Redis Pub/Sub is a fire-and-forget messaging model. Three actors are involved:

- **Publisher** — sends a message to a *channel* (a named string, e.g. `"test"`, `"topic_a"`).
- **Subscriber** — listens on one or more channels and receives every message published to them.
- **Channel** — a routing key. Subscribers on `"topic_a"` only see messages published to `"topic_a"`.

In Redis Pub/Sub:

- Messages are **not persisted**. If no subscriber is connected when a message is published, the message is lost.
- Delivery is **at-most-once**. There are no acknowledgements, no retries, no dead-letter queue.
- It is **extremely fast** because everything happens in memory.

### Why use Redis as a broker for learning?

- **Zero ceremony.** No topics to create, no partitions, no consumer groups. You `PUBLISH` and `SUBSCRIBE` and that's it.
- **Easy to inspect.** With `redis-cli`, you can manually publish messages and watch the handlers react.
- **Lightweight.** Perfect for prototypes, demos, and small services.

### How FastStream talks to Redis

When you write:

```python
from faststream.redis import RedisBroker
broker = RedisBroker()
```

FastStream opens a single TCP connection to `redis://localhost:6379` (by default) and:

- Subscribes handlers to the channels you declared with `@broker.subscriber(...)`.
- Uses the same connection to publish, reusing it across handlers.

You never touch the Redis client directly — FastStream does it for you.

---

## ✅ Requirements

- **Python 3.10+** — the code uses the `int | None` PEP 604 union syntax, which requires Python 3.10 or higher.
- **Redis 5+** running locally (default: `redis://localhost:6379`).
- **pip** for installing dependencies.
- (Optional) **Docker** to run Redis in a container.

---

## 📁 Project Structure

```
FastStream/
├── exemplo_00.py        # Basic example: subscriber with Pydantic validation
├── exemplo_01.py        # Chaining: handler_a → topic_b → handler_b
├── exemplo_02.py        # Cycle: topic_a → topic_b → topic_c → topic_a
├── chat_backend.py      # FastStream/Redis backend (GUI-agnostic)
├── chat_gui.py          # Tkinter chat window (no FastStream imports)
├── chat_controller.py   # Tray icon + in-app notification popup + unread counter
├── chat.py              # CLI entry point: `python chat.py alice|bob`
├── test.py              # Tests with TestRedisBroker
├── .gitignore           # Files ignored by Git
└── README.md            # This file
```

---

## 🚀 Installation

### 1. (Optional) Clone the repository

```bash
git clone <repository-url>
cd FastStream
```

### 2. Create a virtual environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

### 3. Install the dependencies

```bash
pip install "faststream[redis]" pytest pytest-asyncio
```

This installs:

- `faststream[redis]` — the framework with the Redis broker.
- `pytest` and `pytest-asyncio` — required to run `test.py`.

---

## 🔴 Running Redis

You need a running Redis instance. Pick one of the options below.

### Option A: Docker (recommended)

```bash
docker run --name redis-faststream -p 6379:6379 -d redis
```

To stop it:
```bash
docker stop redis-faststream
```

To start it again later:
```bash
docker start redis-faststream
```

### Option B: Native installation

Follow the [official Redis installation guide](https://redis.io/docs/getting-started/installation/) for your OS, then start the server:

```bash
redis-server
```

### Verify that Redis is alive

```bash
redis-cli ping
```

Expected response: `PONG`.

---

## ▶️ How to Run the Examples

Every example file exposes an `app` object. The standard way to start a FastStream service is:

```bash
faststream run <module>:<app>
```

For example:

```bash
faststream run exemplo_00:app
```

This reads the `app` instance, opens the broker connection, registers all `@broker.subscriber` callbacks, and waits for messages.

> 💡 **Tip:** The `faststream` CLI is installed as part of the `faststream` package. Make sure your virtual environment is activated.

---

### `exemplo_00.py` — Basic subscriber with Pydantic

```bash
faststream run exemplo_00:app
```

**What it does:**

1. Creates a `RedisBroker` (the transport).
2. Creates the `FastStream` application bound to that broker.
3. Defines a Pydantic model `Event` with two fields: `id` (optional `int`) and `message` (`str`).
4. Registers `handler` on the `test` channel.

**The handler signature is key to understand:**

```python
@broker.subscriber("test")
async def handler(trace_id: int, message: Event):
    print(message)
    return message
```

- `trace_id: int` — FastStream looks for a **header** named `trace_id` in the Redis message; if present and parseable as `int`, it is injected as a function argument. If you do not send it, the call will fail.
- `message: Event` — the message body is **automatically deserialized from JSON** and validated against the `Event` Pydantic model. If the payload is invalid, FastStream raises an error before calling the handler.
- The `return message` is significant: returning a value from a handler makes it FastStream's responsibility to send that value somewhere — but since no `@broker.publisher` is applied here, the return value is effectively ignored (in this example).

**How to test it:**

In another terminal, publish a JSON message to the `test` channel:

```bash
redis-cli publish test '{"id": 1, "message": "Hello, FastStream!"}'
```

In the running application's logs, you should see `message='Hello, FastStream!' id=1` printed.

**Test edge cases:**

- Try publishing a malformed JSON: the handler will not be called; FastStream logs a decoding error.
- Try publishing an `Event` with the wrong type (e.g. `message` as a number): Pydantic validation fails before the handler runs.

---

### `exemplo_01.py` — Chaining messages between topics

```bash
faststream run exemplo_01:app
```

**What it does:**

This example demonstrates **manual publishing** to chain two handlers:

- `handler_a` subscribes to `topic_a`, prints the message, then **explicitly republishes** the same message to `topic_b` using `await broker.publish(...)`.
- `handler_b` subscribes to `topic_b` and prints whatever it receives.

This is a **pipeline** (or a *fan-out* of 1): a message enters `topic_a`, gets transformed/inspected by `handler_a`, and is forwarded to `topic_b` where `handler_b` processes it.

**How to test it:**

```bash
redis-cli publish topic_a "first message"
```

Expected output (in the application logs):

```
handler_a: first message
handler_b: first message
```

**What the line `await broker.publish(event_model, 'topic_b')` does:**

- It tells the broker: "Send this message to the `topic_b` channel."
- The broker reuses its connection, calls Redis `PUBLISH topic_b <message>`, and Redis delivers it to every subscriber on `topic_b` — which, in this case, is `handler_b`.

**Why use this pattern?**

In real systems, you would split work across topics to:

- **Decouple services** — `handler_a` and `handler_b` can be deployed and scaled independently.
- **Parallelize** — multiple subscribers on the same topic can process messages in parallel.
- **Organize** — different topics represent different kinds of events (e.g. `user.created`, `order.paid`).

---

### `exemplo_02.py` — Multiple publishers and subscribers (cycle)

```bash
faststream run exemplo_02:app
```

**What it does:**

This example uses the `@broker.publisher` **decorator** (instead of manual `broker.publish`) to make handlers return-driven. The flow is:

- **`handler_a`** — subscribes to `topic_a`, **publishes to `topic_b` AND `topic_c`**, logs a warning, sleeps 2 seconds, and returns the message. Because of the two `@broker.publisher` decorators, the *return value* is automatically sent to both `topic_b` and `topic_c`.
- **`handler_b`** — subscribes to `topic_b`, publishes to `topic_c`, sleeps 2 seconds, and returns the message.
- **`handler_c`** — subscribes to `topic_c`, publishes to `topic_a`, sleeps 2 seconds, and returns the message.

**Important: this is a cycle.** Once you publish a message to `topic_a`, it will keep circulating:

```
topic_a → topic_b → topic_c → topic_a → topic_b → ...
```

**How to test it:**

```bash
redis-cli publish topic_a "start the cycle"
```

You will see a repeating log pattern:

```
topic_a
topic_b
topic_c
topic_a
...
```

**Stop the cycle** with `Ctrl+C` in the terminal running the application.

> ⚠️ **This is a teaching example, not a production pattern.** Cycles like this are exactly how you accidentally create infinite loops. In real code, you would either remove the publisher from one of the handlers (breaking the cycle) or use a counter/TTL to bound the number of hops.

**What the decorators do, line by line:**

```python
@broker.subscriber("topic_a")   # listens on topic_a
@broker.publisher("topic_b")    # sends the return value to topic_b
@broker.publisher("topic_c")    # sends the return value to topic_c
async def handler_a(message, logger: Logger):
    ...
    return message
```

When multiple decorators are stacked, they apply **bottom-up**: the function is first wrapped by the innermost decorator, then the next one, and so on. FastStream handles this correctly: the message is delivered to **all** declared publishers.

The injected `logger: Logger` is FastStream's built-in logger, pre-configured with the service context — use it instead of `print` for production code.

---

## 💬 Chat Interface (Two Windows over Redis)

A small Tkinter chat that lets two users exchange messages through FastStream/Redis. The interface, the messaging layer, and the notification/tray logic are kept in separate files so each layer can be reasoned about (and tested) in isolation.

### Files

| File | Responsibility |
| --- | --- |
| `chat_backend.py` | Owns the `RedisBroker`, the asyncio loop, and a thread-safe `queue.Queue` of incoming messages. Exposes a tiny API: `start()`, `send(recipient, text)`, `messages`. |
| `chat_gui.py` | Tkinter window (pure GUI). Calls `backend.send(...)` on user input, polls `backend.messages` to render incoming lines, tracks sent/received counters, and exposes `show()` / `withdraw()` lifecycle hooks. **No FastStream/Redis imports.** |
| `chat_controller.py` | Owns the **system tray icon** and the **in-app notification popup**. Keeps an unread counter that grows while the window is hidden and resets when the window is shown. The popup itself grows in size with the unread count. |
| `chat.py` | CLI entry point. Wires a `ChatBackend` to a `ChatWindow` via a `ChatController`, then runs the Tkinter main loop. |

### Install the GUI dependencies

```bash
pip install plyer pystray Pillow
```

- `plyer` — cross-platform desktop notifications (imported lazily; the GUI still works without it).
- `pystray` + `Pillow` — system tray icon with Show / Quit menu (also imported lazily).

### Run two windows

Open two terminals, activate the venv in each, and run:

**Terminal 1:**
```bash
python chat.py alice
```

**Terminal 2:**
```bash
python chat.py bob
```

A window titled `Chat — alice` opens in the first terminal and `Chat — bob` in the second. Each window shows a counter in the top-right corner: `Sent: 0   Received: 0`. Type a message in one window, press Enter, and it appears in the other window.

### Hide, unread counter, and growing popup

Clicking the window's close button (the `×`) **hides** the window instead of quitting. The application keeps running in the background, with the **tray icon** as the entry point. To exit, right-click the tray icon and choose **Quit**.

- While the window is hidden, every incoming message increments an **unread counter**.
- A dark in-app **notification popup** slides into the bottom-right corner of the screen. Its width grows as more unread messages accumulate (capped so it never exceeds the screen width).
- The window's **title bar** also shows the unread count: `Chat — bob (3 unread)`.
- Showing the window (via the tray's "Show" entry, or by clicking the popup) **resets the unread counter** and dismisses the popup.

```
   ┌─────────────────┐                       ┌─────────────────┐
   │   chat_gui.py   │   backend.send(...)   │ chat_backend.py │
   │   (Tk thread)   │ ────────────────────▶ │  (asyncio thr.) │
   │                 │                       │                 │
   │   _drain ───────┼──────────────────────▶│  RedisBroker    │
   │      │          │      queue.Queue      │                 │
   │      ▼          │                       └────────┬────────┘
   │   ChatWindow    │                                │
   │   (with hooks)  │                                ▼
   └────────┬────────┘                          ┌──────────┐
            │ hooks: _on_incoming, _on_focus    │  Redis   │
            ▼                                   └──────────┘
   ┌─────────────────┐
   │chat_controller.py│  owns tray icon, unread counter,
   │                 │  in-app notification popup
   └─────────────────┘
```

- The GUI thread is the Tkinter main loop. It never touches asyncio.
- The backend thread runs its own asyncio event loop and a single `RedisBroker` connection.
- The controller and the window communicate through two simple hooks: `window._on_incoming(msg)` and `window._on_focus()`. The window does not know a controller exists; the controller is plugged in by the CLI.
- Each user has a dedicated Redis channel: `chat:to:alice` and `chat:to:bob`. The wire format is `"<sender>::<text>"` — simple, easy to inspect with `redis-cli`.

### Try it from the command line too

You can also poke the system from outside the GUI. In a third terminal:

```bash
redis-cli publish chat:to:bob 'cli::hello from redis-cli'
```

You will see `bob: hello from redis-cli` appear in Bob's window. If Bob's window is hidden at the moment, the unread counter goes up and the popup grows accordingly.

---

## 🧪 Running the Tests

```bash
pytest test.py -v
```

The `test.py` file contains two tests for `exemplo_00.py` that use `TestRedisBroker` — an **in-memory replacement** for the real Redis broker. No running Redis instance is required for the tests.

- **`test_handler`** — calls the `handler` function directly (without the broker), passing `'teste'` as the positional argument. Notice that the handler's first parameter is `trace_id: int` in `exemplo_00.py`, so calling `handler('teste')` passes the string as `trace_id` — this test will actually fail under strict Pydantic validation. In a real project, the test would be:

  ```python
  assert await handler(trace_id=1, message=Event(message="teste")) == Event(message="teste")
  ```

  The current test as written is illustrative — it shows that handlers are just async functions and can be called directly.

- **`test_handler_integration`** — uses `TestRedisBroker` as an async context manager. Inside the `async with` block, the real `broker` is replaced with an in-memory broker, so messages do not actually go through Redis. The test publishes a message with `br.request(...)` (which publishes and waits for a response, similar to a request/Reply pattern) on the `test` channel, and asserts the response matches.

  Note: the original handler in `exemplo_00.py` only **returns** the message; it does not publish a response. The test as written would only pass if you adapted the handler to use `@broker.publisher` or a manual `broker.publish`. Treat it as a starting point.

**Why use `TestRedisBroker`?**

- Tests are **deterministic** and **fast** — no network, no broker.
- You can test **integration flows** (publish → handler → response) without standing up infrastructure.
- The same code can be tested in CI without a Redis sidecar.

---

## 🛠️ Useful Commands

| Command | Description |
| --- | --- |
| `faststream run exemplo_00:app` | Runs example 00 |
| `faststream run exemplo_01:app` | Runs example 01 |
| `faststream run exemplo_02:app` | Runs example 02 |
| `python chat.py alice` | Opens Alice's chat window |
| `python chat.py bob` | Opens Bob's chat window |
| `pytest test.py -v` | Runs the tests with verbose output |
| `redis-cli ping` | Checks if Redis is alive |
| `redis-cli publish <channel> "<message>"` | Publishes a message to a channel |
| `redis-cli subscribe <channel>` | Subscribes interactively to a channel |
| `redis-cli monitor` | Streams all commands Redis receives |

---

## 📚 Additional Resources

- [FastStream Official Documentation](https://faststream.airt.ai/)
- [FastStream — Redis broker](https://faststream.airt.ai/latest/redis/)
- [FastStream on GitHub](https://github.com/airtai/faststream)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Redis Documentation](https://redis.io/docs/)
- [Redis Pub/Sub explained](https://redis.io/docs/manual/pubsub/)
- [AsyncAPI Specification](https://www.asyncapi.com/)
