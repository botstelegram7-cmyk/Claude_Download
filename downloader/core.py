"""
Serena Bot - Core Downloader
YouTube FIX: web_embedded + tv_embedded clients FIRST
(Same client Telegram uses for its inline embed player)
These bypass "Sign in to confirm you're not a bot"
"""
import os
import sys
import asyncio
import subprocess
import uuid
import time
import shutil
import zipfile
import json
import re
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
    "https://invidious.flokinet.to",
    "https://invidious.tiekoetter.com",
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
            logger.error(f"Invidious fallback failed: {e}")

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
        except Exception as e:
            logger.debug(f"Invidious instance {base} failed: {e}")
            return None

    data = None
    for inst in INVIDIOUS_INSTANCES:
        data = await _try(inst)
        if data:
            logger.info(f"Using Invidious instance: {inst}")
            break

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


# ── Generic video host scraper (streaam.net etc.) ─────────────────────────
async def _scrape_video_host(url: str, out_dir: str, hook) -> tuple:
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    hdrs = {
        "User-Agent": CHROME_UA,
        "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": url,
    }

    async with aiohttp.ClientSession(headers=hdrs) as session:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20),
                               allow_redirects=True) as resp:
            if resp.status != 200:
                raise RuntimeError(f"Page load failed: HTTP {resp.status}")
            html = await resp.text(errors="ignore")
            final_url = str(resp.url)

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else ""
        title = re.sub(r"\s*[-|–]\s*.+$", "", title).strip()

        direct_url = None
        patterns = [
            r'(?:file|src|source)\s*[=:]\s*["\']([^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']',
            r'(?:file|url)\s*:\s*["\']([^"\']+\.(?:mp4|m3u8|webm)[^"\']*)["\']',
            r'"(?:hls|mp4|stream|video|source)"\s*:\s*"([^"]+)"',
            r'videoUrl\s*[=:]\s*["\']([^"\']+)["\']',
            r'<source[^>]+src=["\']([^"\']+)["\']',
            r'"stream_url"\s*:\s*"([^"]+)"',
            r'"url"\s*:\s*"(https?://[^"]+\.(?:mp4|m3u8|webm)[^"]*)"',
            r'player\.src\s*\(\s*["\']([^"\']+)["\']',
            r'atob\s*\(\s*["\']([A-Za-z0-9+/=]{20,})["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.I)
            if m:
                found = m.group(1)
                if re.match(r"^[A-Za-z0-9+/=]{20,}$", found) and "." not in found:
                    try:
                        import base64
                        decoded = base64.b64decode(found).decode("utf-8", errors="ignore")
                        if "http" in decoded:
                            fm = re.search(r"https?://[^\s\"']+", decoded)
                            found = fm.group(0) if fm else None
                    except Exception: found = None
                if found:
                    if found.startswith("/"):
                        from urllib.parse import urljoin
                        found = urljoin(final_url, found)
                    if found.startswith("http"):
                        direct_url = found; break

        if not direct_url:
            # Check iframe
            iframe_m = re.search(r'<iframe[^>]+src=["\']([^"\']+)["\']', html, re.I)
            if iframe_m:
                iframe_src = iframe_m.group(1)
                if iframe_src.startswith("/"):
                    from urllib.parse import urljoin
                    iframe_src = urljoin(final_url, iframe_src)
                if iframe_src != url:
                    try:
                        async with session.get(iframe_src, timeout=aiohttp.ClientTimeout(total=15),
                                               headers={**hdrs,"Referer":url}) as r2:
                            html2 = await r2.text(errors="ignore")
                        for pat in patterns:
                            m = re.search(pat, html2, re.I)
                            if m:
                                found = m.group(1)
                                if found.startswith("/"):
                                    from urllib.parse import urljoin
                                    found = urljoin(str(r2.url), found)
                                if found.startswith("http"):
                                    direct_url = found; break
                    except Exception: pass

        if not direct_url:
            raise RuntimeError("❌ Could not extract video — site uses JS obfuscation.")

        dl_hdrs = {**hdrs, "Referer": final_url}

        if ".m3u8" in direct_url or "m3u8" in direct_url:
            out_file = os.path.join(out_dir, f"{clean_filename(title or 'video')}.mp4")
            cmd = [
                "ffmpeg","-y",
                "-headers", f"User-Agent: {CHROME_UA}\r\nReferer: {final_url}\r\n",
                "-allowed_extensions","ALL",
                "-protocol_whitelist","file,http,https,tcp,tls,crypto",
                "-i",direct_url,"-c","copy","-movflags","+faststart",out_file
            ]
            loop = asyncio.get_event_loop()
            def _run():
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                if r.returncode != 0: raise RuntimeError(f"ffmpeg: {r.stderr[-150:]}")
                return out_file
            await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=310)
        else:
            fname = clean_filename(title or "video") + ".mp4"
            out_file = os.path.join(out_dir, fname)
            async with session.get(direct_url, timeout=aiohttp.ClientTimeout(total=3600),
                                   headers=dl_hdrs, allow_redirects=True) as dl:
                dl.raise_for_status()
                total = int(dl.headers.get("Content-Length",0))
                done  = 0
                with open(out_file, "wb") as f:
                    async for chunk in dl.content.iter_chunked(131072):
                        f.write(chunk); done += len(chunk)
                        if hook:
                            try: await hook(done, total)
                            except Exception: pass

    return out_file, {"title": title or "Video", "ext": "mp4"}


