"""
Serena Bot - Helpers
"""
import os, sys, re, tempfile
from typing import Optional
from urllib.parse import unquote

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

# All Terabox domains — checked in detect_url_type
TERABOX_DOMAINS = [
    "terabox.com", "1024terabox.com", "teraboxapp.com", "terabox.app",
    "4funbox.com", "mirrobox.com", "nephobox.com", "freeterabox.com",
    "momerybox.com", "tibibox.com", "teraboxlink.com", "terasharelink.com",
    "www.terabox.com", "www.1024terabox.com",
]


def fmt_size(size_bytes: int) -> str:
    if size_bytes <= 0: return "0 B"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.2f} TB"

_fmt_size = fmt_size


def fmt_duration(seconds: int) -> str:
    if seconds < 60:    return f"{seconds}s"
    elif seconds < 3600: return f"{seconds//60}m {seconds%60}s"
    else:
        h = seconds // 3600; m = (seconds % 3600) // 60
        return f"{h}h {m}m"


def _fix_cookie_content(content: str) -> str:
    if not content: return content
    content = content.strip().strip('"').strip("'")
    content = content.replace("\\n", "\n").replace("\\t", "\t")
    return content


def write_cookies(content: str, prefix: str) -> Optional[str]:
    if not content or not content.strip():
        return None
    content = _fix_cookie_content(content)
    if not content.strip():
        return None
    try:
        tf = tempfile.NamedTemporaryFile(
            mode="w", prefix=f"{prefix}_cookies_", suffix=".txt",
            delete=False, dir="/tmp"
        )
        if "# Netscape" not in content:
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


def get_title_from_url(url: str) -> str:
    """
    Extract human-readable title from URL.
    Checks ?title= param first, then path filename.
    Returns clean title without extension or underscores.
    """
    # 1. Check ?title= query param (common in CDN download links)
    m = re.search(r"[?&]title=([^&]+)", url)
    if m:
        t = unquote(m.group(1))
        # Remove extension
        t = re.sub(r"\.(mp4|mkv|mp3|m4a|pdf|zip|rar|webm|avi|mov|flv|jpg|png|gif)$",
                   "", t, flags=re.I)
        # Replace separators with spaces
        t = t.replace("_", " ").replace("-", " ").replace("+", " ")
        t = re.sub(r"\s+", " ", t).strip()
        if len(t) > 5:
            return t[:100]

    # 2. Fallback: filename from URL path
    path = url.split("?")[0].rstrip("/")
    fname = path.split("/")[-1]
    if fname:
        fname = unquote(fname)
        fname = re.sub(r"\.(mp4|mkv|mp3|m4a|pdf|zip|rar|webm|avi|mov|flv|jpg|png|gif)$",
                       "", fname, flags=re.I)
        fname = fname.replace("_", " ").replace("-", " ").replace("+", " ")
        fname = re.sub(r"\s+", " ", fname).strip()
        if len(fname) > 5:
            return fname[:100]
    return ""


def detect_url_type(url: str) -> str:
    u    = url.lower()
    path = url.split("?")[0].lower()

    # Social / video platforms
    if re.search(r"(youtube\.com|youtu\.be)", u):                  return "youtube"
    if re.search(r"instagram\.com", u):                             return "instagram"
    if re.search(r"(tiktok\.com|vm\.tiktok|vt\.tiktok)", u):      return "tiktok"
    if re.search(r"(twitter\.com|x\.com|t\.co)", u):               return "twitter"
    if re.search(r"(facebook\.com|fb\.watch|fb\.com)", u):         return "facebook"
    if re.search(r"(reddit\.com|v\.redd\.it)", u):                 return "generic"
    if re.search(r"(twitch\.tv|clips\.twitch\.tv)", u):            return "generic"
    if re.search(r"(vimeo\.com)", u):                               return "generic"
    if re.search(r"(dailymotion\.com|dai\.ly)", u):                 return "generic"
    if re.search(r"(soundcloud\.com)", u):                          return "generic"
    if re.search(r"(pinterest\.com|pin\.it)", u):                   return "generic"
    if re.search(r"(snapchat\.com)", u):                            return "generic"

    # Google Drive (normal)
    if re.search(r"drive\.google\.com", u):                         return "gdrive"

    # Google Cloud Storage — treat as direct downloadable file
    if re.search(r"storage\.googleapis\.com", u):                   return "direct_doc"

    # Terabox — all domains
    if any(d in u for d in TERABOX_DOMAINS):                        return "terabox"

    # M3U8 streams
    if re.search(r"\.m3u8", u):                                     return "m3u8"

    # ── Direct file detection — check path extension (expanded) ──
    # Video
    if re.search(r"\.(mp4|mkv|webm|avi|mov|flv|ts|m2ts|3gp|m4v|wmv|rm|rmvb|vob|ogv)(\?|$|#)", path):
        return "direct_video"
    # Audio
    if re.search(r"\.(mp3|aac|flac|wav|ogg|m4a|opus|wma|aiff|alac|amr|au)(\?|$|#)", path):
        return "direct_audio"
    # Image
    if re.search(r"\.(jpg|jpeg|png|gif|webp|bmp|tiff|svg|ico|heic|avif)(\?|$|#)", path):
        return "direct_image"
    # Archive / binary / app
    if re.search(r"\.(zip|rar|tar|7z|gz|bz2|xz|apk|xapk|exe|dmg|pkg|iso|bin|msi|deb|rpm)(\?|$|#)", path):
        return "direct_doc"
    # Document
    if re.search(r"\.(pdf|doc|docx|epub|ppt|pptx|xls|xlsx|odt|ods|odp|txt|csv|json|xml)(\?|$|#)", path):
        return "direct_doc"

    # ── Fallback: check ?title= or ?filename= param for extension ──
    for param in ("title", "filename", "name", "file"):
        m = re.search(rf"[?&]{param}=([^&]+)", url)
        if m:
            t = unquote(m.group(1)).lower()
            if re.search(r"\.(mp4|mkv|webm|avi|mov|flv|ts|m2ts|3gp)", t):  return "direct_video"
            if re.search(r"\.(mp3|aac|flac|wav|m4a|opus|ogg)", t):           return "direct_audio"
            if re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)", t):                return "direct_image"
            if re.search(r"\.(apk|exe|dmg|zip|rar|7z|iso)", t):              return "direct_doc"
            if re.search(r"\.(pdf|zip|rar|doc|docx|epub)", t):               return "direct_doc"

    # ── CDN / download path patterns ──
    if re.search(r"/(download|dl|file|get|fetch|tmp|recycle|attach|attachment)/", u):
        if re.search(r"(\.mp4|video|vid|\.mkv|\.webm)", u):         return "direct_video"
        if re.search(r"(\.mp3|audio|music|\.m4a)", u):              return "direct_audio"
        return "direct_doc"

    return "generic"


def is_valid_url(url: str) -> bool:
    url = url.strip()
    return url.startswith("http://") or url.startswith("https://")


def clean_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', name)[:100].strip()
