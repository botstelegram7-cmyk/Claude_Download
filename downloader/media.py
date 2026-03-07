"""
Serena Bot - Upload Pipeline
Caption: ALWAYS platform original title — never filename
All videos: supports_streaming=True (Telegram inline playback)
GDrive bulk ZIP (storage.googleapis.com): send as-is document
"""
import os, sys, asyncio
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified

from downloader.core import (
    download_with_ytdlp, download_gdrive_folder,
    download_m3u8, download_direct,
    find_thumbnail, download_thumb_from_url,
    generate_thumbnail, remux_to_mp4,
    get_video_info, zip_folder, cleanup_files
)
from utils.helpers import detect_url_type, fmt_size, fmt_duration, get_title_from_url
from utils.progress import ProgressTracker, YtdlpProgressHook
import database as db

VIDEO_EXTS = {"mp4","mkv","webm","avi","mov","flv","ts","m2ts","3gp","m4v","wmv"}
AUDIO_EXTS = {"mp3","aac","flac","wav","ogg","m4a","opus","wma"}
IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","bmp","tiff"}

_gdrive_pending: dict = {}


def _ext(p):
    return p.rsplit(".", 1)[-1].lower() if "." in p else ""

async def _safe_edit(msg, text):
    for _ in range(3):
        try: await msg.edit_text(text); return
        except FloodWait as e: await asyncio.sleep(e.value + 1)
        except (MessageNotModified, Exception): return

async def _flood_send(coro, retries=3):
    for i in range(retries):
        try: return await coro
        except FloodWait as e: await asyncio.sleep(e.value + 2)
        except Exception as e:
            if i == retries - 1: raise
            await asyncio.sleep(2)


def _make_caption(url: str, filename: str, meta: Optional[dict],
                  file_size: int, platform: str = "") -> str:
    """
    Caption priority:
    1. meta['title'] — from yt-dlp (platform original title)
    2. meta['fulltitle']
    3. title from URL ?title= param (for direct links)
    4. filename cleaned up (last resort only)

    NEVER use raw filename as-is.
    """
    title = ""

    # 1. yt-dlp metadata title (most accurate — YouTube/Instagram/TikTok etc.)
    if meta:
        title = (
            meta.get("title") or
            meta.get("fulltitle") or
            meta.get("track") or
            ""
        ).strip()

    # 2. URL ?title= param (CDN direct links like vidssave.com)
    if not title and url:
        title = get_title_from_url(url)

    # 3. Cleaned filename — absolute last resort
    if not title:
        title = os.path.splitext(filename)[0]
        title = title.replace("_", " ").replace("-", " ").strip()
        title = title[:80]

    title = title[:80]

    # Extra metadata
    uploader = ""
    duration = 0
    views    = 0
    if meta:
        uploader = (
            meta.get("uploader") or meta.get("channel") or
            meta.get("artist") or meta.get("creator") or ""
        ).strip()[:40]
        duration = int(meta.get("duration") or 0)
        views    = int(meta.get("view_count") or 0)

    ext = _ext(filename).upper() or (meta.get("ext", "").upper() if meta else "")

    lines = [f"**{title}**"]
    if uploader:  lines.append(f"👤 `{uploader}`")

    # Compact stats line
    stats = []
    if duration: stats.append(f"⏱ `{fmt_duration(duration)}`")
    stats.append(f"📦 `{fmt_size(file_size)}`")
    if ext:      stats.append(f"🎞 `{ext}`")
    lines.append("  •  ".join(stats))

    if views >= 1000:
        lines.append(f"👁 `{views:,}` views")
    if platform:
        lines.append(f"🌐 `{platform}`")

    return "\n".join(lines)


def _upload_cb(tracker):
    if not tracker: return None
    async def _cb(c, t): await tracker.uploading(c, t)
    return _cb