# ── Terabox ───────────────────────────────────────────────────────────────
# Expanded third-party APIs
_TERABOX_THIRD_PARTY_APIS = [
    "https://teraboxdownloader.online/api/download?url=",
    "https://terabox.udayscriptsx.workers.dev/?url=",
    "https://tera.instavideosave.com/?url=",
    "https://teradl-api.dapuntaratya.com/generate?url=",
    "https://terabox-dl-api.vercel.app/api?url=",
    "https://terabox.hnn.workers.dev/?url=",
    "https://terabox.giize.com/?url=",
]

_TERABOX_DOMAINS_API = [
    "https://www.terabox.com",
    "https://www.1024tera.com",
    "https://teraboxapp.com",
    "https://www.terabox.app",
    "https://www.4funbox.com",
]


def _extract_terabox_surl(url: str) -> Optional[str]:
    """Extract surl from any Terabox URL format"""
    patterns = [
        r'[?&]surl=([a-zA-Z0-9_-]+)',
        r'/s/1?([a-zA-Z0-9_-]+)',
        r'tbx\.to/([a-zA-Z0-9_-]+)',
        r'/sharing/(?:link|video)\?surl=([a-zA-Z0-9_-]+)',
        r'/wap/share/filelist\?surl=([a-zA-Z0-9_-]+)',
    ]
    for pat in patterns:
        m = re.search(pat, url)
        if m: return m.group(1)
    return None


def _normalize_terabox_url(url: str) -> str:
    """Normalize any Terabox URL to standard format"""
    surl = _extract_terabox_surl(url)
    if surl:
        clean = surl.lstrip("1") if len(surl) > 20 else surl
        return f"https://www.terabox.com/s/1{clean}"
    return url


def _terabox_third_party(url: str) -> tuple:
    """Try free third-party APIs to get direct download link"""
    import requests as req
    from urllib.parse import quote
    normalized = _normalize_terabox_url(url)
    for api in _TERABOX_THIRD_PARTY_APIS:
        try:
            api_url = api + quote(normalized, safe="")
            r = req.get(api_url, timeout=30)
            if r.status_code != 200: continue
            ct = r.headers.get("Content-Type","")
            data = r.json() if "json" in ct else {}
            dl_url = (
                data.get("download_link") or data.get("downloadLink") or
                data.get("dlink") or data.get("url") or
                (data.get("data") or {}).get("download_link") or
                (data.get("data") or {}).get("dlink") or
                (data.get("result") or {}).get("download_link")
            )
            filename = (
                data.get("filename") or data.get("file_name") or
                data.get("name") or
                (data.get("data") or {}).get("filename") or
                "terabox_file"
            )
            if dl_url and dl_url.startswith("http"):
                logger.info(f"Terabox third-party API success: {api}")
                return dl_url, clean_filename(filename)
        except Exception as e:
            logger.debug(f"Terabox API {api} failed: {e}")
            continue
    return None, None


