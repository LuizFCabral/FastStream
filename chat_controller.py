"""Chat controller — owns the tray icon and the in-app notification popup.

Sits between the ``ChatWindow`` (pure Tkinter) and the ``ChatBackend`` (pure
messaging). Responsibilities:

  * Spawns and manages a system tray icon with "Show" and "Quit" entries.
  * Keeps an "unread" counter that grows as new messages arrive while the
    window is hidden, and resets to zero when the window is shown.
  * Renders an in-app notification popup that grows with the unread count
    (so the user can tell at a glance how many messages are waiting).
  * Forwards window-hide events to ``root.withdraw()`` and window-show
    events to ``window.show()``.

Tray + Pillow are imported lazily so the app still runs without them; in that
case the unread count is still shown in the window's title bar and the
in-app popup still works, only the system tray icon is missing.
"""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from chat_gui import ChatWindow
    from chat_backend import ChatMessage


# Maximum number of unread messages displayed on a single popup line. Anything
# above this shows as "N+ new messages" so the popup doesn't grow forever.
MAX_POPUP_VISIBLE = 99


class ChatController:
    """Wires the window to the tray icon and the in-app notification popup."""

    def __init__(self, window: "ChatWindow") -> None:
        self.window = window
        self.unread: int = 0
        self._tray = None  # type: ignore[var-annotated]
        self._popup: "NotificationPopup | None" = None
        self._popup_after_id: str | None = None  # Tk after-cancel handle

        # Hooks the window calls when something interesting happens.
        self.window._on_incoming = self._on_incoming_message
        self.window._on_focus = self._on_window_focused

    # -- tray icon --------------------------------------------------------

    def start_tray(self) -> None:
        """Create the system tray icon on a background thread. If pystray /
        Pillow aren't installed, the rest of the app still works."""
        try:
            import pystray  # type: ignore
            from PIL import Image, ImageDraw  # type: ignore
        except ImportError:
            return  # No tray support; title-bar badge still works.

        def _run_tray() -> None:
            icon_image = self._build_icon_image(Image, ImageDraw)
            menu = pystray.Menu(
                pystray.MenuItem("Show", self._tray_show, default=True),
                pystray.MenuItem("Quit", self._tray_quit),
            )
            self._tray = pystray.Icon(
                f"faststream-chat-{self.window.user}",
                icon_image,
                f"Chat — {self.window.user}",
                menu,
            )
            self._tray.run()

        t = threading.Thread(target=_run_tray, daemon=True, name="tray")
        t.start()

    @staticmethod
    def _build_icon_image(Image, ImageDraw):  # type: ignore[no-untyped-def]
        """Generate a 64x64 icon programmatically. No PNG asset needed."""
        size = 64
        image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)
        # Rounded square background.
        draw.rounded_rectangle(
            (4, 4, size - 4, size - 4), radius=12, fill=(33, 150, 243, 255)
        )
        # Speech bubble tail.
        draw.polygon(
            [(20, size - 4), (32, size - 4), (24, size - 14)], fill=(33, 150, 243, 255)
        )
        # Three dots inside the bubble.
        for cx in (22, 32, 42):
            draw.ellipse((cx - 3, 24, cx + 3, 30), fill=(255, 255, 255, 255))
        return image

    def _tray_show(self, _icon, _item) -> None:  # type: ignore[no-untyped-def]
        # Called from the tray thread; bounce into the Tk main loop.
        self.window.root.after(0, self.window.show)

    def _tray_quit(self, _icon, _item) -> None:  # type: ignore[no-untyped-def]
        self.window.root.after(0, self.quit)

    # -- incoming message handling ---------------------------------------

    def _on_incoming_message(self, msg: "ChatMessage") -> None:
        # If the window is already visible, just refresh the title to "no
        # unread" (the user is reading live) and skip the popup. Otherwise
        # increment the unread counter and show the in-app popup.
        if self.window.is_visible():
            self.window._refresh_title(unread=0)
            return

        self.unread += 1
        self.window._refresh_title(unread=self.unread)
        self._show_popup(msg)

    def _on_window_focused(self) -> None:
        # Reset the unread counter when the user brings the window back.
        self.unread = 0
        self.window._refresh_title(unread=0)
        self._dismiss_popup()

    def _on_popup_clicked(self) -> None:
        # Clicking the popup brings the main window to the front, which
        # in turn clears the unread badge and dismisses the popup.
        self.window.show()

    # -- in-app popup ----------------------------------------------------

    def _show_popup(self, msg: "ChatMessage") -> None:
        if self._popup is None or not self._popup.alive():
            self._popup = NotificationPopup(
                self.window.root,
                self.window.user,
                on_click=self._on_popup_clicked,
            )
        self._popup.update(msg, self.unread)
        # Auto-dismiss after a few seconds, but only if the unread count
        # hasn't grown further in the meantime. We re-schedule the
        # dismissal every time a new message arrives, so a rapid burst of
        # messages keeps the popup on screen.
        if self._popup_after_id is not None:
            try:
                self.window.root.after_cancel(self._popup_after_id)
            except tk.TclError:
                pass
        self._popup_after_id = self.window.root.after(
            self.AUTO_DISMISS_MS, self._auto_dismiss_popup
        )

    def _auto_dismiss_popup(self) -> None:
        # Only dismiss if the window is still hidden (otherwise leave it).
        if self._popup is not None and not self.window.is_visible():
            self._dismiss_popup()

    def _dismiss_popup(self) -> None:
        if self._popup is not None:
            self._popup.close()
            self._popup = None
        self._popup_after_id = None

    # -- shutdown --------------------------------------------------------

    def quit(self) -> None:
        self._dismiss_popup()
        if self._tray is not None:
            try:
                self._tray.stop()
            except Exception:
                pass
        self.window.destroy()


