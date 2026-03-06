"""
Serena Downloader Bot - Core Downloader
Fix: YouTube bot detection bypass using android client + po_token workaround
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
#  yt-dlp option builders
# ─────────────────────────────────────────

def _base_opts(out_dir: str, fmt: str, postprocessors: list) -> dict:
    from config import YT_PROXY
    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": postprocessors,
        "retries": 10,
        "fragment_retries": 10,
        "file_access_retries": 3,
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        "socket_timeout": 30,
        "http_chunk_size": 10485760,
    }
    if YT_PROXY:
        opts["proxy"] = YT_PROXY
    return opts


def _yt_opts_android(out_dir: str, fmt: str, cookie_file: Optional[str], hook) -> dict:
    """
    Strategy 1: Android client — bypasses bot detection without cookies.
    This is the most reliable method on server IPs.
    """
    opts = _base_opts(out_dir, fmt, [])
    opts["extractor_args"] = {
        "youtube": {
            "player_client": ["android"],
            "player_skip": ["webpage", "configs"],
        }
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


def _yt_opts_tv(out_dir: str, fmt: str, cookie_file: Optional[str], hook) -> dict:
    """
    Strategy 2: TV embedded client — another bypass method.
    """
    opts = _base_opts(out_dir, fmt, [])
    opts["extractor_args"] = {
        "youtube": {
            "player_client": ["tv_embedded"],
            "player_skip": ["webpage"],
        }
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


def _yt_opts_web(out_dir: str, fmt: str, cookie_file: Optional[str], hook) -> dict:
    """
    Strategy 3: Web client with cookies — needs valid cookies.
    """
    opts = _base_opts(out_dir, fmt, [])
    opts["extractor_args"] = {
        "youtube": {
            "player_client": ["web"],
        }
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


def _generic_opts(out_dir: str, hook) -> dict:
    """For non-YouTube platforms."""
    opts = _base_opts(out_dir, "best[ext=mp4]/best", [])
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


def _get_quality_fmt(quality: str) -> str:
    q_map = {
        "144p":  "bestvideo[height<=144]+bestaudio/best[height<=144]/best",
        "360p":  "bestvideo[height<=360]+bestaudio/best[height<=360]/best",
        "720p":  "bestvideo[height<=720]+bestaudio/best[height<=720]/best",
        "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "audio": "bestaudio/best",
        "best":  "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
    }
    return q_map.get(quality, q_map["best"])


# ─────────────────────────────────────────
#  File finder
# ─────────────────────────────────────────

def _find_output_file(out_dir: str, info: dict, ydl) -> Optional[str]:
    if not info:
        return None
    try:
        f = ydl.prepare_filename(info)
        for candidate in [f, f.replace(".webm",".mp4"), f.replace(".mkv",".mp4"), f.replace(".opus",".mp3")]:
            if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                return candidate
    except Exception:
        pass
    # Fallback: newest real file in dir
    try:
        skip = {".jpg",".jpeg",".png",".webp",".part",".ytdl",".tmp"}
        files = [
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip)
            and os.path.getsize(os.path.join(out_dir, x)) > 1000
        ]
        if files:
            return max(files, key=os.path.getmtime)
    except Exception:
        pass
    return None


# ─────────────────────────────────────────
#  Main download — multi-strategy for YouTube
# ─────────────────────────────────────────

async def download_with_ytdlp(
    url: str,
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    progress_hook: Optional[Callable] = None,
) -> tuple:
    import yt_dlp
    from config import YT_COOKIES, INSTAGRAM_COOKIES, TERABOX_COOKIES

    url_type = detect_url_type(url)
    os.makedirs(out_dir, exist_ok=True)
    loop = asyncio.get_event_loop()

    # ── Non-YouTube platforms ──
    if url_type not in ("youtube",):
        cookie_file = None
        if url_type == "instagram" and INSTAGRAM_COOKIES:
            cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
        elif url_type == "terabox" and TERABOX_COOKIES:
            cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb")

        opts = _generic_opts(out_dir, progress_hook)
        if cookie_file:
            opts["cookiefile"] = cookie_file

        def _run_generic():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None, None
                if "entries" in info:
                    results = [_find_output_file(out_dir, e, ydl) for e in (info.get("entries") or []) if e]
                    return [r for r in results if r], info
                return _find_output_file(out_dir, info, ydl), info

        try:
            result, meta = await loop.run_in_executor(None, _run_generic)
            return result, meta
        except Exception as e:
            raise RuntimeError(f"Download failed: {str(e)[:200]}")
        finally:
            if cookie_file and os.path.exists(cookie_file):
                try: os.remove(cookie_file)
                except: pass

    # ── YouTube — try multiple strategies ──
    fmt = "bestaudio/best" if audio_only else _get_quality_fmt(quality)

    # Get cookie file if available
    cookie_file = None
    if YT_COOKIES:
        cookie_file = _write_cookie_file(YT_COOKIES, "yt")

    # Define strategies in order of preference
    strategies = [
        ("android client",     _yt_opts_android(out_dir, fmt, cookie_file, progress_hook)),
        ("tv_embedded client", _yt_opts_tv(out_dir, fmt, cookie_file, progress_hook)),
        ("web + cookies",      _yt_opts_web(out_dir, fmt, cookie_file, progress_hook)),
        ("best fallback",      {**_base_opts(out_dir, "best", []), **({"cookiefile": cookie_file} if cookie_file else {})}),
    ]

    last_error = ""
    for strategy_name, opts in strategies:
        def _make_runner(o):
            def _run():
                with yt_dlp.YoutubeDL(o) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if not info:
                        return None, None
                    if "entries" in info:
                        results = [_find_output_file(out_dir, e, ydl) for e in (info.get("entries") or []) if e]
                        return [r for r in results if r], info
                    return _find_output_file(out_dir, info, ydl), info
            return _run

        try:
            result, meta = await loop.run_in_executor(None, _make_runner(opts))
            if result:
                return result, meta
        except Exception as e:
            last_error = str(e)
            # Only continue to next strategy on bot-detection / format errors
            if any(x in last_error for x in [
                "Sign in", "bot", "cookies", "LOGIN_REQUIRED",
                "format is not available", "Postprocessing"
            ]):
                continue
            # Other errors (network, etc.) — still try next
            continue

    # All strategies failed
    if cookie_file and os.path.exists(cookie_file):
        try: os.remove(cookie_file)
        except: pass

    if "Sign in" in last_error or "bot" in last_error.lower() or "LOGIN_REQUIRED" in last_error:
        raise RuntimeError(
            "🍪 **YouTube bot detection triggered.**\n\n"
            "▸ Proxy is set ✅\n"
            "▸ But YouTube still requires cookies from a logged-in browser.\n\n"
            "**Fix:** Export cookies using **Get cookies.txt LOCALLY** extension\n"
            "→ Set `YT_COOKIES` env var on Render\n"
            "→ Use `/cookies` command to verify"
        )

    raise RuntimeError(
        f"❌ All download strategies failed.\n\n"
        f"Last error: `{last_error[:200]}`\n\n"
        f"▸ Try `/formats [url]` to check availability\n"
        f"▸ Make sure `YT_PROXY` and `YT_COOKIES` are both set"
    )


# ─────────────────────────────────────────
#  M3U8 / Direct download
# ─────────────────────────────────────────

async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> tuple:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    cmd = ["ffmpeg","-y","-i",url,"-c","copy","-bsf:a","aac_adtstoasc",out_file]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg error: {r.stderr[-200:]}")
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


# ─────────────────────────────────────────
#  Thumbnail / Video utils
# ─────────────────────────────────────────

def find_thumbnail(base_path: str) -> Optional[str]:
    for ext in (".jpg", ".jpeg", ".webp", ".png"):
        t = base_path.rsplit(".", 1)[0] + ext
        if os.path.exists(t) and os.path.getsize(t) > 500:
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
    thumb_path = video_path.rsplit(".", 1)[0] + "_thumb.jpg"
    loop = asyncio.get_event_loop()
    def _run():
        duration = 0
        try:
            r = subprocess.run(
                ["ffprobe","-v","quiet","-print_format","json","-show_format", video_path],
                capture_output=True, text=True
            )
            duration = float(json.loads(r.stdout).get("format",{}).get("duration", 0))
        except Exception:
            pass
        seek_points = [int(duration*p) for p in [0.1,0.2,0.3,0.5] if duration > 5] + [5, 3, 1, 0]
        for seek in seek_points:
            r = subprocess.run(
                ["ffmpeg","-y","-ss",str(seek),"-i",video_path,
                 "-vframes","1","-vf","scale=320:-1","-q:v","3", thumb_path],
                capture_output=True
            )
            if r.returncode == 0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 3000:
                return thumb_path
        return None
    return await loop.run_in_executor(None, _run)


async def remux_to_mp4(input_path: str) -> str:
    out = input_path.rsplit(".", 1)[0] + "_tg.mp4"
    cmd = ["ffmpeg","-y","-i",input_path,"-c","copy","-movflags","+faststart",out]
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
    try:
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_streams","-show_format","-select_streams","v:0", path],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        stream = (data.get("streams") or [{}])[0]
        duration = float(data.get("format",{}).get("duration", 0))
        return {"width": stream.get("width",0), "height": stream.get("height",0), "duration": int(duration)}
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
        if not p: continue
        try:
            if os.path.isdir(p): shutil.rmtree(p, ignore_errors=True)
            elif os.path.exists(p): os.remove(p)
        except Exception:
            pass
