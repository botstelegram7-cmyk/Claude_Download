"""
Serena Downloader Bot - Core Downloader
YouTube fix: exact method from working reference code
- format: best[ext=mp4]/best
- Chrome User-Agent header
- Direct proxy on each request
- No complex postprocessors
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile, json, requests
from typing import Optional, Callable

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import detect_url_type, clean_filename

os.makedirs(DL_DIR, exist_ok=True)

# Chrome User-Agent — same as working reference code
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"


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
                "message": f"⚠️ All **{expired}** entries are **expired**!"}
    elif valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ Valid! `{valid}` entries. Expiry: `{exp_str}`"}
    return {"valid": False, "expired": False, "message": "❌ No valid entries found."}


# ─────────────────────────────────────────
#  yt-dlp opts builders
# ─────────────────────────────────────────

def _yt_opts(out_dir: str, quality: str, audio_only: bool,
             cookie_file: Optional[str], hook, proxy: str) -> dict:
    """
    YouTube opts — based on working reference code.
    Key: best[ext=mp4]/best format + Chrome UA + proxy.
    No FFmpegMetadata, no complex merge — avoids postprocessing errors.
    """
    if audio_only:
        fmt = "bestaudio/best"
    else:
        q_map = {
            "144p":  "best[ext=mp4][height<=144]/best[height<=144]/best",
            "360p":  "best[ext=mp4][height<=360]/best[height<=360]/best",
            "720p":  "best[ext=mp4][height<=720]/best[height<=720]/best",
            "1080p": "best[ext=mp4][height<=1080]/best[height<=1080]/best",
            "best":  "best[ext=mp4]/best",
        }
        fmt = q_map.get(quality, "best[ext=mp4]/best")

    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": [],           # ← empty, no FFmpegMetadata
        "merge_output_format": "mp4",
        "retries": 10,
        "fragment_retries": 10,
        "sleep_interval": 1,
        "max_sleep_interval": 5,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},  # ← Chrome UA
    }

    if proxy:
        opts["proxy"] = proxy           # ← direct proxy

    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    if audio_only:
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio",
             "preferredcodec": "mp3",
             "preferredquality": "192"},
        ]

    if hook:
        opts["progress_hooks"] = [hook]

    return opts


def _generic_opts(out_dir: str, cookie_file: Optional[str], hook) -> dict:
    """For Instagram, TikTok, Twitter, Facebook, etc."""
    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 5,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


# ─────────────────────────────────────────
#  File finder — same logic as reference code
# ─────────────────────────────────────────

def _find_output_file(out_dir: str, info: dict, ydl) -> Optional[str]:
    if not info:
        return None
    # Try ydl prepared filename first
    try:
        filename = ydl.prepare_filename(info)
        if os.path.exists(filename) and os.path.getsize(filename) > 1000:
            return filename
        # Try alternate extensions — same as reference code
        base, _ = os.path.splitext(filename)
        for ext in ["mp4", "mkv", "webm", "mov", "mp3", "m4a"]:
            candidate = f"{base}.{ext}"
            if os.path.exists(candidate) and os.path.getsize(candidate) > 1000:
                return candidate
    except Exception:
        pass

    # Fallback: newest real file in dir
    try:
        skip = {".jpg", ".jpeg", ".png", ".webp", ".part", ".ytdl", ".tmp"}
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
#  Thumbnail download — same as reference code
# ─────────────────────────────────────────

def download_thumb_from_url(thumb_url: str, video_id: str) -> Optional[str]:
    """Download original thumbnail from URL — reference code method."""
    if not thumb_url:
        return None
    thumb_path = f"/tmp/thumb_{video_id}.jpg"
    try:
        resp = requests.get(
            thumb_url,
            headers={"User-Agent": CHROME_UA},
            timeout=10
        )
        if resp.status_code == 200 and len(resp.content) > 500:
            with open(thumb_path, "wb") as f:
                f.write(resp.content)
            return thumb_path
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
    import yt_dlp
    from config import YT_COOKIES, INSTAGRAM_COOKIES, TERABOX_COOKIES, YT_PROXY

    url_type = detect_url_type(url)
    os.makedirs(out_dir, exist_ok=True)
    loop = asyncio.get_event_loop()

    # ── Non-YouTube ──
    if url_type != "youtube":
        cookie_file = None
        if url_type == "instagram" and INSTAGRAM_COOKIES:
            cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
        elif url_type == "terabox" and TERABOX_COOKIES:
            cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb")

        opts = _generic_opts(out_dir, cookie_file, progress_hook)

        def _run_generic():
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None, None
                if "entries" in info:
                    results = []
                    for e in (info.get("entries") or []):
                        if e:
                            f = _find_output_file(out_dir, e, ydl)
                            if f:
                                results.append(f)
                    return results or None, info
                return _find_output_file(out_dir, info, ydl), info

        try:
            return await loop.run_in_executor(None, _run_generic)
        except Exception as e:
            raise RuntimeError(f"Download failed: {str(e)[:200]}")
        finally:
            if cookie_file and os.path.exists(cookie_file):
                try: os.remove(cookie_file)
                except: pass

    # ── YouTube — exact method from working reference ──
    cookie_file = _write_cookie_file(YT_COOKIES, "yt") if YT_COOKIES else None
    opts = _yt_opts(out_dir, quality, audio_only, cookie_file, progress_hook, YT_PROXY)

    def _run_yt():
        with yt_dlp.YoutubeDL(opts) as ydl:
            # Step 1: extract info only (check duration, get metadata)
            info = ydl.extract_info(url, download=False)
            if not info:
                raise RuntimeError("Could not extract video info.")

            # Step 2: download
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None

            if "entries" in info:
                results = []
                for e in (info.get("entries") or []):
                    if e:
                        f = _find_output_file(out_dir, e, ydl)
                        if f:
                            results.append(f)
                return results or None, info

            return _find_output_file(out_dir, info, ydl), info

    last_error = ""
    try:
        result, meta = await loop.run_in_executor(None, _run_yt)
        if result:
            return result, meta
        raise RuntimeError("File not found after download.")

    except Exception as e:
        last_error = str(e)

        # Retry with absolute fallback format if format error
        if "format" in last_error.lower() or "Postprocessing" in last_error:
            fallback = dict(opts)
            fallback["format"] = "best"
            fallback["postprocessors"] = []
            fallback.pop("progress_hooks", None)

            def _run_fallback():
                with yt_dlp.YoutubeDL(fallback) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return _find_output_file(out_dir, info, ydl) if info else None, info

            try:
                result2, meta2 = await loop.run_in_executor(None, _run_fallback)
                if result2:
                    return result2, meta2
            except Exception as e2:
                last_error = str(e2)

        # Friendly error messages
        if any(x in last_error for x in ["Sign in", "bot", "LOGIN_REQUIRED", "cookies"]):
            raise RuntimeError(
                "🍪 **YouTube requires cookies.**\n\n"
                "▸ Export cookies with **Get cookies.txt LOCALLY** browser extension\n"
                "▸ Set `YT_COOKIES` in Render Environment vars\n"
                "▸ Use `/cookies` to verify"
            )
        raise RuntimeError(f"YouTube download failed: {last_error[:250]}")

    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


# ─────────────────────────────────────────
#  Google Drive folder handler
# ─────────────────────────────────────────

async def download_gdrive_folder(
    url: str,
    out_dir: str,
    as_zip: bool = True,
    progress_hook: Optional[Callable] = None,
) -> tuple:
    """
    Download Google Drive folder contents.
    Returns (zip_path, meta) if as_zip=True
    Returns (list_of_files, meta) if as_zip=False
    """
    import yt_dlp
    os.makedirs(out_dir, exist_ok=True)
    loop = asyncio.get_event_loop()

    opts = {
        "format": "best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "retries": 5,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return [], info

            skip = {".part", ".ytdl", ".tmp"}
            files = [
                os.path.join(out_dir, x) for x in os.listdir(out_dir)
                if os.path.isfile(os.path.join(out_dir, x))
                and not any(x.endswith(e) for e in skip)
                and os.path.getsize(os.path.join(out_dir, x)) > 0
            ]
            return sorted(files, key=os.path.getmtime), info

    files, meta = await loop.run_in_executor(None, _run)
    return files, meta


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
                ["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                capture_output=True, text=True
            )
            duration = float(json.loads(r.stdout).get("format",{}).get("duration",0))
        except Exception:
            pass
        for seek in ([int(duration*p) for p in [0.1,0.2,0.3,0.5] if duration>5] + [5,3,1,0]):
            r = subprocess.run(
                ["ffmpeg","-y","-ss",str(seek),"-i",video_path,
                 "-vframes","1","-vf","scale=320:-1","-q:v","3",thumb_path],
                capture_output=True
            )
            if r.returncode==0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path)>3000:
                return thumb_path
        return None
    return await loop.run_in_executor(None, _run)


async def remux_to_mp4(input_path: str) -> str:
    out = input_path.rsplit(".", 1)[0] + "_tg.mp4"
    cmd = ["ffmpeg","-y","-i",input_path,"-c","copy","-movflags","+faststart",out]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode==0 and os.path.exists(out) and os.path.getsize(out)>1000:
            try: os.remove(input_path)
            except: pass
            return out
        return input_path
    return await loop.run_in_executor(None, _run)


def get_video_info(path: str) -> dict:
    try:
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_streams","-show_format","-select_streams","v:0",path],
            capture_output=True, text=True
        )
        data = json.loads(r.stdout)
        stream = (data.get("streams") or [{}])[0]
        duration = float(data.get("format",{}).get("duration",0))
        return {"width":stream.get("width",0),"height":stream.get("height",0),"duration":int(duration)}
    except Exception:
        return {"width":0,"height":0,"duration":0}


async def zip_folder(folder_path: str, out_path: str, name: str = "files") -> str:
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
