import time
import logging

logger = logging.getLogger(__name__)


class Progress:
    def __init__(self):
        self.last_update_time = 0
        self.update_interval = 5  # seconds

    def generate_progress_bar(self, current: int, total: int, length: int = 15) -> str:
        if total == 0:
            return "░" * length
        pct     = current / total
        filled  = int(length * pct)
        empty   = length - filled
        return "▓" * filled + "░" * empty

    def format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:         return f"{size_bytes} B"
        elif size_bytes < 1024**2:    return f"{size_bytes/1024:.2f} KB"
        elif size_bytes < 1024**3:    return f"{size_bytes/1024**2:.2f} MB"
        else:                          return f"{size_bytes/1024**3:.2f} GB"

    def format_time(self, seconds: int) -> str:
        if seconds < 0:    return "0s"
        if seconds < 60:   return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds//60)}m {int(seconds%60)}s"
        h = int(seconds // 3600); m = int((seconds % 3600) // 60)
        return f"{h}h {m}m"

    def should_update(self) -> bool:
        now = time.time()
        if now - self.last_update_time >= self.update_interval:
            self.last_update_time = now
            return True
        return False

    def get_download_progress_text(
        self, filename: str, current: int, total: int, speed: float, eta: int
    ) -> str:
        pct = (current / total * 100) if total > 0 else 0
        bar = self.generate_progress_bar(current, total)
        name = filename[:45] + ("..." if len(filename) > 45 else "")
        lines = [
            f"⬇️ Downloading `{name}`",
            f"[{bar}] {pct:.1f}%",
            f"┌ 📦 {self.format_size(current)} / {self.format_size(total)}",
            f"├ 🚀 {self.format_size(int(speed))}/s",
            f"└ ⏳ {self.format_time(eta)}",
        ]
        return "\n".join(lines)

    def get_upload_progress_text(
        self, filename: str, current: int, total: int, speed: float, eta: int
    ) -> str:
        pct = (current / total * 100) if total > 0 else 0
        bar = self.generate_progress_bar(current, total)
        name = filename[:45] + ("..." if len(filename) > 45 else "")
        lines = [
            f"📤 Uploading `{name}`",
            f"[{bar}] {pct:.1f}%",
            f"┌ 📦 {self.format_size(current)} / {self.format_size(total)}",
            f"├ 🚀 {self.format_size(int(speed))}/s",
            f"└ ⏳ {self.format_time(eta)}",
        ]
        return "\n".join(lines)

    def get_queue_status_text(self, current: int, total: int, filename: str) -> str:
        return f"📊 **Task Progress:** {current}/{total}\n📁 **Current:** `{filename}`"


async def progress_callback(current, total, message, progress_obj, start_time, filename, is_upload=False):
    try:
        if not progress_obj.should_update():
            return
        elapsed = time.time() - start_time
        speed   = current / elapsed if elapsed > 0 else 0
        eta     = int((total - current) / speed) if speed > 0 else 0
        if is_upload:
            text = progress_obj.get_upload_progress_text(filename, current, total, speed, eta)
        else:
            text = progress_obj.get_download_progress_text(filename, current, total, speed, eta)
        await message.edit_text(text)
    except Exception as e:
        logger.debug(f"Progress update error: {e}")