def _terabox_official_api(surl: str, cookie: str) -> tuple:
    """Use official Terabox API with cookies"""
    import requests as req
    if not cookie: return None, None
    headers = {
        "User-Agent": CHROME_UA,
        "Accept": "application/json",
        "Cookie": cookie,
        "Referer": "https://www.terabox.com/",
    }
    for base in _TERABOX_DOMAINS_API:
        for prefix in ["1", ""]:
            try:
                api_url = f"{base}/api/shorturlinfo?shorturl={prefix}{surl}&root=1"
                r = req.get(api_url, headers=headers, timeout=30)
                if r.status_code != 200: continue
                data = r.json()
                if data.get("errno") == 0:
                    file_list = data.get("list", [])
                    if file_list:
                        first = file_list[0]
                        dlink = first.get("dlink","")
                        fname = first.get("server_filename") or first.get("filename") or "terabox_file"
                        if dlink:
                            logger.info(f"Terabox official API success")
                            return dlink, clean_filename(fname)
            except Exception:
                continue
    return None, None


def _terabox_scrape(url: str, cookie: str = "") -> tuple:
    """Scrape Terabox page for direct dlink"""
    import requests as req
    try:
        headers = {"User-Agent": CHROME_UA, "Accept": "text/html"}
        if cookie: headers["Cookie"] = cookie
        normalized = _normalize_terabox_url(url)
        r = req.get(normalized, headers=headers, timeout=30)
        text = r.text
        dlink = None
        for pat in [r'"dlink"\s*:\s*"([^"]+)"', r'"downloadLink"\s*:\s*"([^"]+)"']:
            m = re.search(pat, text)
            if m:
                candidate = m.group(1).replace("\/", "/").replace("\u0026", "&")
                if candidate.startswith("http"):
                    dlink = candidate; break
        filename = "terabox_file"
        for pat in [r'"server_filename"\s*:\s*"([^"]+)"', r'"filename"\s*:\s*"([^"]+)"']:
            m = re.search(pat, text)
            if m:
                fname = m.group(1).strip()
                if fname and len(fname) > 2:
                    filename = clean_filename(fname); break
        if dlink:
            logger.info(f"Terabox scrape success")
        return dlink, filename
    except Exception as e:
        logger.debug(f"Terabox scrape failed: {e}")
        return None, "terabox_file"


def _detect_file_type_magic(file_path: str) -> str:
    """Detect real file type from magic bytes — same as terabox bot"""
    try:
        with open(file_path, "rb") as f:
            h = f.read(32)
        if b"ftyp" in h[:12]:                               return "mp4"
        if h[:4] == b"\x1a\x45\xdf\xa3":               return "mkv"
        if h[:4] == b"RIFF" and h[8:12] == b"AVI ":        return "avi"
        if h[:3] == b"FLV":                                  return "flv"
        if h[:3] == b"ID3" or h[:2] in [b"\xff\xfb", b"\xff\xfa"]: return "mp3"
        if h[:4] == b"fLaC":                                 return "flac"
        if h[:4] == b"RIFF" and h[8:12] == b"WAVE":         return "wav"
        if h[:4] == b"OggS":                                 return "ogg"
        if h[:2] == b"\xff\xd8":                          return "jpg"
        if h[:8] == b"\x89PNG\r\n\x1a\n":              return "png"
        if h[:6] in [b"GIF87a", b"GIF89a"]:                 return "gif"
        if h[:4] == b"RIFF" and h[8:12] == b"WEBP":         return "webp"
        if h[:4] == b"%PDF":                                 return "pdf"
        if h[:4] == b"PK\x03\x04":                        return "zip"
        if h[:6] == b"Rar!\x1a\x07":                      return "rar"
        if b"<!DOCTYPE" in h or b"<html" in h.lower():       return "html"
    except Exception:
        pass
    return ""


