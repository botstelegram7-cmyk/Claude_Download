"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Progress     ║
╚══════════════════════════════════════════╝
"""

import time
import asyncio
from typing import Optional
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified


def _make_bar(pct: float, length: int = 20) -> str:
    filled = int(length * pct / 100)
    empty = length - filled
    return "●" * filled + "○" * empty


def _fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def _fmt_eta(seconds: int) -> str:
    if seconds <= 0:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        m, s = divmod(seconds, 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(seconds, 3600)
        m = rem // 60
        return f"{h}h {m}m"


def _fmt_speed(bps: float) -> str:
    return _fmt_size(int(bps)) + "/s"


def build_progress_text(
    title: str,
    pct: float,
    current: int,
    total: int,
    speed: float = 0,
    eta: int = 0,
    action: str = "Downloading",
) -> str:
    bar = _make_bar(pct)
    done_str = _fmt_size(current)
    total_str = _fmt_size(total) if total else "?"
    speed_str = _fmt_speed(speed) if speed > 0 else "—"
    eta_str = _fmt_eta(eta)
    return (
        f"➵⋆ **{action}** `{title[:40]}`\n\n"
        f"`[{bar}]`\n"
        f"◌ Progress 😉 : 〘 **{pct:.2f}%** 〙\n"
        f"Done: 〘 **{done_str}** of **{total_str}** 〙\n"
        f"◌ Speed 🚀 : 〘 **{speed_str}** 〙\n"
        f"◌ Time Left ⏳ : 〘 **{eta_str}** 〙"
    )


class ProgressTracker:
    def __init__(self, message: Message, title: str = "Media", action: str = "Downloading", interval: float = 3.5):
        self.message = message
        self.title = title
        self.action = action
        self.interval = interval
        self._last_update: float = 0
        self._last_text: str = ""
        self._last_bytes: int = 0
        self._last_speed_time: float = time.time()
        self._speed: float = 0.0

    def _calc_speed(self, current: int) -> float:
        now = time.time()
        elapsed = now - self._last_speed_time
        if elapsed > 0.5:
            self._speed = (current - self._last_bytes) / elapsed
            self._last_bytes = current
            self._last_speed_time = now
        return max(self._speed, 0)

    async def hook(self, current: int, total: int):
        now = time.time()
        if now - self._last_update < self.interval:
            return
        self._last_update = now
        speed = self._calc_speed(current)
        pct = min(current / total * 100, 100.0) if total > 0 else 0.0
        eta = int((total - current) / speed) if speed > 0 and total > 0 else 0
        text = build_progress_text(self.title, pct, current, total, speed, eta, self.action)
        if text == self._last_text:
            return
        self._last_text = text
        await self._safe_edit(text)

    async def _safe_edit(self, text: str, retries: int = 3):
        for _ in range(retries):
            try:
                await self.message.edit_text(text)
                return
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except MessageNotModified:
                return
            except Exception:
                return

    async def done(self, text: str):
        await self._safe_edit(text)

    async def failed(self, reason: str):
        await self._safe_edit(f"❌ **Failed:** `{reason[:200]}`")


class YtdlpProgressHook:
    def __init__(self, tracker: ProgressTracker, loop: asyncio.AbstractEventLoop):
        self.tracker = tracker
        self.loop = loop
        self._last_call: float = 0
        self._interval: float = 3.5

    def __call__(self, d: dict):
        if d["status"] != "downloading":
            return
        now = time.time()
        if now - self._last_call < self._interval:
            return
        self._last_call = now
        current = d.get("downloaded_bytes", 0) or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        speed = d.get("speed") or 0
        eta = int(d.get("eta") or 0)
        pct = min(current / total * 100, 100.0) if total > 0 else 0.0
        text = build_progress_text(self.tracker.title, pct, current, total, speed, eta, self.tracker.action)
        if text == self.tracker._last_text:
            return
        self.tracker._last_text = text
        self.tracker._last_update = now
        asyncio.run_coroutine_threadsafe(self.tracker._safe_edit(text), self.loop)
