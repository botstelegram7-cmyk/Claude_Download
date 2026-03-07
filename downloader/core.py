"""
Serena Bot - Core Downloader
FIXES:
- Direct links: pure aiohttp, skip yt-dlp (403 fix)
- GDrive bulk export (storage.googleapis.com): download as-is ZIP
- Instagram: best quality (bestvideo+bestaudio)
- YouTube: yt-dlp auto-update + playlist authcheck skip
- Terabox: all domains + proxy
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile, json
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import detect_url_type, clean_filename, TERABOX_DOMAINS, get_title_from_url
os.makedirs(DL_DIR, exist_ok=True)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)
BROWSER_HEADERS = {
    "User-Agent": CHROME_UA,
    "Accept": "video/webm,video/mp4,video/*;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",   # no gzip — we need raw bytes for video
    "Connection": "keep-alive",
    "Referer": "https://www.google.com/",
}


# ── yt-dlp auto-update on first use ───────────────────────────────────────
_ytdlp_updated = False

async def _ensure_ytdlp_updated():
    global _ytdlp_updated
    if _ytdlp_updated: return
    _ytdlp_updated = True
    loop = asyncio.get_event_loop()
    def _upd():
        try:
            subprocess.run(
                ["pip", "install", "--upgrade", "yt-dlp", "--break-system-packages", "-q"],
                capture_output=True, timeout=60
            )
        except Exception: pass
    await loop.run_in_executor(None, _upd)


# ── Cookie file writer ────────────────────────────────────────────────────
def _write_cookie_file(raw: str, prefix: str) -> Optional[str]:
    if not raw or not raw.strip(): return None
    content = raw.strip().strip('"').strip("'")
    content = content.replace("\\n", "\n").replace("\\t", "\t")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")
    has_cookie = any(
        len(l.split("\t")) >= 7 and not l.startswith("#")
        for l in lines if l.strip()
    )
    if not has_cookie: return None
    try:
        path = f"/tmp/{prefix}_ck_{os.getpid()}.txt"
        with open(path, "w", encoding="utf-8") as f:
            if "# Netscape" not in content:
                f.write("# Netscape HTTP Cookie File\n\n")
            f.write(content)
            if not content.endswith("\n"): f.write("\n")
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
                "message": "❌ Cookie content invalid — check format."}
    now = int(time.time())
    valid = expired = 0; nearest = None
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
                "message": f"✅ **{valid}** valid entries. Expiry: `{exp_str}`"}
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


# ── YouTube ───────────────────────────────────────────────────────────────
async def _yt_download(url, out_dir, quality, audio_only, hook) -> tuple:
    import yt_dlp
    from config import YT_COOKIES, YT_PROXY

    await _ensure_ytdlp_updated()

    fmt = "bestaudio/best" if audio_only else {
        "144p":  "best[height<=144]/worst",
        "360p":  "best[height<=360]/best",
        "720p":  "best[height<=720]/best",
        "1080p": "best[height<=1080]/best",
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }.get(quality, "best[ext=mp4]/best")

    cookie_file = _write_cookie_file(YT_COOKIES, "yt") if YT_COOKIES else None

    def _make(ea: dict):
        o = {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True, "no_warnings": True,
            "noplaylist": False, "writethumbnail": True,
            "postprocessors": [], "retries": 3,
            "fragment_retries": 3, "socket_timeout": 30,
            "http_headers": {"User-Agent": CHROME_UA},
            # Fix: skip authcheck warning for playlists
            "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
        }
        if ea: o["extractor_args"]["youtube"] = ea
        if YT_PROXY:    o["proxy"] = YT_PROXY
        if cookie_file: o["cookiefile"] = cookie_file
        if audio_only:
            o["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                     "preferredcodec": "mp3", "preferredquality": "192"}]
        if hook: o["progress_hooks"] = [hook]
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
        opts = _make(strat)
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
        "🔐 **YouTube failed.**\n"
        "Update yt-dlp or set fresh cookies.\n"
        f"`{last_err[:120]}`"
    )


# ── Terabox ───────────────────────────────────────────────────────────────
async def _terabox_download(url, out_dir, cookie_file, hook) -> tuple:
    import yt_dlp
    from config import YT_PROXY

    base = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True,
        "writethumbnail": True, "postprocessors": [],
        "retries": 3, "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if cookie_file: base["cookiefile"] = cookie_file
    if hook: base["progress_hooks"] = [hook]

    loop = asyncio.get_event_loop()
    last_err = ""
    candidates = [{**base, "proxy": YT_PROXY}, base] if YT_PROXY else [base]
    for opts in candidates:
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
        f"⛔ Terabox blocked this server's IP.\n`{last_err[:100]}`"
    )


# ── Generic yt-dlp (Instagram best, TikTok, Twitter etc.) ────────────────
async def _generic_ydl(url, out_dir, cookie_file, hook, audio_only=False) -> tuple:
    import yt_dlp

    fmt = "bestaudio/best" if audio_only else \
          "bestvideo[ext=mp4]+bestaudio[ext=m4a]/bestvideo+bestaudio/best[ext=mp4]/best"

    opts = {
        "format": fmt,
        "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True,
        "writethumbnail": True, "postprocessors": [],
        "retries": 3, "socket_timeout": 30,
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

    if url_type == "terabox" or any(d in url.lower() for d in TERABOX_DOMAINS):
        ck = _write_cookie_file(TERABOX_COOKIES, "tb") if TERABOX_COOKIES else None
        try:
            return await _terabox_download(url, out_dir, ck, progress_hook)
        finally:
            if ck and os.path.exists(ck):
                try: os.remove(ck)
                except: pass

    ck = None
    if url_type == "instagram" and INSTAGRAM_COOKIES:
        ck = _write_cookie_file(INSTAGRAM_COOKIES, "ig")
    try:
        return await _generic_ydl(url, out_dir, ck, progress_hook, audio_only)
    except Exception as e:
        raise RuntimeError(f"Download failed: {str(e)[:200]}")
    finally:
        if ck and os.path.exists(ck):
            try: os.remove(ck)
            except: pass


# ── Direct file download (aiohttp — no yt-dlp, handles 403 better) ────────
async def download_direct(url: str, out_dir: str, filename: str = None,
                           extra_headers: dict = None,
                           progress_hook=None) -> tuple:
    """
    Pure aiohttp download for direct links.
    - Reads filename from Content-Disposition header or ?title= param
    - Returns (filepath, meta) where meta has 'title' set from URL/headers
    """
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    # Pre-extract title from URL for caption
    url_title = get_title_from_url(url)

    hdrs = {**BROWSER_HEADERS, **(extra_headers or {})}

    async with aiohttp.ClientSession(headers=hdrs) as session:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=3600),
            allow_redirects=True
        ) as resp:
            if resp.status in (403, 401):
                raise RuntimeError(
                    f"❌ {resp.status} — link expired or access denied.\n"
                    "Try downloading again with a fresh link."
                )
            resp.raise_for_status()

            # Get filename from Content-Disposition header
            cd = resp.headers.get("Content-Disposition", "")
            fname = None
            if cd:
                m = re.search(r'filename\*?=["\']?(?:UTF-8\'\')?([^"\';\r\n]+)',
                               cd, re.I)
                if m:
                    from urllib.parse import unquote
                    fname = unquote(m.group(1).strip().strip('"\''))

            if not fname:
                if filename:
                    fname = filename
                else:
                    # Extract from URL path
                    from urllib.parse import unquote
                    fname = unquote(url.split("?")[0].rstrip("/").split("/")[-1])
                    if not fname or len(fname) < 3:
                        ct = resp.headers.get("Content-Type", "")
                        ext = _ext_from_ct(ct) or "bin"
                        fname = f"file_{uuid.uuid4().hex[:8]}.{ext}"

            fname = clean_filename(fname)
            out_file = os.path.join(out_dir, fname)

            total = int(resp.headers.get("Content-Length", 0))
            done = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(131072):  # 128KB
                    f.write(chunk)
                    done += len(chunk)
                    if progress_hook:
                        await progress_hook(done, total)

    # Build minimal meta with title
    meta = {
        "title": url_title or os.path.splitext(fname)[0].replace("_", " ").replace("-", " ").strip(),
        "ext": fname.rsplit(".", 1)[-1] if "." in fname else "",
    }
    return out_file, meta


def _ext_from_ct(ct: str) -> str:
    ct = ct.split(";")[0].strip().lower()
    return {
        "video/mp4": "mp4", "video/webm": "webm", "video/x-matroska": "mkv",
        "audio/mpeg": "mp3", "audio/mp4": "m4a", "audio/ogg": "ogg",
        "image/jpeg": "jpg", "image/png": "png", "image/gif": "gif", "image/webp": "webp",
        "application/pdf": "pdf", "application/zip": "zip",
        "application/x-rar-compressed": "rar",
    }.get(ct, "")


import re


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
                raise RuntimeError(f"ffmpeg error: {r.stderr[-200:]}")
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


# ── Google Drive folder ───────────────────────────────────────────────────
async def download_gdrive_folder(url, out_dir, progress_hook=None) -> tuple:
    import yt_dlp
    os.makedirs(out_dir, exist_ok=True)
    opts = {
        "format": "best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "quiet": True, "no_warnings": True, "noplaylist": False,
        "retries": 3, "http_headers": {"User-Agent": CHROME_UA},
    }
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
                r = subprocess.run(["ffmpeg","-y","-i",t,jpg], capture_output=True)
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
            r = subprocess.run(
                ["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                capture_output=True, text=True)
            duration = float(json.loads(r.stdout).get("format",{}).get("duration",0))
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
