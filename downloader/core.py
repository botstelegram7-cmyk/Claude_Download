"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Core DL      ║
╚══════════════════════════════════════════╝
"""

import os
import asyncio
import subprocess
import uuid
from typing import Optional, Dict, Any, Callable
from config import DL_DIR
from utils.helpers import (
    get_yt_cookie_file, get_instagram_cookie_file,
    get_terabox_cookie_file, detect_url_type, clean_filename
)


os.makedirs(DL_DIR, exist_ok=True)

QUALITY_MAP = {
    "144p":  "bestvideo[height<=144]+bestaudio/best[height<=144]",
    "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]",
    "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "audio": "bestaudio/best",
    "best":  "bestvideo+bestaudio/best",
}


def _build_ydl_opts(
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    cookie_file: Optional[str] = None,
    progress_hook: Optional[Callable] = None,
) -> Dict[str, Any]:
    fmt = "bestaudio/best" if audio_only else QUALITY_MAP.get(quality, QUALITY_MAP["best"])
    opts: Dict[str, Any] = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "merge_output_format": "mp4",
        "writethumbnail": True,
        "postprocessors": [],
    }
    if audio_only:
        opts["postprocessors"].append({
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192",
        })
    if cookie_file:
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
    """Download URL using yt-dlp and return path to downloaded file."""
    import yt_dlp

    url_type = detect_url_type(url)
    cookie_file = None
    if url_type == "youtube":
        cookie_file = get_yt_cookie_file()
    elif url_type == "instagram":
        cookie_file = get_instagram_cookie_file()
    elif url_type == "terabox":
        cookie_file = get_terabox_cookie_file()

    os.makedirs(out_dir, exist_ok=True)
    opts = _build_ydl_opts(out_dir, quality, audio_only, cookie_file, progress_hook)

    loop = asyncio.get_event_loop()

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info:
                # Handle playlists
                if "entries" in info:
                    files = []
                    for entry in info["entries"]:
                        if entry:
                            f = ydl.prepare_filename(entry)
                            # Try mp4 extension too
                            for ext in [f, f.replace(".webm", ".mp4"), f.replace(".mkv", ".mp4")]:
                                if os.path.exists(ext):
                                    files.append(ext)
                                    break
                    return files if files else None
                else:
                    f = ydl.prepare_filename(info)
                    for ext_try in [f, f.replace(".webm", ".mp4"), f.replace(".mkv", ".mp4")]:
                        if os.path.exists(ext_try):
                            return ext_try
                    # Search directory for recently created file
                    files = sorted(
                        [os.path.join(out_dir, x) for x in os.listdir(out_dir)],
                        key=os.path.getmtime, reverse=True
                    )
                    return files[0] if files else None
        return None

    try:
        result = await loop.run_in_executor(None, _download)
        return result
    except Exception as e:
        raise RuntimeError(f"yt-dlp error: {e}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try:
                os.remove(cookie_file)
            except Exception:
                pass


async def download_m3u8(
    url: str,
    out_dir: str,
    progress_hook: Optional[Callable] = None,
) -> Optional[str]:
    """Download M3U8 stream using ffmpeg."""
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
            raise RuntimeError(f"ffmpeg error: {result.stderr}")
        return out_file

    return await loop.run_in_executor(None, _run)


async def download_direct(
    url: str,
    out_dir: str,
    filename: str = None,
    progress_hook: Optional[Callable] = None,
) -> Optional[str]:
    """Download direct file URL using aiohttp."""
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    if not filename:
        filename = url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4().hex[:8]}"
    filename = clean_filename(filename)
    out_file = os.path.join(out_dir, filename)

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(1024 * 64):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_hook and total:
                        await progress_hook(downloaded, total)
    return out_file


async def generate_thumbnail(video_path: str) -> Optional[str]:
    """Generate thumbnail from video using ffmpeg."""
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
        return thumb_path if result.returncode == 0 else None

    return await loop.run_in_executor(None, _run)


async def remux_video(input_path: str) -> str:
    """Remux video to mp4 using ffmpeg."""
    if input_path.endswith(".mp4"):
        return input_path
    out_path = input_path.rsplit(".", 1)[0] + ".mp4"
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-c", "copy",
        out_path
    ]
    loop = asyncio.get_event_loop()

    def _run():
        subprocess.run(cmd, capture_output=True)
        return out_path if os.path.exists(out_path) else input_path

    return await loop.run_in_executor(None, _run)


def cleanup_files(*paths):
    """Delete temp files."""
    for path in paths:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass
