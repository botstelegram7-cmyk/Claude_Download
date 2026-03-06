"""
Serena Downloader Bot - Upload Pipeline
"""
import os, sys, asyncio
from typing import Optional

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, MessageNotModified

from downloader.core import (
    download_with_ytdlp, download_m3u8, download_direct,
    find_thumbnail, generate_thumbnail, remux_to_mp4,
    get_video_info, zip_folder, cleanup_files
)
from utils.helpers import detect_url_type, fmt_size, fmt_duration, BULLET
from utils.progress import ProgressTracker, YtdlpProgressHook
import database as db

VIDEO_EXTS = {"mp4","mkv","webm","avi","mov","flv","ts","m2ts","3gp"}
AUDIO_EXTS = {"mp3","aac","flac","wav","ogg","m4a","opus","wma"}
IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","bmp","tiff"}


def _ext(path: str) -> str:
    return path.rsplit(".",1)[-1].lower() if "." in path else ""


async def _safe_edit(msg: Message, text: str):
    for _ in range(3):
        try:
            await msg.edit_text(text)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except (MessageNotModified, Exception):
            return


async def _flood_call(coro, retries=3):
    for attempt in range(retries):
        try:
            return await coro
        except FloodWait as e:
            await asyncio.sleep(e.value + 2)
        except Exception as e:
            if attempt == retries - 1:
                raise
            await asyncio.sleep(2)


