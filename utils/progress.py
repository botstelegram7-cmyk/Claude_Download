"""
Serena Downloader Bot - Progress Tracker
Shows progress bar on both downloading AND uploading
"""
import asyncio
import time
from typing import Optional
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified


def _bar(pct: float, length: int = 20) -> str:
    filled = int(length * pct / 100)
    return "●" * filled + "○" * (length - filled)


def _fmt_size(b: int) -> str:
    if b <= 0: return "0 B"
    for u in ("B","KB","MB","GB"):
        if b < 1024: return f"{b:.2f} {u}"
        b /= 1024
    return f"{b:.2f} TB"


def _fmt_eta(secs: int) -> str:
    if secs <= 0: return "∞"
    if secs < 60: return f"{secs}s"
    if secs < 3600: return f"{secs//60}m {secs%60}s"
    return f"{secs//3600}h {(secs%3600)//60}m"


def _fmt_speed(bps: float) -> str:
    return _fmt_size(int(bps)) + "/s"


def build_progress_text(
    title: str,
    action: str,
    done: int,
    total: int,
    speed: float,
    eta: int,
) -> str:
    if total > 0:
        pct = min(done / total * 100, 100)
    else:
        pct = 0

    bar = _bar(pct)
    lines = [
        f"➵⋆ **{action}** `{title[:35]}`\n",
        f"`[{bar}]`",
        f"◌ Progress 😉 : 〘 **{pct:.1f}%** 〙",
        f"Done: 〘 **{_fmt_size(done)}** of **{_fmt_size(total) if total else '?'}** 〙",
        f"◌ Speed 🚀 : 〘 **{_fmt_speed(speed)}** 〙",
        f"◌ Time Left ⏳ : 〘 **{_fmt_eta(eta)}** 〙",
    ]
    return "\n".join(lines)


class ProgressTracker:
    def __init__(
        self,
        message: Optional[Message],
        title: str,
        action: str = "Downloading",
        interval: float = 3.5,
    ):
        self.message = message
        self.title = title
        self.action = action
        self.interval = interval
        self._last_update = 0.0
        self._last_done = 0
        self._last_time = time.time()
        self._speed = 0.0

    async def hook(self, done: int, total: int):
        if not self.message:
            return
        now = time.time()
        if now - self._last_update < self.interval:
            return
        elapsed = now - self._last_time
        if elapsed > 0:
            self._speed = (done - self._last_done) / elapsed
        self._last_done = done
        self._last_time = now
        self._last_update = now
        eta = int((total - done) / self._speed) if self._speed > 0 and total > done else 0
        text = build_progress_text(self.title, self.action, done, total, self._speed, eta)
        await self._safe_edit(text)

    async def uploading(self, done: int, total: int):
        """Call this for upload progress."""
        if not self.message:
            return
        now = time.time()
        if now - self._last_update < self.interval:
            return
        elapsed = now - self._last_time
        if elapsed > 0:
            self._speed = (done - self._last_done) / elapsed
        self._last_done = done
        self._last_time = now
        self._last_update = now
        eta = int((total - done) / self._speed) if self._speed > 0 and total > done else 0
        text = build_progress_text(self.title, "📤 Uploading", done, total, self._speed, eta)
        await self._safe_edit(text)

    async def failed(self, reason: str):
        if self.message:
            await self._safe_edit(f"❌ **Failed:**\n`{reason[:200]}`")

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
    """yt-dlp progress hook — thread-safe, posts to asyncio loop."""
    def __init__(self, tracker: Optional[ProgressTracker], loop: asyncio.AbstractEventLoop):
        self.tracker = tracker
        self.loop = loop
        self._last_post = 0.0

    def __call__(self, d: dict):
        if not self.tracker:
            return
        now = time.time()
        if now - self._last_post < self.tracker.interval:
            return
        self._last_post = now
        if d.get("status") == "downloading":
            done  = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            speed = d.get("speed") or 0.0
            eta   = d.get("eta") or 0
            text  = build_progress_text(self.tracker.title, "⬇️ Downloading",
                                        done, total, speed, eta)
            asyncio.run_coroutine_threadsafe(
                self.tracker._safe_edit(text), self.loop
            )
