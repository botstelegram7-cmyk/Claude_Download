"""
Serena Bot - Core Downloader
FIXES:
1. YouTube: yt-dlp auto-update + PO token bypass + cookies
2. Terabox: all domains + proxy support  
3. Instagram: best quality (bestvideo+bestaudio)
4. All video: remux to streamable MP4
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

# All Terabox domains
TERABOX_DOMAINS = [
    "terabox.com", "1024terabox.com", "teraboxapp.com", "terabox.app",
    "4funbox.com", "mirrobox.com", "nephobox.com", "freeterabox.com",
    "momerybox.com", "tibibox.com", "teraboxlink.com", "terasharelink.com",
]


# ── yt-dlp auto-update (run once on startup) ──────────────────────────────

_yt_dlp_updated = False

async def _ensure_ytdlp_updated():
    global _yt_dlp_updated
    if _yt_dlp_updated:
        return
    _yt_dlp_updated = True
    loop = asyncio.get_event_loop()
    def _upd():
        try:
            r = subprocess.run(
                ["pip", "install", "--upgrade", "yt-dlp", "--break-system-packages", "-q"],
                capture_output=True, text=True, timeout=60
            )
            return r.returncode == 0
        except Exception:
            return False
    await loop.run_in_executor(None, _upd)


# ── Cookie helpers ─────────────────────────────────────────────────────────

def _write_cookie_file(raw: str, prefix: str) -> Optional[str]:
    if not raw or not raw.strip():
        return None
    content = raw.strip().strip('"').strip("'")
    # Fix Render encoding — literal \n and \t to real ones
    content = content.replace("\\n", "\n").replace("\\t", "\t")
    content = content.replace("\r\n", "\n").replace("\r", "\n")

    lines = content.split("\n")
    has_cookie = any(
        len(l.split("\t")) >= 7 and not l.startswith("#")
        for l in lines if l.strip()
    )
    if not has_cookie:
        return None

    try:
        path = f"/tmp/{prefix}_cookies_{os.getpid()}.txt"
        with open(path, "w", encoding="utf-8") as f:
            if "# Netscape" not in content:
                f.write("# Netscape HTTP Cookie File\n\n")
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        return path
    except Exception:
        return None


async def check_yt_cookies_status() -> dict:
    from config import YT_COOKIES
    from datetime import datetime
    if not YT_COOKIES or not YT_COOKIES.strip():
        return {"valid": False, "expired": False,
                "message": "❌ `YT_COOKIES` not set in Render environment."}
    path = _write_cookie_file(YT_COOKIES, "yt_check")
    if not path:
        return {"valid": False, "expired": False,
                "message": "❌ Cookie content invalid — wrong format or encoding issue."}
    now = int(time.time())
    valid = expired = 0
    nearest = None
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"): continue
                parts = line.split("\t")
                if len(parts) >= 7:
                    try:
                        exp = int(parts[4])
                        if exp == 0: valid += 1
                        elif exp > now:
                            valid += 1
                            if nearest is None or exp < nearest: nearest = exp
                        else: expired += 1
                    except ValueError: pass
    finally:
        try: os.remove(path)
        except: pass
    if valid == 0 and expired > 0:
        return {"valid": False, "expired": True,
                "message": f"⚠️ All **{expired}** cookies expired! Export fresh cookies."}
    if valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ **{valid}** valid entries. Nearest expiry: `{exp_str}`"}
    return {"valid": False, "expired": False, "message": "❌ No valid entries found."}


# ── File finder ────────────────────────────────────────────────────────────

def _find_file(out_dir: str, info: Optional[dict], ydl) -> Optional[str]:
    skip = {".jpg", ".jpeg", ".png", ".webp", ".part", ".ytdl", ".tmp"}
    if info:
        try:
            f = ydl.prepare_filename(info)
            base = os.path.splitext(f)[0]
            for c in [f] + [f"{base}.{e}" for e in ["mp4","mkv","webm","mov","mp3","m4a","opus"]]:
                if os.path.exists(c) and os.path.getsize(c) > 500:
                    return c
        except Exception: pass
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


# ── YouTube download ────────────────────────────────────────────────────────

async def _yt_download(url, out_dir, quality, audio_only, hook) -> tuple:
    import yt_dlp
    from config import YT_COOKIES, YT_PROXY

    # Try to update yt-dlp first (fixes "Failed to extract player response")
    await _ensure_ytdlp_updated()

    fmt = "bestaudio/best" if audio_only else {
        "144p": "best[height<=144]/worst",
        "360p": "best[height<=360]/best",
        "720p": "best[height<=720]/best",
        "1080p": "best[height<=1080]/best",
        "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }.get(quality, "best[ext=mp4]/best")

    cookie_file = _write_cookie_file(YT_COOKIES, "yt") if YT_COOKIES else None

    def _opts(client_args: dict):
        o = {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": False,
            "writethumbnail": True,
            "postprocessors": [],
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "http_headers": {"User-Agent": CHROME_UA},
        }
        if YT_PROXY:
            o["proxy"] = YT_PROXY
        if client_args:
            o["extractor_args"] = {"youtube": client_args}
        if cookie_file:
            o["cookiefile"] = cookie_file
        if audio_only:
            o["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                     "preferredcodec": "mp3", "preferredquality": "192"}]
        if hook:
            o["progress_hooks"] = [hook]
        return o

    strategies = [
        {"player_client": ["android"], "player_skip": ["webpage", "configs"]},
        {"player_client": ["android_vr"], "player_skip": ["webpage", "configs"]},
        {"player_client": ["tv_embedded"]},
        {"player_client": ["ios"], "player_skip": ["webpage", "configs"]},
        {"player_client": ["mweb"]},
        {},
    ]

    loop = asyncio.get_event_loop()
    last_err = ""

    for strat in strategies:
        opts = _opts(strat)
        def _run(o=opts):
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info: return None, None
                if "entries" in info:
                    res = [_find_file(out_dir, e, ydl)
                           for e in (info.get("entries") or []) if e]
                    return [r for r in res if r] or None, info
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
            continue

    if cookie_file:
        try: os.remove(cookie_file)
        except: pass

    raise RuntimeError(
        "🔐 **YouTube download failed.**\n\n"
        "**Most likely fix:** Update yt-dlp on Render\n"
        "Add this to `requirements.txt`:\n"
        "`yt-dlp>=2025.1.1`\n\n"
        "Or in Render shell: `pip install -U yt-dlp`\n\n"
        f"`{last_err[:120]}`"
    )


# ── Terabox download (all domains + proxy) ─────────────────────────────────

async def _terabox_download(url, out_dir, cookie_file, hook) -> tuple:
    """
    Terabox: try multiple approaches since Render IPs are often blocked.
    Supports all terabox domains including 1024terabox.com
    """
    import yt_dlp
    from config import YT_PROXY  # reuse proxy for terabox too

    base_opts = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if cookie_file:
        base_opts["cookiefile"] = cookie_file
    if hook:
        base_opts["progress_hooks"] = [hook]

    loop = asyncio.get_event_loop()
    last_err = ""

    # Try with proxy first, then without
    proxy_opts = [{**base_opts, "proxy": YT_PROXY}, base_opts] if YT_PROXY else [base_opts]

    for opts in proxy_opts:
        def _run(o=opts):
            with yt_dlp.YoutubeDL(o) as ydl:
                info = ydl.extract_info(url, download=True)
                if not info: return None, None
                if "entries" in info:
                    res = [_find_file(out_dir, e, ydl)
                           for e in (info.get("entries") or []) if e]
                    return [r for r in res if r] or None, info
                return _find_file(out_dir, info, ydl), info
        try:
            result, meta = await loop.run_in_executor(None, _run)
            if result: return result, meta
        except Exception as e:
            last_err = str(e)
            continue

    raise RuntimeError(
        f"⛔ Terabox blocked this server's IP.\n"
        f"Terabox geoblocks many cloud IPs.\n"
        f"Try a different link or download manually.\n"
        f"`{last_err[:100]}`"
    )


# ── Generic yt-dlp (Instagram best quality, TikTok, Twitter etc.) ──────────

async def _generic_ydl(url, out_dir, cookie_file, hook, audio_only=False) -> tuple:
    import yt_dlp

    if audio_only:
        fmt = "bestaudio/best"
    else:
        # Best quality — bestvideo+bestaudio for Instagram etc.
        fmt = "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True,
        "no_warnings": True,
        "writethumbnail": True,
        "postprocessors": [],
        "retries": 3,
        "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if audio_only:
        opts["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                    "preferredcodec": "mp3", "preferredquality": "320"}]
    if cookie_file: opts["cookiefile"] = cookie_file
    if hook: opts["progress_hooks"] = [hook]

    loop = asyncio.get_event_loop()
    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info: return None, None
            if "entries" in info:
                res = [_find_file(out_dir, e, ydl)
                       for e in (info.get("entries") or []) if e]
                return [r for r in res if r] or None, info
            return _find_file(out_dir, info, ydl), info
    return await loop.run_in_executor(None, _run)


# ── Main entry ────────────────────────────────────────────────────────────

async def download_with_ytdlp(url, out_dir, quality="best",
                               audio_only=False, progress_hook=None) -> tuple:
    from config import INSTAGRAM_COOKIES, TERABOX_COOKIES
    url_type = detect_url_type(url)
    os.makedirs(out_dir, exist_ok=True)

    if url_type == "youtube":
        return await _yt_download(url, out_dir, quality, audio_only, progress_hook)

    # Terabox — all domains
    if url_type == "terabox" or any(d in url for d in TERABOX_DOMAINS):
        cookie_file = _write_cookie_file(TERABOX_COOKIES, "tb") if TERABOX_COOKIES else None
        try:
            return await _terabox_download(url, out_dir, cookie_file, progress_hook)
        finally:
            if cookie_file and os.path.exists(cookie_file):
                try: os.remove(cookie_file)
                except: pass

    cookie_file = None
    if url_type == "instagram" and INSTAGRAM_COOKIES:
        cookie_file = _write_cookie_file(INSTAGRAM_COOKIES, "ig")

    try:
        return await _generic_ydl(url, out_dir, cookie_file, progress_hook, audio_only)
    except Exception as e:
        raise RuntimeError(f"Download failed: {str(e)[:200]}")
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


# ── M3U8 ─────────────────────────────────────────────────────────────────

async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> tuple:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    loop = asyncio.get_event_loop()
    def _run():
        cmd = [
            "ffmpeg", "-y",
            "-headers", f"User-Agent: {CHROME_UA}\r\n",
            "-allowed_extensions", "ALL",
            "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
            "-i", url, "-c", "copy", "-movflags", "+faststart", out_file
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                raise RuntimeError(f"ffmpeg: {r.stderr[-200:]}")
            if not os.path.exists(out_file) or os.path.getsize(out_file) < 1000:
                raise RuntimeError("Output file empty")
            return out_file
        except subprocess.TimeoutExpired:
            raise RuntimeError("⏱ Stream timed out (5 min limit).")
    try:
        result = await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=310)
        return result, None
    except asyncio.TimeoutError:
        raise RuntimeError("⏱ Stream timed out.")


# ── Direct file ───────────────────────────────────────────────────────────

async def download_direct(url, out_dir, filename=None,
                           extra_headers=None, progress_hook=None) -> tuple:
    try:
        r = await _generic_ydl(url, out_dir, None, progress_hook)
        if r[0]: return r
    except Exception: pass

    import aiohttp
    os.makedirs(out_dir, exist_ok=True)
    if not filename:
        filename = url.split("/")[-1].split("?")[0] or f"file_{uuid.uuid4().hex[:8]}"
    filename = clean_filename(filename)
    out_file = os.path.join(out_dir, filename)
    hdrs = {"User-Agent": CHROME_UA, **(extra_headers or {})}
    async with aiohttp.ClientSession(headers=hdrs) as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=3600),
                         allow_redirects=True) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(65536):
                    f.write(chunk); done += len(chunk)
                    if progress_hook: await progress_hook(done, total)
    return out_file, None


# ── Google Drive folder ───────────────────────────────────────────────────

async def download_gdrive_folder(url, out_dir, progress_hook=None) -> tuple:
    import yt_dlp
    os.makedirs(out_dir, exist_ok=True)
    opts = {"format": "best", "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
            "quiet": True, "no_warnings": True, "noplaylist": False,
            "retries": 3, "http_headers": {"User-Agent": CHROME_UA}}
    if progress_hook: opts["progress_hooks"] = [progress_hook]
    loop = asyncio.get_event_loop()
    def _run():
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        skip = {".part", ".ytdl", ".tmp"}
        files = sorted([
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip)
            and os.path.getsize(os.path.join(out_dir, x)) > 0
        ], key=os.path.getmtime)
        return files, info
    return await loop.run_in_executor(None, _run)


# ── Thumbnail helpers ─────────────────────────────────────────────────────

def download_thumb_from_url(thumb_url, video_id) -> Optional[str]:
    try:
        import requests as req
        r = req.get(thumb_url, headers={"User-Agent": CHROME_UA}, timeout=10)
        if r.status_code == 200 and len(r.content) > 500:
            p = f"/tmp/thumb_{video_id}.jpg"
            with open(p, "wb") as f: f.write(r.content)
            return p
    except Exception: pass
    return None

def find_thumbnail(base_path) -> Optional[str]:
    for ext in (".jpg", ".jpeg", ".webp", ".png"):
        t = base_path.rsplit(".", 1)[0] + ext
        if os.path.exists(t) and os.path.getsize(t) > 500:
            if not t.endswith(".jpg"):
                jpg = t.rsplit(".", 1)[0] + ".jpg"
                r = subprocess.run(["ffmpeg", "-y", "-i", t, jpg], capture_output=True)
                if r.returncode == 0 and os.path.exists(jpg):
                    try: os.remove(t)
                    except: pass
                    return jpg
            return t
    return None

async def generate_thumbnail(video_path) -> Optional[str]:
    thumb_path = video_path.rsplit(".", 1)[0] + "_thumb.jpg"
    loop = asyncio.get_event_loop()
    def _run():
        duration = 0
        try:
            r = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json",
                                 "-show_format", video_path], capture_output=True, text=True)
            duration = float(json.loads(r.stdout).get("format", {}).get("duration", 0))
        except Exception: pass
        for seek in ([int(duration*p) for p in [0.1,0.2,0.3] if duration>5]+[5,2,0]):
            r = subprocess.run(
                ["ffmpeg","-y","-ss",str(seek),"-i",video_path,
                 "-vframes","1","-vf","scale=320:-1","-q:v","3",thumb_path],
                capture_output=True)
            if r.returncode==0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path)>2000:
                return thumb_path
        return None
    return await loop.run_in_executor(None, _run)

async def remux_to_mp4(input_path) -> str:
    out = input_path.rsplit(".", 1)[0] + "_tg.mp4"
    loop = asyncio.get_event_loop()
    def _run():
        r = subprocess.run(
            ["ffmpeg","-y","-i",input_path,"-c","copy","-movflags","+faststart",out],
            capture_output=True)
        if r.returncode==0 and os.path.exists(out) and os.path.getsize(out)>500:
            try: os.remove(input_path)
            except: pass
            return out
        return input_path
    return await loop.run_in_executor(None, _run)

def get_video_info(path) -> dict:
    try:
        r = subprocess.run(
            ["ffprobe","-v","quiet","-print_format","json",
             "-show_streams","-show_format","-select_streams","v:0",path],
            capture_output=True, text=True)
        data = json.loads(r.stdout)
        stream = (data.get("streams") or [{}])[0]
        dur = float(data.get("format",{}).get("duration",0))
        return {"width":stream.get("width",0),"height":stream.get("height",0),"duration":int(dur)}
    except Exception:
        return {"width":0,"height":0,"duration":0}

async def zip_folder(folder_path, out_path, name="files") -> str:
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
        except Exception: pass
