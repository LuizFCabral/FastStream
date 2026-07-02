"""Tkinter chat window — pure GUI, no FastStream or Redis imports.

This module knows how to:
  * Render a window with a recipient selector, a scrolling log, and an input
    field.
  * Forward the user's input to a ``ChatBackend`` (passed in by the caller).
  * Drain the backend's message queue on the Tkinter thread and display
    messages in the log.
  * Expose hooks for unread-message accounting (called by the controller
    that owns the tray icon and the hide/show lifecycle).

It does NOT know anything about Redis, asyncio, or the wire format. That
separation lets you swap the backend (e.g. for an in-memory backend in tests)
without touching the GUI code.
"""

from __future__ import annotations

import queue
import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from chat_backend import ChatBackend, ChatMessage


# Users that show up in the recipient selector.
USERS: tuple[str, ...] = ("alice", "bob")


class ChatWindow:
    """A single user's chat window."""

    POLL_INTERVAL_MS = 100  # how often we drain the backend's queue

    def __init__(self, user: str, backend: "ChatBackend") -> None:
        self.user = user
        self.backend = backend
        # Counters updated by the controller / the window itself.
        self.sent_count: int = 0
        self.received_count: int = 0

        self.root = tk.Tk()
        self.root.title(f"Chat — {user}")
        self.root.geometry("480x520")
        # Closing the window hides it; the app keeps running in the tray.
        # The controller's "Quit" menu item is the only way to truly exit.
        self.root.protocol("WM_DELETE_WINDOW", self._on_close_request)

        self._build_widgets()
        self._refresh_title()
        # Begin draining the queue.
        self.root.after(self.POLL_INTERVAL_MS, self._drain_incoming)

    # -- UI construction --------------------------------------------------

    def _build_widgets(self) -> None:
        other = next((u for u in USERS if u != self.user), USERS[0])
        self.recipient_var = tk.StringVar(value=other)

        top = ttk.Frame(self.root, padding=8)
        top.pack(fill=tk.X)
        ttk.Label(top, text="To:").pack(side=tk.LEFT)
        ttk.Combobox(
            top,
            textvariable=self.recipient_var,
            values=list(USERS),
            state="readonly",
            width=10,
        ).pack(side=tk.LEFT, padx=(4, 0))

        # Sent / received counters in the top bar.
        self.counters_var = tk.StringVar(value="Sent: 0   Received: 0")
        ttk.Label(top, textvariable=self.counters_var).pack(side=tk.RIGHT)

        mid = ttk.Frame(self.root, padding=(8, 0))
        mid.pack(fill=tk.BOTH, expand=True)
        self.log = scrolledtext.ScrolledText(mid, state=tk.DISABLED, wrap=tk.WORD)
        self.log.pack(fill=tk.BOTH, expand=True)

        bottom = ttk.Frame(self.root, padding=8)
        bottom.pack(fill=tk.X)
        self.entry = ttk.Entry(bottom)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry.bind("<Return>", lambda _e: self._on_send())
        ttk.Button(bottom, text="Send", command=self._on_send).pack(
            side=tk.LEFT, padx=(6, 0)
        )

    # -- counters & title -------------------------------------------------

    def _refresh_counters(self) -> None:
        self.counters_var.set(
            f"Sent: {self.sent_count}   Received: {self.received_count}"
        )

    def _refresh_title(self, unread: int = 0) -> None:
        if unread > 0:
            self.root.title(f"Chat — {self.user}  ({unread} unread)")
        else:
            self.root.title(f"Chat — {self.user}")

    # -- user actions -----------------------------------------------------

    def _on_send(self) -> None:
        text = self.entry.get().strip()
        if not text:
            return
        recipient = self.recipient_var.get()
        if recipient == self.user:
            return
        self.backend.send(recipient, text)
        self.sent_count += 1
        self._refresh_counters()
        self._append(self._local_echo(text), is_local=True)
        self.entry.delete(0, tk.END)

    def _local_echo(self, text: str) -> "ChatMessage":
        from chat_backend import ChatMessage
        return ChatMessage(sender=self.user, text=text)

    # -- incoming messages ------------------------------------------------

    def _drain_incoming(self) -> None:
        try:
            while True:
                msg = self.backend.messages.get_nowait()
                self._append(msg, is_local=False)
                if msg.sender != "system":
                    self.received_count += 1
                    self._refresh_counters()
                    if self._on_incoming is not None:
                        # Hand off to the controller so it can update the
                        # tray, the title badge, and the popup.
                        self._on_incoming(msg)
        except queue.Empty:
            pass
        finally:
            self.root.after(self.POLL_INTERVAL_MS, self._drain_incoming)

    def _append(self, msg: "ChatMessage", *, is_local: bool) -> None:
        self.log.configure(state=tk.NORMAL)
        prefix = "↩ " if is_local else "← "
        self.log.insert(tk.END, prefix + msg.format() + "\n")
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    # -- window lifecycle hooks (called by the controller) ----------------

    # Set by the controller to be notified of every new incoming message.
    _on_incoming: "Callable[[ChatMessage], None] | None" = None

    def _on_close_request(self) -> None:
        """Hide instead of quitting. Controller decides what 'quit' means."""
        self.root.withdraw()

    def show(self) -> None:
        """Make the window visible, deiconify, and bring to the front."""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        # Clear the unread badge: the user has now seen the messages.
        if self._on_focus is not None:
            self._on_focus()

    def is_visible(self) -> bool:
        try:
            return bool(self.root.winfo_viewable())
        except tk.TclError:
            return False

    _on_focus: "Callable[[], None] | None" = None

    def destroy(self) -> None:
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
