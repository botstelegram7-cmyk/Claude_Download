"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Core DL      ║
╚══════════════════════════════════════════╝
"""

import os
import sys
import asyncio
import subprocess
import uuid
import time
from typing import Optional, Callable

# ── sys.path fix ──
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import (
    get_yt_cookie_file, get_instagram_cookie_file,
    get_terabox_cookie_file, detect_url_type, clean_filename
)

os.makedirs(DL_DIR, exist_ok=True)

# ── Quality format map ──
QUALITY_MAP = {
    "144p":  "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=144]+bestaudio/best[height<=144]/best",
    "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
    "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
    "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    "audio": "bestaudio/best",
    "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
}


def check_cookies_valid(cookie_file: str) -> bool:
    """Check if cookie file has valid non-expired entries."""
    if not cookie_file or not os.path.exists(cookie_file):
        return False
    now = int(time.time())
    valid_count = 0
    expired_count = 0
    try:
        with open(cookie_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    try:
                        expiry = int(parts[4])
                        if expiry == 0:
                            valid_count += 1  # session cookie, no expiry
                        elif expiry > now:
                            valid_count += 1
                        else:
                            expired_count += 1
                    except ValueError:
                        pass
    except Exception:
        return False
    return valid_count > 0


def _build_ydl_opts(
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    cookie_file: Optional[str] = None,
    progress_hook: Optional[Callable] = None,
    url_type: str = "generic",
) -> dict:
    # For non-video platforms, use simpler format to avoid "format not available"
    if audio_only:
        fmt = "bestaudio/best"
    elif url_type in ("instagram", "tiktok", "twitter", "facebook", "terabox", "generic"):
        # These platforms don't support complex format strings — use simple fallback
        fmt = "best[ext=mp4]/best"
    else:
        fmt = QUALITY_MAP.get(quality, QUALITY_MAP["best"])

    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "merge_output_format": "mp4",
        "writethumbnail": False,
        "postprocessors": [],
        "retries": 5,
        "fragment_retries": 5,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        # Fix for "format not available" on generic URLs
        "ignoreerrors": False,
        "allow_unplayable_formats": False,
    }

    if audio_only:
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })

    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    return opts


async def download_with_ytdlp(
    url: str,
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    progress_hook: Optional[Callable] = None,
) -> Optional[str]:
    """Download URL using yt-dlp. Returns file path or list of paths (playlist)."""
    import yt_dlp

    url_type = detect_url_type(url)
    cookie_file = None
    cookie_expired = False

    if url_type == "youtube":
        cookie_file = get_yt_cookie_file()
        if cookie_file and not check_cookies_valid(cookie_file):
            cookie_expired = True
            cookie_file = None  # don't use expired cookies
    elif url_type == "instagram":
        cookie_file = get_instagram_cookie_file()
    elif url_type == "terabox":
        cookie_file = get_terabox_cookie_file()

    os.makedirs(out_dir, exist_ok=True)
    opts = _build_ydl_opts(out_dir, quality, audio_only, cookie_file, progress_hook, url_type)
    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None
            if "entries" in info:
                files = []
                for entry in (info["entries"] or []):
                    if not entry:
                        continue
                    f = ydl.prepare_filename(entry)
                    for candidate in [f, f.replace(".webm", ".mp4"), f.replace(".mkv", ".mp4")]:
                        if os.path.exists(candidate):
                            files.append(candidate)
                            break
                return files or None
            else:
                f = ydl.prepare_filename(info)
                for candidate in [f, f.replace(".webm", ".mp4"), f.replace(".mkv", ".mp4")]:
                    if os.path.exists(candidate):
                        return candidate
                # Fallback: newest file in dir
                all_files = [
                    os.path.join(out_dir, x)
                    for x in os.listdir(out_dir)
                    if os.path.isfile(os.path.join(out_dir, x))
                    and not x.endswith((".jpg", ".png", ".webp"))
                ]
                return sorted(all_files, key=os.path.getmtime, reverse=True)[0] if all_files else None

    try:
        result = await loop.run_in_executor(None, _download)
        return result
    except Exception as e:
        err = str(e)
        # Detect cookie/auth errors and give helpful message
        if "Sign in to confirm" in err or "bot" in err.lower() or "cookies" in err.lower():
            raise RuntimeError(
                "🍪 YouTube requires fresh cookies.\n\n"
                "▸ Your cookies may be expired or missing.\n"
                "▸ Export new cookies from your browser and update `YT_COOKIES` in Render env vars.\n"
                "▸ See: https://github.com/yt-dlp/yt-dlp/wiki/Extractors#exporting-youtube-cookies"
            )
        if "Requested format is not available" in err:
            # Retry with absolute fallback format
            opts["format"] = "best"
            try:
                result = await loop.run_in_executor(None, _download)
                return result
            except Exception as e2:
                raise RuntimeError(f"yt-dlp error: {e2}")
        raise RuntimeError(f"yt-dlp error: {err}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
            except Exception:
                pass


async def check_yt_cookies_status() -> dict:
    """
    Returns dict with:
      - valid: bool
      - expired: bool
      - message: str
      - expires_at: str (nearest expiry date)
    """
    from config import YT_COOKIES
    import time
    from datetime import datetime

    if not YT_COOKIES or not YT_COOKIES.strip():
        return {"valid": False, "expired": False, "message": "❌ No YT_COOKIES set in environment."}

    cookie_file = get_yt_cookie_file()
    if not cookie_file:
        return {"valid": False, "expired": False, "message": "❌ Failed to write cookie file."}

    now = int(time.time())
    valid_count = 0
    expired_count = 0
    nearest_expiry = None

    try:
        with open(cookie_file, "r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    try:
                        expiry = int(parts[4])
                        if expiry == 0:
                            valid_count += 1
                        elif expiry > now:
                            valid_count += 1
                            if nearest_expiry is None or expiry < nearest_expiry:
                                nearest_expiry = expiry
                        else:
                            expired_count += 1
                    except ValueError:
                        pass
    except Exception as e:
        return {"valid": False, "expired": False, "message": f"❌ Cookie parse error: {e}"}
    finally:
        try:
            os.remove(cookie_file)
        except Exception:
            pass

    if valid_count == 0 and expired_count > 0:
        return {
            "valid": False,
            "expired": True,
            "message": f"⚠️ All {expired_count} cookie entries are **expired**!\nPlease export fresh cookies from your browser."
        }
    elif valid_count > 0:
        expiry_str = ""
        if nearest_expiry:
            expiry_str = datetime.utcfromtimestamp(nearest_expiry).strftime("%Y-%m-%d")
        return {
            "valid": True,
            "expired": False,
            "message": f"✅ Cookies valid! `{valid_count}` active entries."
                       + (f"\n▸ Nearest expiry: `{expiry_str}`" if expiry_str else "")
        }
    else:
        return {"valid": False, "expired": False, "message": "❌ No valid cookie entries found."}


async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> Optional[str]:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-i", url,
        "-c", "copy",
        "-bsf:a", "aac_adtstoasc",
        out_file
    ]
    loop = asyncio.get_event_loop()

    def _run():
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg: {result.stderr[-300:]}")
        return out_file

    return await loop.run_in_executor(None, _run)


async def download_direct(
    url: str,
    out_dir: str,
    filename: str = None,
    progress_hook=None,
) -> Optional[str]:
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)
    if not filename:
        filename = url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4().hex[:8]}"
    filename = clean_filename(filename)
    out_file = os.path.join(out_dir, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3600)) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_hook:
                        await progress_hook(downloaded, total)
    return out_file


async def generate_thumbnail(video_path: str) -> Optional[str]:
    thumb_path = video_path.rsplit(".", 1)[0] + "_thumb.jpg"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", "00:00:01",
        "-vframes", "1",
        "-vf", "scale=320:-1",
        thumb_path
    ]
    loop = asyncio.get_event_loop()

    def _run():
        result = subprocess.run(cmd, capture_output=True)
        return thumb_path if result.returncode == 0 and os.path.exists(thumb_path) else None

    return await loop.run_in_executor(None, _run)


async def remux_video(input_path: str) -> str:
    if input_path.endswith(".mp4"):
        return input_path
    out_path = input_path.rsplit(".", 1)[0] + ".mp4"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", out_path]
    loop = asyncio.get_event_loop()

    def _run():
        subprocess.run(cmd, capture_output=True)
        return out_path if os.path.exists(out_path) else input_path

    return await loop.run_in_executor(None, _run)


def cleanup_files(*paths):
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