class NotificationPopup:
    """A small, auto-positioned, borderless Tk window that grows with the
    number of unread messages. Positioned near the bottom-right of the
    primary screen so it doesn't get in the way of the chat window."""

    # Visual constants.
    MIN_WIDTH = 280
    WIDTH_PER_UNREAD = 6  # how much the popup widens per unread message
    MAX_WIDTH = 520
    HEIGHT_BASE = 70
    MARGIN = 24  # distance from the screen edge
    AUTO_DISMISS_MS = 6000  # how long a single popup stays on screen

    def __init__(
        self,
        parent: tk.Misc,
        user: str,
        on_click: "callable | None" = None,
    ) -> None:
        self.user = user
        self._on_click = on_click
        self.top = tk.Toplevel(parent)
        self.top.overrideredirect(True)  # no window decorations
        self.top.attributes("-topmost", True)
        # Light translucent look using ttk styles.
        style = ttk.Style(self.top)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Notif.TFrame",
            background="#1f1f1f",
        )
        style.configure(
            "NotifTitle.TLabel",
            background="#1f1f1f",
            foreground="#ffb74d",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "NotifBody.TLabel",
            background="#1f1f1f",
            foreground="#ffffff",
            font=("Segoe UI", 9),
            wraplength=360,
            justify="left",
        )
        style.configure(
            "NotifCount.TLabel",
            background="#d32f2f",
            foreground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padding=(6, 2),
        )

        self.frame = ttk.Frame(self.top, style="Notif.TFrame", padding=12)
        self.frame.pack(fill=tk.BOTH, expand=True)

        self.title_var = tk.StringVar()
        self.body_var = tk.StringVar()
        self.count_var = tk.StringVar()

        header = ttk.Frame(self.frame, style="Notif.TFrame")
        header.pack(fill=tk.X)
        ttk.Label(
            header, textvariable=self.title_var, style="NotifTitle.TLabel"
        ).pack(side=tk.LEFT)
        ttk.Label(
            header, textvariable=self.count_var, style="NotifCount.TLabel"
        ).pack(side=tk.RIGHT)

        ttk.Label(
            self.frame, textvariable=self.body_var, style="NotifBody.TLabel"
        ).pack(fill=tk.X, pady=(6, 0))

        # Click anywhere to show the window.
        for w in (self.top, self.frame, header):
            w.bind("<Button-1>", lambda _e: self._handle_click())

        self._position()

    def _handle_click(self) -> None:
        if self._on_click is not None:
            self._on_click()

    def alive(self) -> bool:
        try:
            return bool(self.top.winfo_exists())
        except tk.TclError:
            return False

    def _position(self) -> None:
        self.top.update_idletasks()
        # Required so winfo_width/height return real values.
        self.top.update()
        screen_w = self.top.winfo_screenwidth()
        screen_h = self.top.winfo_screenheight()
        w = max(self.top.winfo_width(), self.MIN_WIDTH)
        h = max(self.top.winfo_height(), self.HEIGHT_BASE)
        x = screen_w - w - self.MARGIN
        y = screen_h - h - self.MARGIN
        self.top.geometry(f"{w}x{h}+{x}+{y}")

    def update(self, msg: "ChatMessage", unread: int) -> None:
        unread_display = min(unread, MAX_POPUP_VISIBLE)
        suffix = "+" if unread > MAX_POPUP_VISIBLE else ""
        if unread == 1:
            self.count_var.set("1 new")
        else:
            self.count_var.set(f"{unread_display}{suffix} new")
        self.title_var.set(f"New message from {msg.sender}")
        self.body_var.set(msg.text)
        # Force a re-layout, then re-pin to bottom-right.
        self.top.update_idletasks()
        self.top.update()
        # Make the popup grow with the unread count. The width is bounded
        # by MAX_WIDTH so a flood of messages doesn't push the popup off
        # the right edge of the screen.
        growth = max(0, unread - 1) * self.WIDTH_PER_UNREAD
        total_w = min(self.MAX_WIDTH, self.MIN_WIDTH + growth)
        # The body label's required height grows when the text wraps onto
        # more lines; we add a small fudge factor for the padding.
        body_req_h = self.frame.winfo_reqheight()
        total_h = max(self.HEIGHT_BASE, body_req_h + 24)
        screen_w = self.top.winfo_screenwidth()
        screen_h = self.top.winfo_screenheight()
        x = screen_w - total_w - self.MARGIN
        y = screen_h - total_h - self.MARGIN
        self.top.geometry(f"{total_w}x{total_h}+{x}+{y}")
        # Briefly raise to make sure it stays on top.
        self.top.lift()

    def close(self) -> None:
        try:
            self.top.destroy()
        except tk.TclError:
            pass
