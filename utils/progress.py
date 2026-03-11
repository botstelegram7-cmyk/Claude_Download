"""
Serena Bot - Progress Bar
Format:
  ➵⋆🪐ᴛᴇᴄʜɴɪᴄᴀʟ_sᴇʀᴇɴᴀ𓂃
  📄 filename
  ↔️ to Telegram
  [●●●●○○○○○○○○○○○○○○○○]
  ◌ Progress 😉 : 〘 8.3% 〙
  ✅ Done       : 〘 46.00 MB of 552.19 MB 〙
  🚀 Speed      : 〘 3.98 MB/s 〙
  ⏳ ETA        : 〘 2m 7s 〙
  📶 Network    : 📶 Fast
"""
import asyncio
import time
from typing import Optional
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

HEADER = "➵⋆🪐ᴛᴇᴄʜɴɪᴄᴀʟ_sᴇʀᴇɴᴀ𓂃"
BAR_LEN = 20


def _bar(pct: float) -> str:
    filled = int(BAR_LEN * pct / 100)
    empty  = BAR_LEN - filled
    return "●" * filled + "○" * empty


def _sz(b: int) -> str:
    if b <= 0: return "0 B"
    for u in ("B", "KB", "MB", "GB"):
        if b < 1024: return f"{b:.2f} {u}"
        b /= 1024
    return f"{b:.2f} TB"


def _eta(secs: int) -> str:
    if secs <= 0:    return "∞"
    if secs < 60:    return f"{secs}s"
    if secs < 3600:  return f"{secs // 60}m {secs % 60}s"
    return f"{secs // 3600}h {(secs % 3600) // 60}m"


def _spd(bps: float) -> str:
    return _sz(int(bps)) + "/s"


def _network_label(speed_bps: float) -> str:
    mb = speed_bps / (1024 * 1024)
    if mb >= 5:    return "📶 Super Fast"
    if mb >= 2:    return "📶 Fast"
    if mb >= 0.5:  return "📶 Normal"
    if mb > 0:     return "📶 Slow"
    return "📶 Connecting..."


def build_bar(action: str, title: str, done: int, total: int,
              speed: float, eta_s: int) -> str:
    pct = min(done / total * 100, 100) if total > 0 else 0
    bar = _bar(pct)

    # Direction label
    if "Upload" in action:
        direction = "↔️ to Telegram"
    elif "GoFile" in action:
        direction = "☁️ to GoFile.io"
    else:
        direction = "⬇️ Downloading"

    name = title[:45] if title else "file"

    lines = [
        HEADER,
        f"📄 `{name}`",
        direction,
        f"`[{bar}]`",
        f"◌ Progress 😉 : 〘 **{pct:.1f}%** 〙",
        f"✅ Done       : 〘 `{_sz(done)}` of `{_sz(total) if total else '?'}` 〙",
        f"🚀 Speed      : 〘 `{_spd(speed)}` 〙",
        f"⏳ ETA        : 〘 `{_eta(eta_s)}` 〙",
        f"📶 Network    : {_network_label(speed)}",
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
        act = "Uploading"
        if "GoFile" in self.action:
            act = "GoFile Upload"
        eta = self._calc(done, total)
        if eta is None: return
        await self._safe_edit(build_bar(act, self.title, done, total, self._speed, eta))

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
            info  = d.get("info_dict", {})
            if info.get("title") and not self.tracker.title:
                self.tracker.title = info["title"][:45]
            text = build_bar("Downloading", self.tracker.title, done, total, speed, eta)
            asyncio.run_coroutine_threadsafe(
                self.tracker._safe_edit(text), self.loop
            )
