"""
Serena Bot - Core Downloader
YouTube FIX: web_embedded + tv_embedded clients FIRST
(Same client Telegram uses for its inline embed player)
These bypass "Sign in to confirm you're not a bot"
"""
import os, sys, asyncio, subprocess, uuid, time, shutil, zipfile, json, re
from typing import Optional
import logging

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import DL_DIR
from utils.helpers import detect_url_type, clean_filename, TERABOX_DOMAINS, get_title_from_url

logger = logging.getLogger("SerenaBot.Downloader")

os.makedirs(DL_DIR, exist_ok=True)

CHROME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/133.0.0.0 Safari/537.36"
)

INVIDIOUS_INSTANCES = [
    "https://inv.nadeko.net",
    "https://invidious.nerdvpn.de",
    "https://invidious.privacydev.net",
    "https://vid.puffyan.us",
    "https://y.com.sb",
    "https://invidious.private.coffee",
    "https://inv.vern.cc",
    "https://invidious.snopyta.org",
    "https://invidious.esmailelbob.xyz",
    "https://invidious.projectsegfau.lt",
]


# ── yt-dlp auto-update ─────────────────────────────────────────────────────
_ytdlp_updated = False
async def _ensure_ytdlp_updated():
    global _ytdlp_updated
    if _ytdlp_updated:
        return
    _ytdlp_updated = True
    loop = asyncio.get_event_loop()
    def _upd():
        try:
            subprocess.run(
                ["pip3", "install", "--upgrade", "yt-dlp", "-q"],
                capture_output=True, timeout=30
            )
        except Exception:
            pass
    await loop.run_in_executor(None, _upd)


# ── Cookie file writer with validation ─────────────────────────────────────
def _write_cookie_file(raw: str, prefix: str) -> Optional[str]:
    if not raw or not raw.strip():
        logger.warning(f"No cookie content for {prefix}")
        return None
    content = raw.strip().strip('"').strip("'")
    content = content.replace("\\n", "\n").replace("\\t", "\t")
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = content.split("\n")
    # Validate that at least one line looks like a valid cookie
    has_cookie = any(
        len(l.split("\t")) >= 7 and not l.startswith("#")
        for l in lines if l.strip()
    )
    if not has_cookie:
        logger.warning(f"Cookie content for {prefix} has no valid entries")
        return None
    try:
        path = f"/tmp/{prefix}_ck_{os.getpid()}.txt"
        with open(path, "w", encoding="utf-8") as f:
            if "# Netscape" not in content:
                f.write("# Netscape HTTP Cookie File\n\n")
            f.write(content)
            if not content.endswith("\n"):
                f.write("\n")
        logger.info(f"Cookies written to {path} for {prefix}")
        return path
    except Exception as e:
        logger.error(f"Failed to write cookie file: {e}")
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
                "message": "❌ Cookie content invalid (no valid entries)."}
    now = int(time.time()); valid = expired = 0; nearest = None
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
                "message": f"⚠️ All **{expired}** cookies expired!"}
    if valid > 0:
        exp_str = datetime.utcfromtimestamp(nearest).strftime("%Y-%m-%d") if nearest else "session"
        return {"valid": True, "expired": False,
                "message": f"✅ **{valid}** valid. Expiry: `{exp_str}`"}
    return {"valid": False, "expired": False, "message": "❌ No valid entries."}


# ── File finder ────────────────────────────────────────────────────────────
def _find_file(out_dir: str, info: Optional[dict], ydl) -> Optional[str]:
    skip = {".jpg",".jpeg",".png",".webp",".part",".ytdl",".tmp"}
    if info:
        try:
            f = ydl.prepare_filename(info)
            base = os.path.splitext(f)[0]
            for c in [f]+[f"{base}.{e}" for e in ["mp4","mkv","webm","mov","mp3","m4a","opus"]]:
                if os.path.exists(c) and os.path.getsize(c) > 500: return c
        except Exception: pass
    try:
        files = [
            os.path.join(out_dir, x) for x in os.listdir(out_dir)
            if os.path.isfile(os.path.join(out_dir, x))
            and not any(x.endswith(e) for e in skip)
            and os.path.getsize(os.path.join(out_dir, x)) > 500
        ]
        return max(files, key=os.path.getmtime) if files else None
    except Exception: return None


