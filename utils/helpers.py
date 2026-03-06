"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Helpers      ║
╚══════════════════════════════════════════╝
"""

import os
import sys
import re
import tempfile
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import (
    YT_COOKIES, INSTAGRAM_COOKIES, TERABOX_COOKIES,
    BOT_NAME, BOT_USERNAME, OWNER_USERNAME, SUPPORT_USERNAME, PLANS
)

HEADER  = "⋆｡° ✮ °｡⋆"
DIVIDER = "»»──── ✦ ────««"
FOOTER  = "⋆ ｡˚ ˚｡ ⋆"
BULLET  = "▸"


def fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"


def _fmt_size(size_bytes: int) -> str:
    return fmt_size(size_bytes)


def fmt_duration(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h {m}m"


def _fix_cookie_content(content: str) -> str:
    """Fix Render env var encoding: literal \\n -> real newlines, strip quotes."""
    if not content:
        return content
    content = content.strip().strip('"').strip("'")
    content = content.replace("\\n", "\n")
    content = content.replace("\\t", "\t")
    return content


def write_cookies(content: str, prefix: str) -> Optional[str]:
    if not content or not content.strip():
        return None
    content = _fix_cookie_content(content)
    if not content.strip():
        return None
    try:
        tf = tempfile.NamedTemporaryFile(
            mode="w", prefix=f"{prefix}_cookies_",
            suffix=".txt", delete=False, dir="/tmp"
        )
        if not content.startswith("# Netscape HTTP Cookie File"):
            tf.write("# Netscape HTTP Cookie File\n")
        tf.write(content.strip() + "\n")
        tf.close()
        return tf.name
    except Exception:
        return None


def get_yt_cookie_file() -> Optional[str]:
    return write_cookies(YT_COOKIES, "yt")


def get_instagram_cookie_file() -> Optional[str]:
    return write_cookies(INSTAGRAM_COOKIES, "ig")


def get_terabox_cookie_file() -> Optional[str]:
    return write_cookies(TERABOX_COOKIES, "tb")


def detect_url_type(url: str) -> str:
    u = url.lower()
    if re.search(r"(youtube\.com|youtu\.be)", u):              return "youtube"
    if re.search(r"instagram\.com", u):                         return "instagram"
    if re.search(r"(tiktok\.com|vm\.tiktok)", u):              return "tiktok"
    if re.search(r"(twitter\.com|x\.com|t\.co)", u):           return "twitter"
    if re.search(r"(facebook\.com|fb\.watch)", u):              return "facebook"
    if re.search(r"drive\.google\.com", u):                     return "gdrive"
    if re.search(r"(terabox\.com|4funbox|nephobox)", u):        return "terabox"
    if re.search(r"\.m3u8", u):                                 return "m3u8"
    if re.search(r"\.(mp4|mkv|webm|avi|mov|flv|ts)(\?|$)", u): return "direct_video"
    if re.search(r"\.(mp3|aac|flac|wav|ogg|m4a)(\?|$)", u):    return "direct_audio"
    if re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)(\?|$)", u):   return "direct_image"
    if re.search(r"\.(pdf|doc|docx|zip|rar|tar)(\?|$)", u):    return "direct_doc"
    return "generic"


def is_valid_url(url: str) -> bool:
    pattern = re.compile(
        r"^(https?://)?(www\.)?"
        r"[\w\-]+(\.[\w\-]+)+"
        r"[/\w\-._~:/?#\[\]@!$&'()*+,;=%]*$"
    )
    return bool(pattern.match(url.strip()))


def clean_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name)[:100].strip()


def plan_info_text(plan: str) -> str:
    p = PLANS.get(plan, PLANS["free"])
    limit_str = "Unlimited" if p["limit"] >= 999999 else str(p["limit"])
    duration_str = "Lifetime" if p["days"] == 0 else f"{p['days']} days"
    return f"{p['name']} — {limit_str} downloads/day — {duration_str}"
