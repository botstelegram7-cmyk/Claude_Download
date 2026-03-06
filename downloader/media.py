"""
Serena Downloader Bot - Upload Pipeline
- Upload progress bar
- Thumbnail from URL or generated
- Correct file type detection
- Google Drive folder: ZIP or individual
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
from utils.helpers import detect_url_type, fmt_size, fmt_duration, BULLET
from utils.progress import ProgressTracker, YtdlpProgressHook
import database as db

VIDEO_EXTS = {"mp4","mkv","webm","avi","mov","flv","ts","m2ts","3gp"}
AUDIO_EXTS = {"mp3","aac","flac","wav","ogg","m4a","opus","wma"}
IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","bmp","tiff"}

_gdrive_pending: dict = {}


def _ext(p): return p.rsplit(".",1)[-1].lower() if "." in p else ""


async def _safe_edit(msg: Message, text: str):
    for _ in range(3):
        try:
            await msg.edit_text(text)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except (MessageNotModified, Exception):
            return


async def _flood_send(coro, retries=3):
    for i in range(retries):
        try:
            return await coro
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
        except Exception as e:
            if i == retries - 1:
                raise
            await asyncio.sleep(2)


def _caption(filename, meta, file_size):
    if not meta:
        return f"📁 **{filename[:60]}**\n{BULLET} Size: `{fmt_size(file_size)}`"
    title    = meta.get("title", filename)[:60]
    uploader = meta.get("uploader") or meta.get("channel") or ""
    duration = meta.get("duration", 0)
    views    = meta.get("view_count", 0)
    ext      = meta.get("ext","")
    url      = meta.get("webpage_url","")
    lines    = [f"🎬 **{title}**"]
    if uploader: lines.append(f"{BULLET} Channel: `{uploader[:40]}`")
    if duration: lines.append(f"{BULLET} Duration: `{fmt_duration(int(duration))}`")
    if views:    lines.append(f"{BULLET} Views: `{views:,}`")
    lines.append(f"{BULLET} Size: `{fmt_size(file_size)}`")
    if ext:      lines.append(f"{BULLET} Format: `{ext.upper()}`")
    if url:      lines.append(f"{BULLET} [Source]({url})")
    return "\n".join(lines)


# Upload progress callback factory
def _upload_progress(tracker: Optional[ProgressTracker]):
    if not tracker:
        return None
    async def _cb(current, total):
        await tracker.uploading(current, total)
    return _cb


async def handle_gdrive_choice(client, query, choice):
    user_id = query.from_user.id
    pending = _gdrive_pending.pop(user_id, None)
    if not pending:
        await query.answer("⚠️ Session expired, resend URL.", show_alert=True)
        return
    files, meta, out_dir, orig_msg, status_msg = pending
    await query.answer()
    try:
        name = (meta or {}).get("title","Google Drive Files") if meta else "Google Drive Files"
        if choice == "zip":
            await _safe_edit(status_msg, "📦 **Creating ZIP...**")
            zp = await zip_folder(out_dir, f"/tmp/serena_dl/{user_id}", name)
            sz = os.path.getsize(zp)
            await _safe_edit(status_msg, f"📤 **Uploading ZIP** `{fmt_size(sz)}`...")
            await _flood_send(client.send_document(
                chat_id=orig_msg.chat.id,
                document=zp,
                caption=f"📦 **{name[:60]}**\n{BULLET} `{len(files)} files` · `{fmt_size(sz)}`",
                reply_to_message_id=orig_msg.id,
            ))
            await db.log_download(user_id, "gdrive", title=name, file_size=sz, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(zp)
        else:
            await _safe_edit(status_msg, f"📤 **Sending {len(files)} files...**")
            sent = 0
            for fp in files:
                if not os.path.exists(fp) or os.path.getsize(fp) == 0:
                    continue
                try:
                    await _upload_single(client, orig_msg, fp, None, "gdrive", user_id, None, None)
                    sent += 1
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            await _safe_edit(status_msg, f"✅ **Sent {sent}/{len(files)} files!**")
    except Exception as e:
        await _safe_edit(status_msg, f"❌ `{str(e)[:200]}`")
    finally:
        cleanup_files(out_dir)
        try: await status_msg.delete()
        except: pass


async def process_download(
    client: Client,
    message: Message,
    url: str,
    quality: str = "best",
    audio_only: bool = False,
    status_msg: Optional[Message] = None,
) -> bool:
    user_id = message.from_user.id
    url_type = detect_url_type(url)
    out_dir = f"/tmp/serena_dl/{user_id}/{os.urandom(4).hex()}"
    os.makedirs(out_dir, exist_ok=True)

    tracker = ProgressTracker(
        message=status_msg,
        title=url.split("/")[-1][:30] or "media",
        action="Downloading",
        interval=3.5
    ) if status_msg else None

    loop = asyncio.get_event_loop()
    file_path = None
    meta = None

    try:
        # ── M3U8 ──
        if url_type == "m3u8":
            if status_msg: await _safe_edit(status_msg, "📡 **Downloading M3U8 stream...**")
            file_path, meta = await download_m3u8(url, out_dir)

        # ── Direct file ──
        elif url_type in ("direct_video","direct_audio","direct_image","direct_doc"):
            async def _dh(c, t):
                if tracker: await tracker.hook(c, t)
            if status_msg: await _safe_edit(status_msg, "⬇️ **Starting download...**")
            file_path, meta = await download_direct(url, out_dir, progress_hook=_dh)

        # ── Google Drive FOLDER ──
        elif url_type == "gdrive" and "/drive/folders/" in url:
            if status_msg: await _safe_edit(status_msg, "📁 **Fetching Drive folder...**")
            files, meta = await download_gdrive_folder(url, out_dir)
            if not files:
                if status_msg: await _safe_edit(status_msg, "❌ No files found in folder.")
                await db.log_download(user_id, url, status="failed")
                return False
            name = (meta or {}).get("title","Google Drive Files") if meta else "Google Drive Files"
            total_sz = sum(os.path.getsize(f) for f in files if os.path.exists(f))
            _gdrive_pending[user_id] = (files, meta, out_dir, message, status_msg)
            try:
                await status_msg.edit_text(
                    f"📁 **Google Drive Folder**\n\n"
                    f"{BULLET} Name: `{name[:40]}`\n"
                    f"{BULLET} Files: `{len(files)}`\n"
                    f"{BULLET} Size: `{fmt_size(total_sz)}`\n\n"
                    f"**How to receive?**",
                    reply_markup=InlineKeyboardMarkup([[
                        InlineKeyboardButton("📦 ZIP", callback_data="gdrive_zip"),
                        InlineKeyboardButton("📂 Individual", callback_data="gdrive_individual"),
                    ]])
                )
            except Exception:
                pass
            return True  # wait for callback

        # ── yt-dlp platforms ──
        else:
            if status_msg: await _safe_edit(status_msg, "🔍 **Fetching info...**")
            try:
                import yt_dlp
                def _get_title():
                    with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                        i = ydl.extract_info(url, download=False)
                        return i.get("title","")[:35] if i else ""
                t = await loop.run_in_executor(None, _get_title)
                if t and tracker: tracker.title = t
            except Exception:
                pass

            hook = YtdlpProgressHook(tracker, loop) if tracker else None
            file_path, meta = await download_with_ytdlp(url, out_dir, quality, audio_only, hook)

        if not file_path:
            if status_msg: await _safe_edit(status_msg, "❌ **Download failed.**")
            await db.log_download(user_id, url, status="failed")
            return False

        # ── Playlist → ZIP ──
        if isinstance(file_path, list):
            name = (meta or {}).get("title","playlist") if meta else "playlist"
            if status_msg: await _safe_edit(status_msg, "📦 **Zipping playlist...**")
            zp = await zip_folder(out_dir, f"/tmp/serena_dl/{user_id}", name)
            sz = os.path.getsize(zp)
            if status_msg: await _safe_edit(status_msg, f"📤 **Uploading ZIP** `{fmt_size(sz)}`...")
            await _flood_send(client.send_document(
                chat_id=message.chat.id,
                document=zp,
                caption=f"📦 **{name[:60]}**\n{BULLET} `{len(file_path)} files` · `{fmt_size(sz)}`",
                reply_to_message_id=message.id,
            ))
            await db.log_download(user_id, url, title=name, file_size=sz, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(zp)
        else:
            await _upload_single(client, message, file_path, meta, url, user_id, tracker, status_msg)

        if status_msg:
            try: await status_msg.delete()
            except: pass
        return True

    except Exception as e:
        if status_msg:
            await _safe_edit(status_msg, f"❌ **Failed:**\n`{str(e)[:280]}`")
        await db.log_download(user_id, url, status="failed")
        return False
    finally:
        if user_id not in _gdrive_pending:
            cleanup_files(out_dir)


async def _upload_single(client, message, fp, meta, url, user_id, tracker, status_msg):
    if not os.path.exists(fp) or os.path.getsize(fp) == 0:
        raise RuntimeError("File empty or missing after download.")

    file_size = os.path.getsize(fp)
    orig_name = os.path.basename(fp)
    ext = _ext(fp)
    cap = _caption(orig_name, meta, file_size)
    up_cb = _upload_progress(tracker)

    # ── VIDEO ──
    if ext in VIDEO_EXTS:
        if status_msg: await _safe_edit(status_msg, "🔄 **Optimizing for Telegram...**")
        fp = await remux_to_mp4(fp)

        # Best thumbnail: original URL → file-based → generated
        thumb = None
        if meta:
            tu = meta.get("thumbnail")
            tid = meta.get("id","temp")
            if tu: thumb = download_thumb_from_url(tu, tid)
        if not thumb: thumb = find_thumbnail(fp)
        if not thumb:
            if status_msg: await _safe_edit(status_msg, "🖼️ **Getting thumbnail...**")
            thumb = await generate_thumbnail(fp)

        vi = get_video_info(fp)
        file_size = os.path.getsize(fp)
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

    # ── AUDIO ──
    elif ext in AUDIO_EXTS:
        title  = (meta or {}).get("title", orig_name) if meta else orig_name
        artist = (meta or {}).get("uploader","") if meta else ""
        thumb  = find_thumbnail(fp)
        if not thumb and meta:
            tu = meta.get("thumbnail")
            if tu: thumb = download_thumb_from_url(tu, meta.get("id","temp"))
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading audio** `{fmt_size(file_size)}`...")
        await _flood_send(client.send_audio(
            chat_id=message.chat.id,
            audio=fp,
            thumb=thumb,
            caption=cap,
            title=title[:64] if title else None,
            performer=artist[:64] if artist else None,
            progress=up_cb,
            reply_to_message_id=message.id,
        ))
        if thumb: cleanup_files(thumb)

    # ── IMAGE ──
    elif ext in IMAGE_EXTS:
        if status_msg: await _safe_edit(status_msg, "📤 **Uploading image...**")
        await _flood_send(client.send_photo(
            chat_id=message.chat.id,
            photo=fp,
            caption=cap,
            progress=up_cb,
            reply_to_message_id=message.id,
        ))

    # ── DOCUMENT ──
    else:
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading file** `{fmt_size(file_size)}`...")
        await _flood_send(client.send_document(
            chat_id=message.chat.id,
            document=fp,
            caption=cap,
            progress=up_cb,
            reply_to_message_id=message.id,
        ))

    await db.log_download(user_id, url, title=orig_name, file_size=file_size, status="done")
    await db.increment_daily_count(user_id)
    cleanup_files(fp)
