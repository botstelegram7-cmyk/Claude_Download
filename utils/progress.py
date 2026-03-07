"""
Serena Bot - Progress Tracker
NO title shown in progress — just action + bar + stats
"""
import asyncio, time
from typing import Optional
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified


def _bar(pct: float, length: int = 18) -> str:
    filled = int(length * pct / 100)
    return "█" * filled + "░" * (length - filled)


def _fmt_size(b: int) -> str:
    if b <= 0: return "0 B"
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"


def _fmt_eta(secs: int) -> str:
    if secs <= 0: return "∞"
    if secs < 60: return f"{secs}s"
    if secs < 3600: return f"{secs // 60}m {secs % 60}s"
    return f"{secs // 3600}h {(secs % 3600) // 60}m"


def _fmt_speed(bps: float) -> str:
    return _fmt_size(int(bps)) + "/s"


def _progress_text(action: str, done: int, total: int, speed: float, eta: int) -> str:
    pct = min(done / total * 100, 100) if total > 0 else 0
    bar = _bar(pct)
    lines = [
        f"{'⬇️' if 'ownload' in action else '📤'} **{action}**",
        f"`[{bar}]` **{pct:.1f}%**",
        f"▸ `{_fmt_size(done)}` / `{_fmt_size(total) if total else '?'}`",
        f"▸ Speed: `{_fmt_speed(speed)}`  ETA: `{_fmt_eta(eta)}`",
    ]
    return "\n".join(lines)


class ProgressTracker:
    def __init__(self, message: Optional[Message], title: str = "",
                 action: str = "Downloading", interval: float = 4.0):
        self.message  = message
        self.title    = title   # kept for compat but NOT shown in progress
        self.action   = action
        self.interval = interval
        self._last_update = 0.0
        self._last_done   = 0
        self._last_time   = time.time()
        self._speed       = 0.0

    async def hook(self, done: int, total: int):
        if not self.message: return
        now = time.time()
        if now - self._last_update < self.interval: return
        elapsed = now - self._last_time
        if elapsed > 0:
            self._speed = (done - self._last_done) / elapsed
        self._last_done  = done
        self._last_time  = now
        self._last_update = now
        eta = int((total - done) / self._speed) if self._speed > 0 and total > done else 0
        await self._safe_edit(_progress_text(self.action, done, total, self._speed, eta))

    async def uploading(self, done: int, total: int):
        if not self.message: return
        now = time.time()
        if now - self._last_update < self.interval: return
        elapsed = now - self._last_time
        if elapsed > 0:
            self._speed = (done - self._last_done) / elapsed
        self._last_done  = done
        self._last_time  = now
        self._last_update = now
        eta = int((total - done) / self._speed) if self._speed > 0 and total > done else 0
        await self._safe_edit(_progress_text("Uploading", done, total, self._speed, eta))

    async def _safe_edit(self, text: str):
        for _ in range(3):
            try:
                await self.message.edit_text(text)
                return
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except (MessageNotModified, Exception):
                return


class YtdlpProgressHook:
    def __init__(self, tracker: Optional[ProgressTracker],
                 loop: asyncio.AbstractEventLoop):
        self.tracker   = tracker
        self.loop      = loop
        self._last_post = 0.0

    def __call__(self, d: dict):
        if not self.tracker: return
        now = time.time()
        if now - self._last_post < self.tracker.interval: return
        self._last_post = now
        if d.get("status") == "downloading":
            done  = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or 0.0
            eta   = d.get("eta") or 0
            text  = _progress_text("Downloading", done, total, speed, eta)
            asyncio.run_coroutine_threadsafe(
                self.tracker._safe_edit(text), self.loop
            )
