"""
Serena Downloader Bot - Core Downloader
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile
from typing import Optional, Callable

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import (
    get_yt_cookie_file, get_instagram_cookie_file,
    get_terabox_cookie_file, detect_url_type, clean_filename
)

os.makedirs(DL_DIR, exist_ok=True)

# ── Smart format selection ──
def _get_format(quality: str, url_type: str, audio_only: bool) -> str:
    if audio_only:
        return "bestaudio/best"
    if url_type in ("instagram","tiktok","twitter","facebook","terabox","generic","gdrive"):
        return "best"
    # YouTube and similar — progressive fallback chain
    q_map = {
        "144p":  "bestvideo[height<=144][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=144]+bestaudio/best[height<=144]/best",
        "360p":  "bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        "720p":  "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "1080p": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best",
    }
    return q_map.get(quality, q_map["best"])


def _fix_cookie_str(raw: str) -> str:
    """Fix Render env literal \\n -> real newlines."""
    if not raw:
        return ""
    raw = raw.strip().strip('"').strip("'")
    raw = raw.replace("\\n", "\n").replace("\\t", "\t")
    return raw


def _write_cookie_file(raw: str, prefix: str) -> Optional[str]:
    content = _fix_cookie_str(raw)
    if not content:
        return None
    try:
        import tempfile
        tf = tempfile.NamedTemporaryFile(
            mode="w", prefix=f"{prefix}_", suffix=".txt",
            delete=False, dir="/tmp"
        )
        if "# Netscape" not in content:
            tf.write("# Netscape HTTP Cookie File\n")
        tf.write(content + "\n")
        tf.close()
        return tf.name
    except Exception:
        return None


def _validate_cookie_file(path: str) -> bool:
    """Return True if file has at least one non-expired cookie."""
    if not path or not os.path.exists(path):
        return False
    now = int(time.time())
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    try:
                        exp = int(parts[4])
                        if exp == 0 or exp > now:
                            return True
                    except ValueError:
                        pass
    except Exception:
        pass
    return False


async def check_yt_cookies_status() -> dict:
    from config import YT_COOKIES
    from datetime import datetime
    if not YT_COOKIES or not YT_COOKIES.strip():
        return {"valid": False, "expired": False,
                "message": "❌ `YT_COOKIES` env variable is **not set**.\n\nAdd it on Render Dashboard → Environment."}
    path = _write_cookie_file(YT_COOKIES, "yt_check")
    if not path:
        return {"valid": False, "expired": False, "message": "❌ Failed to parse cookie content."}
    now = int(time.time())
    valid, expired, nearest = 0, 0, None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    try:
                        exp = int(parts[4])
                        if exp == 0:
                            valid += 1
                        elif exp > now:
                            valid += 1
                            if nearest is None or exp < nearest:
                                nearest = exp
                        else:
                            expired += 1
                    except ValueError:
                        pass
    finally:
        try: os.remove(path)
        except: pass
    if valid == 0 and expired > 0:
        return {"valid": False, "expired": True,
                "message": f"⚠️ All **{expired}** cookie entries are **expired**!\n\nPlease export fresh cookies from your browser and update `YT_COOKIES` in Render env vars."}
    elif valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ Cookies are **valid**! `{valid}` active entries.\n{'' if not nearest else f'▸ Nearest expiry: `{exp_str}`'}"}
    return {"valid": False, "expired": False, "message": "❌ No valid cookie entries found in the file."}


async def download_with_ytdlp(
    url: str, out_dir: str, quality: str = "best",
    audio_only: bool = False, progress_hook=None,
) -> Optional[str]:
    import yt_dlp

    url_type = detect_url_type(url)
    cookie_file = None

    # Get cookies
    from config import YT_COOKIES, INSTAGRAM_COOKIES, TERABOX_COOKIES
    if url_type == "youtube" and YT_COOKIES:
        cookie_file = _write_cookie_file(YT_COOKIES, "yt")
        if not _validate_cookie_file(cookie_file):
            # cookies exist but invalid/expired — still try, yt-dlp will warn
            pass
    elif url_type == "instagram" and INSTAGRAM_COOKIES:
        cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
    elif url_type == "terabox" and TERABOX_COOKIES:
        cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb")

    os.makedirs(out_dir, exist_ok=True)
    fmt = _get_format(quality, url_type, audio_only)

    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "merge_output_format": "mp4",
        # Write original thumbnail
        "writethumbnail": True,
        "postprocessors": [
            {"key": "FFmpegMetadata"},  # embed metadata
        ],
        "retries": 5,
        "fragment_retries": 5,
        "sleep_interval": 1,
        "max_sleep_interval": 3,
        "socket_timeout": 30,
    }

    if audio_only:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata"},
        ]
        opts["writethumbnail"] = True

    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    loop = asyncio.get_event_loop()

    def _get_file(info, ydl):
        if not info:
            return None
        f = ydl.prepare_filename(info)
        # Try multiple extensions
        candidates = [f, f.replace(".webm",".mp4"), f.replace(".mkv",".mp4"), f.replace(".opus",".mp3")]
        for c in candidates:
            if os.path.exists(c):
                return c
        # Newest non-thumbnail file in dir
        all_f = sorted(
            [os.path.join(out_dir, x) for x in os.listdir(out_dir)
             if os.path.isfile(os.path.join(out_dir, x))
             and not x.endswith((".jpg",".png",".webp",".part"))],
            key=os.path.getmtime, reverse=True
        )
        return all_f[0] if all_f else None

    def _download():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None
            if "entries" in info:
                results = []
                for entry in (info["entries"] or []):
                    if entry:
                        f = _get_file(entry, ydl)
                        if f:
                            results.append((f, entry))
                return results, None
            return _get_file(info, ydl), info

    try:
        result, meta = await loop.run_in_executor(None, _download)
        return result, meta
    except Exception as e:
        err = str(e)
        if "Sign in to confirm" in err or "bot" in err.lower():
            raise RuntimeError(
                "🍪 **YouTube Cookie Error**\n\n"
                "▸ Your cookies are expired or not set correctly.\n"
                "▸ Use `/cookies` to check status.\n"
                "▸ Export fresh cookies from browser → update `YT_COOKIES` on Render."
            )
        if "Requested format is not available" in err:
            # Hard fallback
            opts2 = dict(opts)
            opts2["format"] = "best"
            opts2.pop("progress_hooks", None)
            def _fallback():
                with yt_dlp.YoutubeDL(opts2) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return _get_file(info, ydl) if info else None, info
            try:
                result2, meta2 = await loop.run_in_executor(None, _fallback)
                return result2, meta2
            except Exception as e2:
                raise RuntimeError(f"yt-dlp error: {e2}")
        raise RuntimeError(f"yt-dlp error: {err}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> tuple:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    cmd = ["ffmpeg","-y","-i",url,"-c","copy","-bsf:a","aac_adtstoasc",out_file]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg: {r.stderr[-300:]}")
        return out_file
    return await loop.run_in_executor(None, _run), None


async def download_direct(url: str, out_dir: str, filename=None, progress_hook=None) -> tuple:
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
            done = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk)
                    done += len(chunk)
                    if progress_hook:
                        await progress_hook(done, total)
    return out_file, None


def find_thumbnail(base_path: str) -> Optional[str]:
    """
    Find yt-dlp downloaded thumbnail or generate a good one via ffmpeg.
    Skips black/near-black frames by seeking to 10% of duration.
    """
    # Check for yt-dlp written thumbnail
    for ext in (".jpg", ".webp", ".png"):
        t = base_path.rsplit(".", 1)[0] + ext
        if os.path.exists(t) and os.path.getsize(t) > 1000:
            # Convert to jpg if needed
            if not t.endswith(".jpg"):
                jpg = t.rsplit(".", 1)[0] + ".jpg"
                subprocess.run(["ffmpeg","-y","-i",t,jpg], capture_output=True)
                if os.path.exists(jpg):
                    try: os.remove(t)
                    except: pass
                    return jpg
            return t
    return None


async def generate_thumbnail(video_path: str) -> Optional[str]:
    """Generate thumbnail avoiding black frames — seek to ~10% of video duration."""
    thumb_path = video_path.rsplit(".", 1)[0] + "_thumb.jpg"
    loop = asyncio.get_event_loop()

    def _run():
        # Get duration first
        probe = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
            capture_output=True, text=True
        )
        duration = 0
        try:
            import json
            info = json.loads(probe.stdout)
            duration = float(info.get("format", {}).get("duration", 0))
        except Exception:
            pass
        seek = max(1, int(duration * 0.1)) if duration > 5 else 1

        # Try multiple seek points to avoid black frames
        for seek_sec in [seek, int(duration*0.2), int(duration*0.3), 3, 1]:
            if seek_sec < 0:
                continue
            result = subprocess.run(
                ["ffmpeg","-y","-ss",str(seek_sec),"-i",video_path,
                 "-vframes","1","-vf","scale=320:-1","-q:v","2",thumb_path],
                capture_output=True
            )
            if result.returncode == 0 and os.path.exists(thumb_path):
                size = os.path.getsize(thumb_path)
                if size > 2000:  # valid image
                    return thumb_path
        return None

    return await loop.run_in_executor(None, _run)


async def remux_to_mp4(input_path: str) -> str:
    """Remux to streamable MP4 with faststart for Telegram."""
    if input_path.endswith(".mp4"):
        # Re-mux anyway to ensure faststart (playable on Telegram)
        out = input_path.replace(".mp4", "_stream.mp4")
    else:
        out = input_path.rsplit(".", 1)[0] + ".mp4"
    cmd = [
        "ffmpeg","-y","-i",input_path,
        "-c","copy",
        "-movflags","+faststart",  # makes MP4 streamable
        out
    ]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(out):
            try: os.remove(input_path)
            except: pass
            return out
        return input_path
    return await loop.run_in_executor(None, _run)


def get_video_dimensions(path: str) -> tuple:
    """Return (width, height, duration) of video."""
    try:
        result = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_streams","-select_streams","v:0",path],
            capture_output=True, text=True
        )
        import json
        data = json.loads(result.stdout)
        stream = data["streams"][0]
        w = stream.get("width", 0)
        h = stream.get("height", 0)
        # Duration
        dur_result = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json","-show_format",path],
            capture_output=True, text=True
        )
        dur_data = json.loads(dur_result.stdout)
        dur = int(float(dur_data.get("format",{}).get("duration",0)))
        return w, h, dur
    except Exception:
        return 0, 0, 0


async def zip_folder(folder_path: str, out_dir: str, name: str = "playlist") -> str:
    """Zip a folder of downloaded files."""
    zip_path = os.path.join(out_dir, f"{clean_filename(name)}.zip")
    loop = asyncio.get_event_loop()
    def _zip():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(folder_path):
                fpath = os.path.join(folder_path, fname)
                if os.path.isfile(fpath):
                    zf.write(fpath, fname)
        return zip_path
    return await loop.run_in_executor(None, _zip)


def cleanup_files(*paths):
    for p in paths:
        if p and os.path.exists(p):
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
            except Exception:
                pass