async def _terabox_download_file(dl_url: str, filename: str, out_dir: str,
                                  cookie: str, hook) -> tuple:
    """Download the actual file from resolved Terabox direct URL"""
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)
    headers = {
        "User-Agent": CHROME_UA,
        "Referer": "https://www.terabox.com/",
        "Accept": "*/*",
        "Accept-Encoding": "identity",
    }
    if cookie: headers["Cookie"] = cookie

    out_file = os.path.join(out_dir, filename)
    async with aiohttp.ClientSession(headers=headers) as s:
        async with s.get(dl_url, timeout=aiohttp.ClientTimeout(total=3600),
                         allow_redirects=True) as resp:
            resp.raise_for_status()
            # Fix filename from Content-Disposition if available
            cd = resp.headers.get("Content-Disposition","")
            if cd:
                m = re.search(r'filename[^;]*=([^;\r\n]+)', cd, re.I)
                if m:
                    from urllib.parse import unquote
                    fname = unquote(m.group(1).strip().strip('"\' '))
                    if fname: out_file = os.path.join(out_dir, clean_filename(fname))

            total = int(resp.headers.get("Content-Length", 0))
            done  = 0
            with open(out_file, "wb") as f:
                async for chunk in resp.content.iter_chunked(131072):
                    f.write(chunk); done += len(chunk)
                    if hook:
                        try: await hook(done, total)
                        except Exception: pass

    # Fix extension from magic bytes
    real_ext = _detect_file_type_magic(out_file)
    if real_ext and real_ext != "html":
        cur_ext = os.path.splitext(out_file)[1].lstrip(".").lower()
        if not cur_ext or cur_ext != real_ext:
            new_path = os.path.splitext(out_file)[0] + "." + real_ext
            try:
                os.rename(out_file, new_path)
                out_file = new_path
            except Exception:
                pass
    elif real_ext == "html":
        os.remove(out_file)
        raise RuntimeError("Got HTML error page — file unavailable or private.")

    meta = {"title": clean_filename(os.path.splitext(os.path.basename(out_file))[0])
                     .replace("_"," ").replace("-"," ").strip()}
    return out_file, meta


