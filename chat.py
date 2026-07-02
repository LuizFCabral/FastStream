"""CLI entry point for the chat.

Run two instances in separate terminals::

    python chat.py alice
    python chat.py bob

This script does no GUI or messaging work of its own — it just wires a
``ChatBackend`` to a ``ChatWindow`` via a ``ChatController`` (which owns the
tray icon and the in-app notifications) and starts the Tkinter main loop.
All the real logic lives in ``chat_backend.py``, ``chat_gui.py`` and
``chat_controller.py``.
"""

from __future__ import annotations

import argparse
import sys

from chat_backend import ChatBackend
from chat_controller import ChatController
from chat_gui import ChatWindow, USERS


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Two-window chat over FastStream/Redis with tray + popups.",
    )
    parser.add_argument(
        "user",
        choices=USERS,
        help="Which user this window represents (alice or bob).",
    )
    args = parser.parse_args()

    backend = ChatBackend(user=args.user)
    backend.start()  # blocks until the broker is connected

    window = ChatWindow(user=args.user, backend=backend)
    controller = ChatController(window)
    controller.start_tray()  # non-blocking; runs in a daemon thread
    window.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
