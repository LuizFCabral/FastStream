"""FastStream/Redis chat backend — GUI-agnostic.

This module owns all the messaging concerns:
  * It spins up an asyncio loop in a background thread.
  * It opens a single ``RedisBroker`` connection.
  * It subscribes to the channel dedicated to the local user.
  * It publishes messages to other users' channels.
  * It exposes incoming messages through a thread-safe ``queue.Queue`` so the
    GUI layer (or any other consumer) can pick them up without needing to
    know anything about asyncio or FastStream.

The GUI never imports this module's dependencies — it only uses the public
``ChatBackend`` class.
"""

from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass


# Third-party — kept at module top so import errors surface at startup.
from faststream.redis import RedisBroker


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class ChatMessage:
    """A single chat message travelling through the system."""

    sender: str
    text: str

    def format(self) -> str:
        return f"{self.sender}: {self.text}"


# ---------------------------------------------------------------------------
# Channel naming convention
# ---------------------------------------------------------------------------


def channel_for(recipient: str) -> str:
    """Return the Redis channel name used to deliver messages to ``recipient``.

    Keeping a simple ``chat:to:<user>`` convention makes it trivial to add
    new users, debug with ``redis-cli``, and reason about routing.
    """
    return f"chat:to:{recipient}"


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------


class ChatBackend:
    """Bridge between a Redis broker (FastStream) and a thread-safe queue.

    Lifecycle::

        backend = ChatBackend(user="alice")
        backend.start()             # spawns the background thread
        ...
        backend.send("bob", "hi")   # non-blocking, schedules a publish
        ...
        for msg in backend.messages: # poll from the GUI thread
            ...

    The class is intentionally minimal: it knows nothing about Tkinter, and
    nothing about notifications. The GUI layer is responsible for both.
    """

    # Payload format on the wire: "<sender>::<text>".
    _SEPARATOR = "::"

    def __init__(self, user: str) -> None:
        self.user = user
        # The GUI drains this queue periodically with ``get_nowait``.
        self.messages: "queue.Queue[ChatMessage]" = queue.Queue()
        self.broker = RedisBroker()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._ready = threading.Event()

    # -- lifecycle --------------------------------------------------------

    def start(self) -> None:
        """Start the background asyncio loop. Returns once subscribers are
        registered and the connection is open."""
        t = threading.Thread(target=self._run_loop, name="chat-backend", daemon=True)
        t.start()
        # Bound the wait so a missing Redis doesn't hang the GUI forever.
        if not self._ready.wait(timeout=5):
            raise RuntimeError(
                "ChatBackend did not become ready within 5s. Is Redis running?"
            )

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        @self.broker.subscriber(channel_for(self.user))
        async def _on_message(raw: str) -> None:
            if self._SEPARATOR not in raw:
                return
            sender, text = raw.split(self._SEPARATOR, 1)
            self.messages.put(ChatMessage(sender=sender, text=text))

        async def _main() -> None:
            await self.broker.start()
            self._ready.set()
            # Park forever; the broker keeps receiving in the background.
            await asyncio.Event().wait()

        try:
            self._loop.run_until_complete(_main())
        except Exception as exc:  # noqa: BLE001
            self.messages.put(
                ChatMessage(sender="system", text=f"Backend error: {exc}")
            )

    # -- publishing -------------------------------------------------------

    def send(self, recipient: str, text: str) -> None:
        """Publish ``text`` to ``recipient``. Safe to call from any thread."""
        if self._loop is None:
            return
        payload = f"{self.user}{self._SEPARATOR}{text}"
        asyncio.run_coroutine_threadsafe(
            self.broker.publish(payload, channel_for(recipient)),
            self._loop,
        )