async def _terabox_download(url, out_dir, cookie_file, hook) -> tuple:
    """
    Terabox download — 4 methods from terabox bot reference:
    1. Third-party free APIs (no cookies)
    2. Official Terabox API (with cookies)
    3. Page scraping (dlink extraction)
    4. yt-dlp fallback (with proxy)
    """
    from config import TERABOX_COOKIES, YT_PROXY
    import yt_dlp

    os.makedirs(out_dir, exist_ok=True)
    cookie_str = ""
    if TERABOX_COOKIES:
        cookie_str = TERABOX_COOKIES.strip().strip('"').strip("'")

    surl = _extract_terabox_surl(url)
    loop = asyncio.get_event_loop()
    last_err = ""

    # ── Method 1: Third-party free APIs ────────────────────────────────────
    try:
        dl_url, filename = await loop.run_in_executor(None, _terabox_third_party, url)
        if dl_url:
            logger.info("Terabox method 1 success (third-party API)")
            return await _terabox_download_file(dl_url, filename or "terabox_file.mp4",
                                                 out_dir, cookie_str, hook)
    except Exception as e:
        last_err = f"API: {str(e)[:60]}"

    # ── Method 2: Official API with cookies ────────────────────────────────
    if surl and cookie_str:
        try:
            dl_url, filename = await loop.run_in_executor(
                None, _terabox_official_api, surl, cookie_str
            )
            if dl_url:
                logger.info("Terabox method 2 success (official API)")
                return await _terabox_download_file(dl_url, filename or "terabox_file.mp4",
                                                     out_dir, cookie_str, hook)
        except Exception as e:
            last_err += f" | OfficialAPI: {str(e)[:60]}"

    # ── Method 3: Page scraping ─────────────────────────────────────────────
    try:
        dl_url, filename = await loop.run_in_executor(
            None, _terabox_scrape, url, cookie_str
        )
        if dl_url:
            logger.info("Terabox method 3 success (scrape)")
            return await _terabox_download_file(dl_url, filename or "terabox_file.mp4",
                                                 out_dir, cookie_str, hook)
    except Exception as e:
        last_err += f" | Scrape: {str(e)[:60]}"

    # ── Method 4: yt-dlp fallback ───────────────────────────────────────────
    base = {
        "format": "best[ext=mp4]/best",
        "outtmpl": os.path.join(out_dir, "%(title).100s.%(ext)s"),
        "merge_output_format": "mp4",
        "quiet": True, "no_warnings": True,
        "retries": 3, "socket_timeout": 30,
        "http_headers": {"User-Agent": CHROME_UA},
    }
    if cookie_file: base["cookiefile"] = cookie_file
    if hook: base["progress_hooks"] = [hook]

    # Try with proxy first if available
    if YT_PROXY:
        proxy_opts = base.copy()
        proxy_opts["proxy"] = YT_PROXY
        strategies_ydl = [proxy_opts, base]
    else:
        strategies_ydl = [base]

    for opts in strategies_ydl:
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
                logger.info("Terabox method 4 success (yt-dlp)")
                return result, meta
        except Exception as e:
            last_err += f" | ytdlp: {str(e)[:60]}"; continue

    raise RuntimeError(
        f"⛔ **Terabox download failed.**\n\n"
        f"All 4 methods tried:\n"
        f"`{last_err[:200]}`"
    )


# ── Generic yt-dlp ────────────────────────────────────────────────────────
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
        result, meta = await _generic_ydl(url, out_dir, ck, progress_hook, audio_only)
        if not result:
            result, meta = await _scrape_video_host(url, out_dir, progress_hook)
        return result, meta
    except Exception as e:
        try:
            return await _scrape_video_host(url, out_dir, progress_hook)
        except Exception as e2:
            raise RuntimeError(f"Download failed: {str(e)[:120]}")
    finally:
        if ck and os.path.exists(ck):
            try: os.remove(ck)
            except: pass


