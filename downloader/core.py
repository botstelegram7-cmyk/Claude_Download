"""
Serena Downloader Bot - Core Downloader
ROOT FIX:
  - YouTube: Use yt-dlp with multiple client strategies that bypass bot detection WITHOUT cookies
  - Direct links: Proper headers to avoid 403
  - Generic URLs: aiohttp with browser headers as fallback
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile, json
from typing import Optional, Callable

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import detect_url_type, clean_filename

os.makedirs(DL_DIR, exist_ok=True)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)


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


async def check_yt_cookies_status() -> dict:
    from config import YT_COOKIES
    from datetime import datetime
    if not YT_COOKIES or not YT_COOKIES.strip():
        return {"valid": False, "expired": False,
                "message": "❌ `YT_COOKIES` is **not set** in environment."}
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
                "message": f"⚠️ All **{expired}** entries **expired**! Export fresh cookies."}
    elif valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ Valid! `{valid}` entries. Expiry: `{exp_str}`"}
    return {"valid": False, "expired": False, "message": "❌ No valid entries found."}


# ─────────────────────────────────────────
#  File finder
# ─────────────────────────────────────────

def _find_file(out_dir: str, info: dict, ydl) -> Optional[str]:
    skip = {".jpg",".jpeg",".png",".webp",".part",".ytdl",".tmp"}
    if info:
        try:
            f = ydl.prepare_filename(info)
            base = os.path.splitext(f)[0]
            for candidate in [f] + [f"{base}.{e}" for e in ["mp4","mkv","webm","mov","mp3","m4a"]]:
                if os.path.exists(candidate) and os.path.getsize(candidate) > 500:
                    return candidate
        except Exception:
            pass
    # newest file in dir
    try:
        files = [
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip)
            and os.path.getsize(os.path.join(out_dir, x)) > 500
        ]
        return max(files, key=os.path.getmtime) if files else None
    except Exception:
        return None


# ─────────────────────────────────────────
#  YouTube download — multi-client strategy
# ─────────────────────────────────────────

def _make_yt_opts(out_dir, fmt, proxy, cookie_file, hook, client_name):
    """Each strategy tries a different yt-dlp client."""
    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if proxy:
        opts["proxy"] = proxy

    # Client-specific extractor args
    client_map = {
        "android":     {"player_client": ["android"],        "player_skip": ["webpage","configs"]},
        "android_vr":  {"player_client": ["android_vr"],     "player_skip": ["webpage","configs"]},
        "tv_embedded": {"player_client": ["tv_embedded"],    "player_skip": ["webpage"]},
        "ios":         {"player_client": ["ios"],            "player_skip": ["webpage","configs"]},
        "mweb":        {"player_client": ["mweb"]},
        "web":         {"player_client": ["web"]},
    }
    if client_name in client_map:
        opts["extractor_args"] = {"youtube": client_map[client_name]}

    if cookie_file and os.path.exists(cookie_file):
        opts["cookiefile"] = cookie_file
    if hook:
        opts["progress_hooks"] = [hook]
    return opts


async def _yt_download(url, out_dir, quality, audio_only, hook) -> tuple:
    import yt_dlp
    from config import YT_COOKIES, YT_PROXY

    if audio_only:
        fmt = "bestaudio/best"
    else:
        fmt = {
            "144p":  "best[height<=144]/best",
            "360p":  "best[height<=360]/best",
            "720p":  "best[height<=720]/best",
            "1080p": "best[height<=1080]/best",
            "best":  "best[ext=mp4]/best",
        }.get(quality, "best[ext=mp4]/best")

    cookie_file = _write_cookie_file(YT_COOKIES, "yt") if YT_COOKIES else None

    # Strategy order — android is most reliable on server IPs
    strategies = ["android", "android_vr", "tv_embedded", "ios", "mweb", "web"]
    loop = asyncio.get_event_loop()
    last_err = ""

    for client in strategies:
        opts = _make_yt_opts(out_dir, fmt, YT_PROXY, cookie_file, hook, client)

        def _run(o=opts):
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info:
                    return None, None
                if "entries" in info:
                    results = [_find_file(out_dir, e, ydl) for e in (info.get("entries") or []) if e]
                    return [r for r in results if r] or None, info
                return _find_file(out_dir, info, ydl), info

        try:
            result, meta = await loop.run_in_executor(None, _run)
            if result:
                if cookie_file:
                    try: os.remove(cookie_file)
                    except: pass
                return result, meta
        except Exception as e:
            last_err = str(e)
            continue  # try next strategy

    if cookie_file:
        try: os.remove(cookie_file)
        except: pass

    # All strategies failed — give clear message
    if "Sign in" in last_err or "bot" in last_err or "LOGIN_REQUIRED" in last_err:
        raise RuntimeError(
            "🍪 YouTube bot detection — all clients failed.\n\n"
            "**Solution:** Set `YT_COOKIES` in Render env vars.\n"
            "Export cookies from Chrome using 'Get cookies.txt LOCALLY' extension.\n"
            "Use `/cookies` to verify."
        )
    raise RuntimeError(f"YouTube failed after all strategies: {last_err[:200]}")


# ─────────────────────────────────────────
#  Generic / other platforms
# ─────────────────────────────────────────

async def _generic_download(url, out_dir, hook) -> tuple:
    import yt_dlp
    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 5,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if hook:
        opts["progress_hooks"] = [hook]

    loop = asyncio.get_event_loop()

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None
            if "entries" in info:
                results = [_find_file(out_dir, e, ydl) for e in (info.get("entries") or []) if e]
                return [r for r in results if r] or None, info
            return _find_file(out_dir, info, ydl), info

    return await loop.run_in_executor(None, _run)


# ─────────────────────────────────────────
#  Main entry point
# ─────────────────────────────────────────

async def download_with_ytdlp(
    url: str,
    out_dir: str,
    quality: str = "best",
    audio_only: bool = False,
    progress_hook: Optional[Callable] = None,
) -> tuple:
    from config import INSTAGRAM_COOKIES, TERABOX_COOKIES

    url_type = detect_url_type(url)
    os.makedirs(out_dir, exist_ok=True)

    if url_type == "youtube":
        return await _yt_download(url, out_dir, quality, audio_only, progress_hook)

    # Instagram / Terabox with cookies
    cookie_file = None
    if url_type == "instagram" and INSTAGRAM_COOKIES:
        cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
    elif url_type == "terabox" and TERABOX_COOKIES:
        cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb")

    import yt_dlp
    opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 5,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

    loop = asyncio.get_event_loop()

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                return None, None
            if "entries" in info:
                results = [_find_file(out_dir, e, ydl) for e in (info.get("entries") or []) if e]
                return [r for r in results if r] or None, info
            return _find_file(out_dir, info, ydl), info

    try:
        result = await loop.run_in_executor(None, _run)
        return result
    except Exception as e:
        raise RuntimeError(f"Download failed: {str(e)[:200]}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


# ─────────────────────────────────────────
#  Direct file download (aiohttp) — 403 fix
# ─────────────────────────────────────────

async def download_direct(url: str, out_dir: str, filename=None, progress_hook=None) -> tuple:
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    # First try yt-dlp (handles many direct links better)
    try:
        result = await _generic_download(url, out_dir, progress_hook)
        if result[0]:
            return result
    except Exception:
        pass

    # Fallback: raw aiohttp with browser headers
    if not filename:
        filename = url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4().hex[:8]}"
    filename = clean_filename(filename)
    out_file = os.path.join(out_dir, filename)

    headers = {
        "User-Agent": CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3600),
                               allow_redirects=True) as resp:
            if resp.status == 403:
                raise RuntimeError(
                    f"❌ 403 Forbidden — server blocked the download.\n"
                    f"This usually means the link requires login or has expired."
                )
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
#  M3U8
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


# ─────────────────────────────────────────
#  Google Drive folder
# ─────────────────────────────────────────

async def download_gdrive_folder(url: str, out_dir: str, progress_hook=None) -> tuple:
    import yt_dlp
    os.makedirs(out_dir, exist_ok=True)
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

    loop = asyncio.get_event_loop()

    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        skip = {".part",".ytdl",".tmp"}
        files = sorted([
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip)
            and os.path.getsize(os.path.join(out_dir, x)) > 0
        ], key=os.path.getmtime)
        return files, info

    return await loop.run_in_executor(None, _run)


# ─────────────────────────────────────────
#  Thumbnail helpers
# ─────────────────────────────────────────

def download_thumb_from_url(thumb_url: str, video_id: str) -> Optional[str]:
    try:
        import requests as req
        thumb_path = f"/tmp/thumb_{video_id}.jpg"
        r = req.get(thumb_url, headers={"User-Agent": CHROME_UA}, timeout=10)
        if r.status_code == 200 and len(r.content) > 500:
            with open(thumb_path, "wb") as f:
                f.write(r.content)
            return thumb_path
    except Exception:
        pass
    return None


def find_thumbnail(base_path: str) -> Optional[str]:
    for ext in (".jpg",".jpeg",".webp",".png"):
        t = base_path.rsplit(".",1)[0] + ext
        if os.path.exists(t) and os.path.getsize(t) > 500:
            if not t.endswith(".jpg"):
                jpg = t.rsplit(".",1)[0] + ".jpg"
                r = subprocess.run(["ffmpeg","-y","-i",t,jpg], capture_output=True)
                if r.returncode == 0 and os.path.exists(jpg):
                    try: os.remove(t)
                    except: pass
                    return jpg
            return t
    return None


async def generate_thumbnail(video_path: str) -> Optional[str]:
    thumb_path = video_path.rsplit(".",1)[0] + "_thumb.jpg"
    loop = asyncio.get_event_loop()
    def _run():
        duration = 0
        try:
            r = subprocess.run(
                ["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                capture_output=True, text=True)
            duration = float(json.loads(r.stdout).get("format",{}).get("duration",0))
        except Exception:
            pass
        for seek in ([int(duration*p) for p in [0.1,0.2,0.3,0.5] if duration>5] + [5,3,1,0]):
            r = subprocess.run(
                ["ffmpeg","-y","-ss",str(seek),"-i",video_path,
                 "-vframes","1","-vf","scale=320:-1","-q:v","3",thumb_path],
                capture_output=True)
            if r.returncode==0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path)>2000:
                return thumb_path
        return None
    return await loop.run_in_executor(None, _run)


async def remux_to_mp4(input_path: str) -> str:
    out = input_path.rsplit(".",1)[0] + "_tg.mp4"
    cmd = ["ffmpeg","-y","-i",input_path,"-c","copy","-movflags","+faststart",out]
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode==0 and os.path.exists(out) and os.path.getsize(out)>500:
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
            capture_output=True, text=True)
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
        with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as zf:
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