# ── YouTube — EMBED CLIENTS FIRST ──────────────────────────────────────────
async def _yt_download(url, out_dir, quality, audio_only, hook) -> tuple:
    import yt_dlp
    from config import YT_COOKIES, YT_PROXY

    await _ensure_ytdlp_updated()

    vid_id = None
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([A-Za-z0-9_-]{11})", url)
    if m: vid_id = m.group(1)

    fmt = "bestaudio/best" if audio_only else {
        "144p":  "best[height<=144]/worst",
        "360p":  "best[height<=360]/best",
        "720p":  "best[height<=720]/best",
        "1080p": "best[height<=1080]/best",
        "best":  "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    }.get(quality, "best[ext=mp4]/best")

    cookie_file = _write_cookie_file(YT_COOKIES, "yt") if YT_COOKIES else None
    if cookie_file:
        logger.info(f"YouTube cookies loaded from {cookie_file}")
    else:
        logger.warning("No YouTube cookies available")

    def _make(player_clients: list, extra_ea: dict = {}):
        ea = {
            "youtube": {"player_client": player_clients},
            "youtubetab": {"skip": ["authcheck"]},
            **extra_ea,
        }
        o = {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True, "no_warnings": True,
            "noplaylist": False, "writethumbnail": True,
            "postprocessors": [], "retries": 3,
            "fragment_retries": 3, "socket_timeout": 30,
            "http_headers": {"User-Agent": CHROME_UA},
            "extractor_args": ea,
        }
        if YT_PROXY:
            o["proxy"] = YT_PROXY
            logger.debug(f"Using proxy: {YT_PROXY}")
        if cookie_file:
            o["cookiefile"] = cookie_file
        if audio_only:
            o["postprocessors"] = [{"key": "FFmpegExtractAudio",
                                     "preferredcodec": "mp3", "preferredquality": "192"}]
        if hook:
            o["progress_hooks"] = [hook]
        return o

    # ── Strategy order: embed clients FIRST ──────────────────────────────
    strategies = [
        _make(["web_embedded"]),
        _make(["tv_embedded"]),
        _make(["web_embedded", "tv_embedded"]),
        _make(["tv_embedded", "web_embedded"]),
        _make(["android"], {"youtube": {"player_client": ["android"],
                                         "player_skip": ["webpage","configs"]}}),
        _make(["android_vr"], {"youtube": {"player_client": ["android_vr"],
                                            "player_skip": ["webpage","configs"]}}),
        _make(["ios"], {"youtube": {"player_client": ["ios"],
                                     "player_skip": ["webpage","configs"]}}),
        _make(["mediaconnect"]),
        _make(["mweb"]),
        _make(["android_testsuite"]),
        # Default fallback
        {
            "format": fmt,
            "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
            "merge_output_format": "mp4",
            "quiet": True, "no_warnings": True,
            "noplaylist": False, "writethumbnail": True,
            "postprocessors": [], "retries": 2,
            "socket_timeout": 30,
            "http_headers": {"User-Agent": CHROME_UA},
            "extractor_args": {"youtubetab": {"skip": ["authcheck"]}},
            **({} if not YT_PROXY else {"proxy": YT_PROXY}),
            **({} if not cookie_file else {"cookiefile": cookie_file}),
            **({} if not hook else {"progress_hooks": [hook]}),
            **({} if not audio_only else {"postprocessors": [{"key": "FFmpegExtractAudio",
                                                               "preferredcodec": "mp3",
                                                               "preferredquality": "192"}]}),
        },
    ]

    loop = asyncio.get_event_loop()
    last_err = ""

    for idx, opts in enumerate(strategies):
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
            logger.debug(f"Trying YouTube strategy #{idx+1}")
            result, meta = await loop.run_in_executor(None, _run)
            if result:
                logger.info(f"YouTube download succeeded with strategy #{idx+1}")
                if cookie_file:
                    try: os.remove(cookie_file)
                    except: pass
                return result, meta
        except Exception as e:
            last_err = str(e)
            logger.warning(f"YouTube strategy #{idx+1} failed: {last_err[:150]}")
            continue

    if cookie_file:
        try: os.remove(cookie_file)
        except: pass

    # ── Invidious fallback ──────────────────────────────────────────────
    if vid_id:
        try:
            logger.info("Trying Invidious fallback...")
            return await _yt_via_invidious(vid_id, out_dir, quality, audio_only, hook)
        except Exception as e:
            last_err += f" | Invidious: {str(e)[:80]}"

    raise RuntimeError(
        f"❌ **YouTube download failed.**\n\n"
        f"**Error:** `{last_err[:200]}`\n\n"
        f"**Quick fix:** Delete Render service → create new (gets fresh IP)\n"
        f"**Permanent fix:** Set `YT_PROXY` (Webshare residential) and valid cookies.\n"
        f"Use `/cookies` to check cookie status."
    )


# ── Invidious fallback ─────────────────────────────────────────────────────
async def _yt_via_invidious(video_id: str, out_dir: str, quality: str,
                              audio_only: bool, hook) -> tuple:
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    async def _try(base: str) -> Optional[dict]:
        api = f"{base}/api/v1/videos/{video_id}?fields=title,author,lengthSeconds,adaptiveFormats,formatStreams"
        try:
            async with aiohttp.ClientSession(
                headers={"User-Agent": CHROME_UA},
                connector=aiohttp.TCPConnector(ssl=False)
            ) as s:
                async with s.get(api, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    if r.status != 200: return None
                    return await r.json()
        except Exception: return None

    data = None
    for inst in INVIDIOUS_INSTANCES:
        data = await _try(inst)
        if data: break

    if not data:
        raise RuntimeError("All Invidious instances failed.")

    title    = data.get("title", video_id)
    author   = data.get("author", "")
    duration = data.get("lengthSeconds", 0)

    if audio_only:
        fmts = sorted(
            [f for f in data.get("adaptiveFormats",[]) if "audio" in f.get("type","")],
            key=lambda x: int(x.get("bitrate",0)), reverse=True
        )
        chosen = fmts[0] if fmts else None
        out_ext = "m4a"
    else:
        target_h = {"144p":144,"360p":360,"720p":720,"1080p":1080}.get(quality, 9999)
        fmts = sorted(
            [f for f in data.get("formatStreams",[]) if f.get("container") == "mp4"],
            key=lambda x: abs(int(x.get("resolution","0p").replace("p","") or 0) - target_h)
        )
        if not fmts: fmts = data.get("formatStreams",[])
        chosen = fmts[0] if fmts else None
        out_ext = "mp4"

    if not chosen or not chosen.get("url"):
        raise RuntimeError("No downloadable format via Invidious.")

    fname    = clean_filename(title) + f".{out_ext}"
    out_file = os.path.join(out_dir, fname)
    dl_url   = chosen["url"]

    async with aiohttp.ClientSession(headers={"User-Agent": CHROME_UA}) as s:
        async with s.get(dl_url, timeout=aiohttp.ClientTimeout(total=3600),
                         allow_redirects=True) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("Content-Length",0))
            done  = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(131072):
                    f.write(chunk); done += len(chunk)
                    if hook:
                        try: await hook(done, total)
                        except Exception: pass

    return out_file, {"title": title, "uploader": author, "duration": duration, "ext": out_ext}


# ── Rest of the file unchanged (Terabox, generic, direct, etc.) ────────────
# ... (keep the rest as before, no changes needed for those parts)