# ── Direct file (pure aiohttp) ────────────────────────────────────────────
async def download_direct(url: str, out_dir: str, filename: str = None,
                           extra_headers: dict = None, progress_hook=None) -> tuple:
    import aiohttp
    os.makedirs(out_dir, exist_ok=True)

    url_title = get_title_from_url(url)
    hdrs = {
        "User-Agent": CHROME_UA,
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Referer": "/".join(url.split("/")[:3]) + "/",
        **(extra_headers or {})
    }

    async with aiohttp.ClientSession(headers=hdrs) as s:
        async with s.get(url, timeout=aiohttp.ClientTimeout(total=3600),
                         allow_redirects=True) as resp:
            if resp.status in (403, 401):
                hdrs2 = {k: v for k, v in hdrs.items() if k != "Referer"}
                async with s.get(url, timeout=aiohttp.ClientTimeout(total=3600),
                                  headers=hdrs2, allow_redirects=True) as r2:
                    if r2.status in (403, 401):
                        raise RuntimeError(f"❌ {r2.status} — link expired.")
                    resp = r2
            resp.raise_for_status()

            cd = resp.headers.get("Content-Disposition","")
            fname = None
            if cd:
                m = re.search(r'filename[^;]*=([^;\r\n]+)', cd, re.I)
                if m:
                    from urllib.parse import unquote
                    fname = unquote(m.group(1).strip().strip('"\' '))
            if not fname:
                from urllib.parse import unquote
                raw = unquote(url.split("?")[0].rstrip("/").split("/")[-1])
                fname = raw if len(raw) > 3 else f"file_{uuid.uuid4().hex[:8]}"
                if "." not in fname:
                    ext = _ext_from_ct(resp.headers.get("Content-Type","")) or "bin"
                    fname += f".{ext}"

            fname = clean_filename(fname)
            out_file = os.path.join(out_dir, fname)
            total = int(resp.headers.get("Content-Length",0))
            done  = 0
            with open(out_file,"wb") as f:
                async for chunk in resp.content.iter_chunked(131072):
                    f.write(chunk); done += len(chunk)
                    if progress_hook:
                        try: await progress_hook(done, total)
                        except Exception: pass

    meta = {
        "title": url_title or os.path.splitext(fname)[0].replace("_"," ").replace("-"," ").strip(),
        "ext": fname.rsplit(".",1)[-1] if "." in fname else "",
    }
    return out_file, meta


def _ext_from_ct(ct: str) -> str:
    ct = ct.split(";")[0].strip().lower()
    return {
        "video/mp4":"mp4","video/webm":"webm","video/x-matroska":"mkv",
        "audio/mpeg":"mp3","audio/mp4":"m4a","audio/ogg":"ogg",
        "image/jpeg":"jpg","image/png":"png","image/gif":"gif","image/webp":"webp",
        "application/pdf":"pdf","application/zip":"zip",
    }.get(ct,"")


# ── M3U8 ─────────────────────────────────────────────────────────────────
async def download_m3u8(url: str, out_dir: str, progress_hook=None) -> tuple:
    os.makedirs(out_dir, exist_ok=True)
    out_file = os.path.join(out_dir, f"stream_{uuid.uuid4().hex[:8]}.mp4")
    loop = asyncio.get_event_loop()
    def _run():
        cmd = [
            "ffmpeg","-y","-headers",f"User-Agent: {CHROME_UA}\r\n",
            "-allowed_extensions","ALL",
            "-protocol_whitelist","file,http,https,tcp,tls,crypto",
            "-i",url,"-c","copy","-movflags","+faststart",out_file
        ]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if r.returncode != 0: raise RuntimeError(f"ffmpeg: {r.stderr[-200:]}")
            if not os.path.exists(out_file) or os.path.getsize(out_file) < 1000:
                raise RuntimeError("Output empty")
            return out_file
        except subprocess.TimeoutExpired:
            raise RuntimeError("⏱ Stream timed out.")
    try:
        return await asyncio.wait_for(loop.run_in_executor(None,_run), timeout=310), None
    except asyncio.TimeoutError:
        raise RuntimeError("⏱ Stream timed out.")