# ── Google Drive choice handler ───────────────────────────────────────────
async def handle_gdrive_choice(client, query, choice):
    uid = query.from_user.id
    pending = _gdrive_pending.pop(uid, None)
    if not pending:
        await query.answer("⚠️ Session expired.", show_alert=True); return
    files, meta, out_dir, orig_msg, sm = pending
    await query.answer()
    try:
        name = (meta or {}).get("title", "Google Drive Files") if meta else "Google Drive Files"
        if choice == "zip":
            await _safe_edit(sm, "📦 **Creating ZIP...**")
            zp = await zip_folder(out_dir, f"/tmp/serena_dl/{uid}", name)
            sz = os.path.getsize(zp)
            await _safe_edit(sm, f"📤 **Uploading** `{fmt_size(sz)}`...")
            await _flood_send(client.send_document(
                chat_id=orig_msg.chat.id, document=zp,
                caption=f"📦 **{name[:60]}**\n📂 `{len(files)} files` · `{fmt_size(sz)}`",
                reply_to_message_id=orig_msg.id,
            ))
            await db.log_download(uid, "gdrive", title=name, file_size=sz, status="done")
            await db.increment_daily_count(uid)
            cleanup_files(zp)
        else:
            await _safe_edit(sm, f"📤 **Sending {len(files)} files...**")
            sent = 0
            for fp in files:
                if not os.path.exists(fp) or os.path.getsize(fp) == 0: continue
                try:
                    await _upload_single(client, orig_msg, fp, None, uid,
                                         None, None, url="", platform="Google Drive")
                    sent += 1
                    await asyncio.sleep(0.5)
                except Exception: pass
            await _safe_edit(sm, f"✅ **Sent {sent}/{len(files)} files!**")
    except Exception as e:
        await _safe_edit(sm, f"❌ `{str(e)[:200]}`")
    finally:
        cleanup_files(out_dir)
        try: await sm.delete()
        except: pass