def _build_caption(filename: str, meta: Optional[dict], file_size: int) -> str:
    if not meta:
        return f"📁 **{filename[:60]}**\n{BULLET} Size: `{fmt_size(file_size)}`"
    title    = meta.get("title", filename)[:60]
    uploader = meta.get("uploader") or meta.get("channel") or ""
    duration = meta.get("duration", 0)
    views    = meta.get("view_count", 0)
    ext      = meta.get("ext", "")
    url      = meta.get("webpage_url", "")

    lines = [f"🎬 **{title}**"]
    if uploader:  lines.append(f"{BULLET} Channel: `{uploader[:40]}`")
    if duration:  lines.append(f"{BULLET} Duration: `{fmt_duration(int(duration))}`")
    if views:     lines.append(f"{BULLET} Views: `{views:,}`")
    lines.append(f"{BULLET} Size: `{fmt_size(file_size)}`")
    if ext:       lines.append(f"{BULLET} Format: `{ext.upper()}`")
    if url:       lines.append(f"{BULLET} [Source]({url})")
    return "\n".join(lines)


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
    run_id = os.urandom(4).hex()
    out_dir = f"/tmp/serena_dl/{user_id}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    tracker = ProgressTracker(
        message=status_msg,
        title=url.split("/")[-1][:30] or "media",
        action="Downloading",
        interval=3.5
    ) if status_msg else None

    loop = asyncio.get_event_loop()

    try:
        file_path = None
        meta = None

        # ── M3U8 ──
        if url_type == "m3u8":
            if status_msg: await _safe_edit(status_msg, "📡 **Downloading M3U8 stream...**")
            file_path, meta = await download_m3u8(url, out_dir)

        # ── Direct file ──
        elif url_type in ("direct_video","direct_audio","direct_image","direct_doc"):
            async def direct_hook(c, t):
                if tracker: await tracker.hook(c, t)
            if status_msg: await _safe_edit(status_msg, "⬇️ **Starting download...**")
            file_path, meta = await download_direct(url, out_dir, progress_hook=direct_hook)

        # ── yt-dlp (YouTube, Instagram, TikTok, etc.) ──
        else:
            # Pre-fetch title for progress display
            if status_msg: await _safe_edit(status_msg, "🔍 **Fetching media info...**")
            try:
                import yt_dlp
                def _title():
                    with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                        i = ydl.extract_info(url, download=False)
                        return i.get("title","")[:40] if i else ""
                t = await loop.run_in_executor(None, _title)
                if t and tracker:
                    tracker.title = t
            except Exception:
                pass

            hook = YtdlpProgressHook(tracker, loop) if tracker else None
            file_path, meta = await download_with_ytdlp(url, out_dir, quality, audio_only, hook)

        if not file_path:
            if tracker: await tracker.failed("Media could not be retrieved.")
            else:
                if status_msg: await _safe_edit(status_msg, "❌ **Download failed.** No file returned.")
            await db.log_download(user_id, url, status="failed")
            return False

        # ── Playlist → ZIP ──
        if isinstance(file_path, list):
            if not file_path:
                await db.log_download(user_id, url, status="failed")
                return False
            playlist_name = (meta or {}).get("title","playlist") if meta else "playlist"
            if status_msg: await _safe_edit(status_msg, "📦 **Zipping playlist files...**")
            zip_path = await zip_folder(out_dir, f"/tmp/serena_dl/{user_id}", playlist_name)
            zip_size = os.path.getsize(zip_path)
            if status_msg: await _safe_edit(status_msg, f"📤 **Uploading ZIP** `{fmt_size(zip_size)}`...")
            await _flood_call(
                client.send_document(
                    chat_id=message.chat.id,
                    document=zip_path,
                    caption=f"📦 **{playlist_name[:60]}**\n{BULLET} `{len(file_path)} files` · `{fmt_size(zip_size)}`",
                    reply_to_message_id=message.id,
                )
            )
            await db.log_download(user_id, url, title=playlist_name, file_size=zip_size, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(zip_path)

        # ── Single file ──
        else:
            await _upload_single(client, message, file_path, meta, url, user_id, tracker, status_msg)

        if status_msg:
            try: await status_msg.delete()
            except: pass
        return True

    except Exception as e:
        err_text = str(e)
        if status_msg:
            await _safe_edit(status_msg, f"❌ **Failed:**\n`{err_text[:280]}`")
        await db.log_download(user_id, url, status="failed")
        return False
    finally:
        cleanup_files(out_dir)


async def _upload_single(client, message, fp, meta, url, user_id, tracker, status_msg):
    if not os.path.exists(fp):
        raise RuntimeError("Downloaded file not found on disk.")

    file_size = os.path.getsize(fp)
    if file_size == 0:
        raise RuntimeError("Downloaded file is empty.")

    orig_name = os.path.basename(fp)
    ext = _ext(fp)
    caption = _build_caption(orig_name, meta, file_size)

    # ── VIDEO ──
    if ext in VIDEO_EXTS:
        # Remux to streamable MP4
        if status_msg: await _safe_edit(status_msg, "🔄 **Optimizing for Telegram...**")
        fp = await remux_to_mp4(fp)

        # Thumbnail: original first, then generated
        thumb = find_thumbnail(fp)
        if not thumb:
            if status_msg: await _safe_edit(status_msg, "🖼️ **Generating thumbnail...**")
            thumb = await generate_thumbnail(fp)

        vinfo = get_video_info(fp)
        file_size = os.path.getsize(fp)
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading video** `{fmt_size(file_size)}`...")

        sent = await _flood_call(
            client.send_video(
                chat_id=message.chat.id,
                video=fp,
                thumb=thumb,
                caption=caption,
                supports_streaming=True,
                width=vinfo["width"] or None,
                height=vinfo["height"] or None,
                duration=vinfo["duration"] or None,
                reply_to_message_id=message.id,
            )
        )
        if thumb: cleanup_files(thumb)

    # ── AUDIO ──
    elif ext in AUDIO_EXTS:
        title    = (meta or {}).get("title", orig_name) if meta else orig_name
        artist   = (meta or {}).get("uploader","") if meta else ""
        thumb    = find_thumbnail(fp)
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading audio** `{fmt_size(file_size)}`...")
        sent = await _flood_call(
            client.send_audio(
                chat_id=message.chat.id,
                audio=fp,
                thumb=thumb,
                caption=caption,
                title=title[:64] if title else None,
                performer=artist[:64] if artist else None,
                reply_to_message_id=message.id,
            )
        )
        if thumb: cleanup_files(thumb)

    # ── IMAGE ──
    elif ext in IMAGE_EXTS:
        if status_msg: await _safe_edit(status_msg, "📤 **Uploading image...**")
        sent = await _flood_call(
            client.send_photo(
                chat_id=message.chat.id,
                photo=fp,
                caption=caption,
                reply_to_message_id=message.id,
            )
        )

    # ── DOCUMENT (PDF, ZIP, etc.) ──
    else:
        if status_msg: await _safe_edit(status_msg, f"📤 **Uploading file** `{fmt_size(file_size)}`...")
        sent = await _flood_call(
            client.send_document(
                chat_id=message.chat.id,
                document=fp,
                caption=caption,
                reply_to_message_id=message.id,
            )
        )

    await db.log_download(user_id, url, title=orig_name, file_size=file_size, status="done")
    await db.increment_daily_count(user_id)
    cleanup_files(fp)
