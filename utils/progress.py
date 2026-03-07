"""
Serena Bot - Progress Bar
Shows title + action + animated bar + stats
"""
import asyncio, time
from typing import Optional
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified


def _bar(pct: float, length: int = 16) -> str:
    filled = int(length * pct / 100)
    return "▓" * filled + "░" * (length - filled)

def _sz(b: int) -> str:
    if b <= 0: return "0 B"
    for u in ("B","KB","MB","GB"):
        if b < 1024: return f"{b:.1f} {u}"
        b /= 1024
    return f"{b:.1f} TB"

def _eta(secs: int) -> str:
    if secs <= 0: return "∞"
    if secs < 60: return f"{secs}s"
    if secs < 3600: return f"{secs//60}m {secs%60}s"
    return f"{secs//3600}h {(secs%3600)//60}m"

def _spd(bps: float) -> str:
    return _sz(int(bps)) + "/s"


def build_bar(action: str, title: str, done: int, total: int,
              speed: float, eta_s: int) -> str:
    pct = min(done / total * 100, 100) if total > 0 else 0
    icon = "⬇️" if "ownload" in action else "📤"
    name = f"`{title[:35]}`" if title else ""
    lines = [
        f"{icon} **{action}** {name}",
        f"`[{_bar(pct)}]` **{pct:.1f}%**",
        f"┌ 📦 `{_sz(done)}` / `{_sz(total) if total else '?'}`",
        f"├ 🚀 `{_spd(speed)}`",
        f"└ ⏳ `{_eta(eta_s)}`",
    ]
    return "\n".join(lines)


class ProgressTracker:
    def __init__(self, message: Optional[Message], title: str = "",
                 action: str = "Downloading", interval: float = 4.0):
        self.message  = message
        self.title    = title
        self.action   = action
        self.interval = interval
        self._last_update = 0.0
        self._last_done   = 0
        self._last_time   = time.time()
        self._speed       = 0.0

    def _calc(self, done, total):
        now = time.time()
        if now - self._last_update < self.interval:
            return None
        elapsed = now - self._last_time
        if elapsed > 0:
            self._speed = (done - self._last_done) / elapsed
        self._last_done   = done
        self._last_time   = now
        self._last_update = now
        eta = int((total - done) / self._speed) if self._speed > 0 and total > done else 0
        return eta

    async def hook(self, done: int, total: int):
        if not self.message: return
        eta = self._calc(done, total)
        if eta is None: return
        await self._safe_edit(build_bar(self.action, self.title, done, total, self._speed, eta))

    async def uploading(self, done: int, total: int):
        if not self.message: return
        eta = self._calc(done, total)
        if eta is None: return
        await self._safe_edit(build_bar("Uploading", self.title, done, total, self._speed, eta))

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
        self.tracker    = tracker
        self.loop       = loop
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
            # update title from info if available
            info = d.get("info_dict", {})
            if info.get("title") and not self.tracker.title:
                self.tracker.title = info["title"][:35]
            text = build_bar("Downloading", self.tracker.title, done, total, speed, eta)
            asyncio.run_coroutine_threadsafe(
                self.tracker._safe_edit(text), self.loop
            )
