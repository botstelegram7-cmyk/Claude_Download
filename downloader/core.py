"""
Serena Downloader Bot - Core Downloader
Fixes:
  - Postprocessing error: removed FFmpegMetadata from non-audio pipeline
  - YouTube format: uses recommended format string from community
  - Proxy support for Render IP blocks
  - Cookie multiline fix for Render env vars
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile, json
from typing import Optional, Callable

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import detect_url_type, clean_filename

os.makedirs(DL_DIR, exist_ok=True)


# ─────────────────────────────────────────
#  Cookie helpers
# ─────────────────────────────────────────

def _fix_cookie_str(raw: str) -> str:
    """Render env vars store newlines as literal \\n — fix them."""
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
                "message": "❌ `YT_COOKIES` env variable is **not set**."}
    path = _write_cookie_file(YT_COOKIES, "yt_check")
    if not path:
        return {"valid": False, "expired": False,
                "message": "❌ Failed to parse cookie content."}
    now = int(time.time())
    valid = expired = 0
    nearest = None
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
                "message": f"⚠️ All **{expired}** entries are **expired**! Export fresh cookies."}
    elif valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ Valid! `{valid}` active entries. Nearest expiry: `{exp_str}`"}
    return {"valid": False, "expired": False,
            "message": "❌ No valid cookie entries found."}


# ─────────────────────────────────────────
#  yt-dlp format strategy
# ─────────────────────────────────────────

def _get_ydl_opts(
    out_dir: str,
    quality: str,
    audio_only: bool,
    url_type: str,
    cookie_file: Optional[str],
    progress_hook: Optional[Callable],
) -> dict:
    """
    Build yt-dlp options.
    Key fix: do NOT use FFmpegMetadata postprocessor for video —
    it causes "Error opening input files: Invalid data found" on Render.
    """
    from config import YT_PROXY

    outtmpl = os.path.join(out_dir, "%(title).80s.%(ext)s")

    if audio_only:
        fmt = "bestaudio/best"
        postprocessors = [
            {"key": "FFmpegExtractAudio",
             "preferredcodec": "mp3",
             "preferredquality": "192"},
        ]
    elif url_type in ("instagram","tiktok","twitter","facebook","terabox","generic","gdrive"):
        # Simple format — these platforms don't support complex strings
        fmt = "best[ext=mp4]/best"
        postprocessors = []
    else:
        # YouTube / general video — community-recommended format that avoids
        # "Requested format is not available" on Render IPs
        q_map = {
            "144p":  "bestvideo[height<=144]+bestaudio/best[height<=144]/best",
            "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
            "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
            "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
            "best":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        }
        fmt = q_map.get(quality, q_map["best"])
        postprocessors = []  # ← NO FFmpegMetadata here — causes postprocessing error

    opts = {
        "format": fmt,
        "outtmpl": outtmpl,
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": postprocessors,
        # Reliability settings
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 3,
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        "socket_timeout": 30,
        "http_chunk_size": 10485760,  # 10MB chunks
        # Fix for Render servers — use Android client to bypass bot detection
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web"],
                "skip": ["hls", "dash"],
            }
        },
    }

    # Proxy (important for Render IPs blocked by YouTube)
    if YT_PROXY and url_type == "youtube":
        opts["proxy"] = YT_PROXY

    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    return opts


def _find_output_file(out_dir: str, info: dict, ydl) -> Optional[str]:
    """Find the actual downloaded file robustly."""
    if not info:
        return None
    try:
        f = ydl.prepare_filename(info)
        candidates = [
            f,
            f.replace(".webm", ".mp4"),
            f.replace(".mkv", ".mp4"),
            f.replace(".opus", ".mp3"),
            f.replace(".m4a", ".mp3"),
        ]
        for c in candidates:
            if os.path.exists(c) and os.path.getsize(c) > 1000:
                return c
    except Exception:
        pass

    # Fallback: newest non-thumbnail file in dir
    try:
        skip_exts = {".jpg", ".jpeg", ".png", ".webp", ".part", ".ytdl"}
        files = [
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip_exts)
            and os.path.getsize(os.path.join(out_dir, x)) > 1000
        ]
        if files:
            return max(files, key=os.path.getmtime)
    except Exception:
        pass
    return None


# ─────────────────────────────────────────
#  Main download function
# ─────────────────────────────────────────

async def download_with_ytdlp(
    url: str,
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    progress_hook: Optional[Callable] = None,
) -> tuple:
    """Returns (file_path_or_list, meta_dict)."""
    import yt_dlp
    from config import YT_COOKIES, INSTAGRAM_COOKIES, TERABOX_COOKIES

    url_type = detect_url_type(url)
    cookie_file = None

    if url_type == "youtube" and YT_COOKIES:
        cookie_file = _write_cookie_file(YT_COOKIES, "yt")
    elif url_type == "instagram" and INSTAGRAM_COOKIES:
        cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
    elif url_type == "terabox" and TERABOX_COOKIES:
        cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb")

    os.makedirs(out_dir, exist_ok=True)
    opts = _get_ydl_opts(out_dir, quality, audio_only, url_type, cookie_file, progress_hook)
    loop = asyncio.get_event_loop()

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None
            # Playlist
            if "entries" in info:
                results = []
                for entry in (info.get("entries") or []):
                    if not entry:
                        continue
                    f = _find_output_file(out_dir, entry, ydl)
                    if f:
                        results.append(f)
                return results if results else None, info
            # Single
            return _find_output_file(out_dir, info, ydl), info

    try:
        result, meta = await loop.run_in_executor(None, _run)
        return result, meta

    except Exception as e:
        err = str(e)

        # ── Cookie / bot detection error ──
        if any(x in err for x in ["Sign in to confirm", "bot", "cookies", "LOGIN_REQUIRED"]):
            raise RuntimeError(
                "🍪 **YouTube Cookie Required**\n\n"
                "▸ Export cookies from your browser (Get cookies.txt LOCALLY extension)\n"
                "▸ Set `YT_COOKIES` in Render env vars\n"
                "▸ Use `/cookies` to check status"
            )

        # ── Format not available — retry with absolute fallback ──
        if "Requested format is not available" in err or "Postprocessing" in err:
            fallback_opts = dict(opts)
            fallback_opts["format"] = "best"
            fallback_opts["postprocessors"] = []
            fallback_opts.pop("progress_hooks", None)
            def _fallback():
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return _find_output_file(out_dir, info, ydl) if info else None, info
            try:
                result2, meta2 = await loop.run_in_executor(None, _fallback)
                if result2:
                    return result2, meta2
            except Exception:
                pass
            raise RuntimeError(
                "❌ Format not available for this URL.\n\n"
                "▸ Try `/formats [url]` to see what's available\n"
                "▸ For YouTube: add `YT_PROXY` env var (Render IP may be blocked)"
            )

        raise RuntimeError(f"Download failed: {err[:300]}")

    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


# ─────────────────────────────────────────
#  M3U8 / Direct / Thumbnail / Utils
# ─────────────────────────────────────────

async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> tuple:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    cmd = ["ffmpeg","-y","-i",url,"-c","copy","-bsf:a","aac_adtstoasc",out_file]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg m3u8 error: {r.stderr[-200:]}")
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
    """Find yt-dlp written thumbnail next to video file."""
    for ext in (".jpg", ".jpeg", ".webp", ".png"):
        t = base_path.rsplit(".", 1)[0] + ext
        if os.path.exists(t) and os.path.getsize(t) > 500:
            # Convert webp/png to jpg for Telegram
            if not t.endswith(".jpg"):
                jpg = t.rsplit(".", 1)[0] + ".jpg"
                r = subprocess.run(["ffmpeg","-y","-i",t,jpg], capture_output=True)
                if r.returncode == 0 and os.path.exists(jpg):
                    try: os.remove(t)
                    except: pass
                    return jpg
            return t
    return None


async def generate_thumbnail(video_path: str) -> Optional[str]:
    """Generate thumbnail avoiding black/white frames by seeking to 10-30% of duration."""
    thumb_path = video_path.rsplit(".", 1)[0] + "_thumb.jpg"
    loop = asyncio.get_event_loop()

    def _run():
        # Get video duration
        duration = 0
        try:
            r = subprocess.run(
                ["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                capture_output=True, text=True
            )
            data = json.loads(r.stdout)
            duration = float(data.get("format",{}).get("duration", 0))
        except Exception:
            pass

        # Try multiple seek points to find a good frame
        seek_points = []
        if duration > 10:
            seek_points = [
                int(duration * 0.1),
                int(duration * 0.2),
                int(duration * 0.3),
                int(duration * 0.5),
                5, 3, 1
            ]
        else:
            seek_points = [1, 0]

        for seek in seek_points:
            r = subprocess.run(
                ["ffmpeg", "-y",
                 "-ss", str(seek),
                 "-i", video_path,
                 "-vframes", "1",
                 "-vf", "scale=320:-1",
                 "-q:v", "3",
                 thumb_path],
                capture_output=True
            )
            if r.returncode == 0 and os.path.exists(thumb_path):
                size = os.path.getsize(thumb_path)
                if size > 3000:  # must be a real image, not blank
                    return thumb_path
        return None

    return await loop.run_in_executor(None, _run)


async def remux_to_mp4(input_path: str) -> str:
    """Remux to streamable MP4 with faststart flag for Telegram."""
    out = input_path.rsplit(".", 1)[0] + "_tg.mp4"
    cmd = ["ffmpeg", "-y", "-i", input_path, "-c", "copy", "-movflags", "+faststart", out]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0 and os.path.exists(out) and os.path.getsize(out) > 1000:
            try: os.remove(input_path)
            except: pass
            return out
        return input_path
    return await loop.run_in_executor(None, _run)


def get_video_info(path: str) -> dict:
    """Return width, height, duration of a video file."""
    try:
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_streams","-show_format","-select_streams","v:0", path],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        stream = (data.get("streams") or [{}])[0]
        duration = float(data.get("format",{}).get("duration", 0))
        return {
            "width": stream.get("width", 0),
            "height": stream.get("height", 0),
            "duration": int(duration),
        }
    except Exception:
        return {"width": 0, "height": 0, "duration": 0}


async def zip_folder(folder_path: str, out_path: str, name: str = "playlist") -> str:
    zip_path = os.path.join(out_path, f"{clean_filename(name)}.zip")
    loop = asyncio.get_event_loop()
    def _zip():
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(folder_path):
                fp = os.path.join(folder_path, fname)
                if os.path.isfile(fp) and not fname.endswith((".part",".ytdl")):
                    zf.write(fp, fname)
        return zip_path
    return await loop.run_in_executor(None, _zip)


def cleanup_files(*paths):
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p):
                os.remove(p)
        except Exception:
            pass