# ── Main process_download ─────────────────────────────────────────────────
async def process_download(
    client: Client, message: Message,
    url: str, quality: str = "best",
    audio_only: bool = False,
    status_msg: Optional[Message] = None,
    platform: str = "",
) -> bool:
    user_id  = message.from_user.id
    url_type = detect_url_type(url)
    out_dir  = f"/tmp/serena_dl/{user_id}/{os.urandom(4).hex()}"
    os.makedirs(out_dir, exist_ok=True)

    # Prefetch title for progress bar
    pre_title = get_title_from_url(url)

    tracker = ProgressTracker(
        message=status_msg,
        title=pre_title,
        action="Downloading",
        interval=3.5,
    ) if status_msg else None

    loop = asyncio.get_event_loop()
    fp = meta = None

    try:
        # ── M3U8 ──────────────────────────────────────────────────────────
        if url_type == "m3u8":
            if status_msg:
                await _safe_edit(status_msg, "📡 **Downloading stream...**\n⏱ Max 5 minutes.")
            fp, meta = await download_m3u8(url, out_dir)

        # ── Direct file / GDrive bulk export ──────────────────────────────
        elif url_type in ("direct_video", "direct_audio", "direct_image", "direct_doc"):
            async def _dh(c, t):
                if tracker: await tracker.hook(c, t)
            if status_msg: await _safe_edit(status_msg, "⬇️ **Downloading...**")
            fp, meta = await download_direct(url, out_dir, progress_hook=_dh)

            # If it's a ZIP / archive — send as-is document
            if fp and _ext(fp) in ("zip", "rar", "tar", "7z"):
                sz = os.path.getsize(fp)
                title = (meta or {}).get("title", "") or get_title_from_url(url) or os.path.basename(fp)
                if status_msg: await _safe_edit(status_msg, f"📤 **Uploading archive** `{fmt_size(sz)}`...")
                await _flood_send(client.send_document(
                    chat_id=message.chat.id,
                    document=fp,
                    caption=f"📦 **{title[:60]}**\n📦 `{fmt_size(sz)}`",
                    reply_to_message_id=message.id,
                ))
                await db.log_download(user_id, url, title=title, file_size=sz, status="done")
                await db.increment_daily_count(user_id)
                cleanup_files(fp)
                if status_msg:
                    try: await status_msg.delete()
                    except: pass
                return True

        # ── Google Drive folder ────────────────────────────────────────────
        elif url_type == "gdrive" and "/drive/folders/" in url:
            if status_msg: await _safe_edit(status_msg, "📁 **Fetching Drive folder...**")
            files, meta = await download_gdrive_folder(url, out_dir)
            if not files:
                if status_msg: await _safe_edit(status_msg, "❌ No files found.")
                await db.log_download(user_id, url, status="failed")
                return False
            name    = (meta or {}).get("title", "Google Drive Files") if meta else "Google Drive Files"
            total_s = sum(os.path.getsize(f) for f in files if os.path.exists(f))
            _gdrive_pending[user_id] = (files, meta, out_dir, message, status_msg)
            try:
                await status_msg.edit_text(
                    f"📁 **Google Drive Folder**\n\n"
                    f"📂 `{name[:40]}`\n"
                    f"🗃 `{len(files)} files` · `{fmt_size(total_s)}`\n\n"
                    f"**How to receive?**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📦 ZIP", callback_data="gdrive_zip"),
                        InlineKeyboardButton("📂 Individual", callback_data="gdrive_individual"),
                    ]])
                )
            except Exception: pass
            return True

        # ── yt-dlp platforms (YouTube, Instagram, TikTok, Twitter, etc.) ──
        else:
            if status_msg: await _safe_edit(status_msg, "🔍 **Fetching info...**")
            # Try to get real title before download for progress bar
            try:
                import yt_dlp
                def _get_title():
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                        i = ydl.extract_info(url, download=False)
                        return (i.get("title") or "")[:35] if i else ""
                t = await loop.run_in_executor(None, _get_title)
                if t and tracker: tracker.title = t
            except Exception: pass

            hook = YtdlpProgressHook(tracker, loop) if tracker else None
            fp, meta = await download_with_ytdlp(url, out_dir, quality, audio_only, hook)

        if not fp:
            if status_msg: await _safe_edit(status_msg, "❌ **Download failed.** No file returned.")
            await db.log_download(user_id, url, status="failed")
            return False

        # Playlist (list of files) → ZIP
        if isinstance(fp, list):
            name = (meta or {}).get("title", "playlist") if meta else "playlist"
            if status_msg: await _safe_edit(status_msg, "📦 **Zipping playlist...**")
            zp = await zip_folder(out_dir, f"/tmp/serena_dl/{user_id}", name)
            sz = os.path.getsize(zp)
            if status_msg: await _safe_edit(status_msg, f"📤 **Uploading ZIP** `{fmt_size(sz)}`...")
            await _flood_send(client.send_document(
                chat_id=message.chat.id, document=zp,
                caption=f"📦 **{name[:60]}**\n📂 `{len(fp)} files` · `{fmt_size(sz)}`",
                reply_to_message_id=message.id,
            ))
            await db.log_download(user_id, url, title=name, file_size=sz, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(zp)
        else:
            await _upload_single(client, message, fp, meta, user_id,
                                  tracker, status_msg, url=url, platform=platform)

        if status_msg:
            try: await status_msg.delete()
            except: pass
        return True

    except Exception as e:
        if status_msg:
            await _safe_edit(status_msg, f"❌ **Failed:**\n\n`{str(e)[:280]}`")
        await db.log_download(user_id, url, status="failed")
        return False
    finally:
        if user_id not in _gdrive_pending:
            cleanup_files(out_dir)


# ── Single file upload ────────────────────────────────────────────────────
async def _upload_single(client, message, fp, meta, user_id,
                          tracker, status_msg, url="", platform=""):
    if not os.path.exists(fp) or os.path.getsize(fp) == 0:
        raise RuntimeError("File missing or empty after download.")

    file_size = os.path.getsize(fp)
    orig_name = os.path.basename(fp)
    ext       = _ext(fp)
    cap       = _make_caption(url, orig_name, meta, file_size, platform)
    up_cb     = _upload_cb(tracker)

    if tracker and meta:
        tracker.title = (meta.get("title") or "")[:35]

    # Smart video detection: ext + meta vcodec + ffprobe fallback
    is_video = ext in VIDEO_EXTS
    if not is_video and meta:
        if (meta.get("ext","").lower() in VIDEO_EXTS or
            (meta.get("vcodec") and meta.get("vcodec") != "none")):
            is_video = True
    # ffprobe fallback: detect video stream even without recognized ext
    if not is_video and ext not in AUDIO_EXTS and ext not in IMAGE_EXTS:
        try:
            import subprocess as _sp, json as _json
            r = _sp.run(
                ["ffprobe","-v","quiet","-print_format","json",
                 "-show_streams","-select_streams","v:0", fp],
                capture_output=True, text=True, timeout=8
            )
            if r.returncode == 0 and _json.loads(r.stdout).get("streams"):
                is_video = True
        except Exception:
            pass

    if is_video:
        if status_msg: await _safe_edit(status_msg, "🔄 **Preparing video...**")
        remuxed = await remux_to_mp4(fp)
        if os.path.exists(remuxed) and os.path.getsize(remuxed) > 1000:
            fp = remuxed

        thumb = None
        if meta:
            tu = meta.get("thumbnail"); tid = meta.get("id", "temp")
            if tu: thumb = download_thumb_from_url(tu, tid)
        if not thumb: thumb = find_thumbnail(fp)
        if not thumb:
            if status_msg: await _safe_edit(status_msg, "🖼️ **Generating thumbnail...**")
            thumb = await generate_thumbnail(fp)

        vi        = get_video_info(fp)
        file_size = os.path.getsize(fp)
        cap       = _make_caption(url, os.path.basename(fp), meta, file_size, platform)

        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading** `{fmt_size(file_size)}`...")
        await _flood_send(client.send_video(
            chat_id=message.chat.id,
            video=fp,
            thumb=thumb,
            caption=cap,
            supports_streaming=True,
            width=vi["width"] or None,
            height=vi["height"] or None,
            duration=vi["duration"] or None,
            progress=up_cb,
            reply_to_message_id=message.id,
        ))
        if thumb: cleanup_files(thumb)

    elif ext in AUDIO_EXTS:
        title  = (meta.get("title") or meta.get("track") or "").strip() if meta else ""
        artist = (meta.get("uploader") or meta.get("artist") or "").strip() if meta else ""
        if not title:
            title = get_title_from_url(url) or os.path.splitext(orig_name)[0]
        thumb = find_thumbnail(fp)
        if not thumb and meta:
            tu = meta.get("thumbnail")
            if tu: thumb = download_thumb_from_url(tu, meta.get("id", "temp"))
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading audio** `{fmt_size(file_size)}`...")
        await _flood_send(client.send_audio(
            chat_id=message.chat.id, audio=fp,
            thumb=thumb, caption=cap,
            title=title[:64] if title else None,
            performer=artist[:64] if artist else None,
            progress=up_cb,
            reply_to_message_id=message.id,
        ))
        if thumb: cleanup_files(thumb)

    elif ext in IMAGE_EXTS:
        if status_msg: await _safe_edit(status_msg, "📤 **Uploading image...**")
        await _flood_send(client.send_photo(
            chat_id=message.chat.id, photo=fp, caption=cap,
            progress=up_cb, reply_to_message_id=message.id,
        ))

    else:
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading** `{fmt_size(file_size)}`...")
        await _flood_send(client.send_document(
            chat_id=message.chat.id, document=fp, caption=cap,
            progress=up_cb, reply_to_message_id=message.id,
        ))

    await db.log_download(user_id, url, title=orig_name, file_size=file_size, status="done")
    await db.increment_daily_count(user_id)
    cleanup_files(fp)