# ── Google Drive folder (with cookie support) ─────────────────────────────
async def download_gdrive_folder(url, out_dir, progress_hook=None) -> tuple:
    import yt_dlp
    from config import GDRIVE_COOKIES
    os.makedirs(out_dir, exist_ok=True)

    cookie_file = _write_cookie_file(GDRIVE_COOKIES, "gdrive") if GDRIVE_COOKIES else None
    opts = {
        "format": "best",
        "outtmpl": os.path.join(out_dir, "%(title).80s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "noplaylist": False,
        "retries": 3,
        "http_headers": {"User-Agent": CHROME_UA}
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
        logger.info(f"Using Google Drive cookies from {cookie_file}")
    if progress_hook:
        opts["progress_hooks"] = [progress_hook]

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

    try:
        return await loop.run_in_executor(None, _run)
    finally:
        if cookie_file and os.path.exists(cookie_file):
            try: os.remove(cookie_file)
            except: pass


# ── Thumbnails ────────────────────────────────────────────────────────────
def download_thumb_from_url(thumb_url, video_id) -> Optional[str]:
    try:
        import requests as req
        r = req.get(thumb_url, headers={"User-Agent":CHROME_UA}, timeout=10)
        if r.status_code==200 and len(r.content)>500:
            p = f"/tmp/thumb_{video_id}.jpg"
            with open(p,"wb") as f: f.write(r.content)
            return p
    except Exception: pass
    return None

def find_thumbnail(base_path) -> Optional[str]:
    for ext in (".jpg",".jpeg",".webp",".png"):
        t = base_path.rsplit(".",1)[0]+ext
        if os.path.exists(t) and os.path.getsize(t)>500:
            if not t.endswith(".jpg"):
                jpg = t.rsplit(".",1)[0]+".jpg"
                r = subprocess.run(["ffmpeg","-y","-i",t,jpg],capture_output=True)
                if r.returncode==0 and os.path.exists(jpg):
                    try: os.remove(t)
                    except: pass
                    return jpg
            return t
    return None

async def generate_thumbnail(video_path) -> Optional[str]:
    thumb_path = video_path.rsplit(".",1)[0]+"_thumb.jpg"
    loop = asyncio.get_event_loop()
    def _run():
        duration=0
        try:
            r=subprocess.run(["ffprobe","-v","quiet","-print_format","json","-show_format",video_path],
                             capture_output=True,text=True)
            duration=float(json.loads(r.stdout).get("format",{}).get("duration",0))
        except Exception: pass
        for seek in ([int(duration*p) for p in [0.1,0.2,0.3] if duration>5]+[5,2,0]):
            r=subprocess.run(["ffmpeg","-y","-ss",str(seek),"-i",video_path,
                              "-vframes","1","-vf","scale=320:-1","-q:v","3",thumb_path],
                             capture_output=True)
            if r.returncode==0 and os.path.exists(thumb_path) and os.path.getsize(thumb_path)>2000:
                return thumb_path
        return None
    return await loop.run_in_executor(None,_run)

async def remux_to_mp4(input_path) -> str:
    out = input_path.rsplit(".",1)[0]+"_tg.mp4"
    loop = asyncio.get_event_loop()
    def _run():
        r=subprocess.run(["ffmpeg","-y","-i",input_path,"-c","copy",
                          "-movflags","+faststart",out],capture_output=True)
        if r.returncode==0 and os.path.exists(out) and os.path.getsize(out)>500:
            try: os.remove(input_path)
            except: pass
            return out
        return input_path
    return await loop.run_in_executor(None,_run)

def get_video_info(path) -> dict:
    try:
        r=subprocess.run(["ffprobe","-v","quiet","-print_format","json",
                          "-show_streams","-show_format","-select_streams","v:0",path],
                         capture_output=True,text=True)
        data=json.loads(r.stdout)
        stream=(data.get("streams") or [{}])[0]
        dur=float(data.get("format",{}).get("duration",0))
        return {"width":stream.get("width",0),"height":stream.get("height",0),"duration":int(dur)}
    except Exception:
        return {"width":0,"height":0,"duration":0}

async def zip_folder(folder_path,out_path,name="files") -> str:
    zip_path=os.path.join(out_path,f"{clean_filename(name)}.zip")
    loop=asyncio.get_event_loop()
    def _zip():
        with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as zf:
            for fname in os.listdir(folder_path):
                fp=os.path.join(folder_path,fname)
                if os.path.isfile(fp) and not fname.endswith((".part",".ytdl")):
                    zf.write(fp,fname)
        return zip_path
    return await loop.run_in_executor(None,_zip)

def cleanup_files(*paths):
    for p in paths:
        if not p: continue
        try:
            if os.path.isdir(p): shutil.rmtree(p,ignore_errors=True)
            elif os.path.exists(p): os.remove(p)
        except Exception: pass
