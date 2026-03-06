"""
Serena Downloader Bot - Media Upload Pipeline
"""
import os, sys, asyncio
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from downloader.core import (
    download_with_ytdlp, download_m3u8, download_direct,
    find_thumbnail, generate_thumbnail, remux_to_mp4,
    get_video_dimensions, zip_folder, cleanup_files
)
from utils.helpers import detect_url_type, fmt_size
from utils.progress import ProgressTracker, YtdlpProgressHook
import database as db

YTDLP_TYPES = {"youtube","instagram","tiktok","twitter","facebook","terabox","generic","gdrive"}
DIRECT_TYPES = {"direct_video","direct_audio","direct_image","direct_doc"}
VIDEO_EXTS = {"mp4","mkv","webm","avi","mov","flv","ts"}
AUDIO_EXTS = {"mp3","aac","flac","wav","ogg","m4a","opus"}
IMAGE_EXTS = {"jpg","jpeg","png","gif","webp","bmp"}


def _ext(path: str) -> str:
    return path.rsplit(".",1)[-1].lower() if "." in path else ""


async def _safe_edit(msg: Message, text: str):
    from pyrogram.errors import MessageNotModified
    for _ in range(3):
        try:
            await msg.edit_text(text)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except MessageNotModified:
            return
        except Exception:
            return


async def _flood_send(coro, retries=3):
    for _ in range(retries):
        try:
            return await coro
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            raise
    return None


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

    try:
        file_path = None
        meta = None

        if url_type == "m3u8":
            if tracker: await _safe_edit(status_msg, "📡 **Downloading M3U8 stream...**")
            file_path, meta = await download_m3u8(url, out_dir)

        elif url_type in DIRECT_TYPES:
            async def direct_hook(c, t):
                if tracker: await tracker.hook(c, t)
            if tracker: await _safe_edit(status_msg, "⬇️ **Starting download...**")
            file_path, meta = await download_direct(url, out_dir, progress_hook=direct_hook)

        else:
            # Try to pre-fetch title
            if tracker: await _safe_edit(status_msg, "🔍 **Fetching media info...**")
            try:
                import yt_dlp
                def _get_title():
                    with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                        info = ydl.extract_info(url, download=False)
                        return info.get("title", "")[:40] if info else ""
                t = await loop.run_in_executor(None, _get_title)
                if t and tracker: tracker.title = t
            except Exception:
                pass

            hook = YtdlpProgressHook(tracker, loop) if tracker else None
            file_path, meta = await download_with_ytdlp(url, out_dir, quality, audio_only, hook)

        if not file_path:
            if tracker: await tracker.failed("Media could not be retrieved.")
            await db.log_download(user_id, url, status="failed")
            return False

        # Handle playlist (list of file paths)
        if isinstance(file_path, list):
            # Zip the whole folder
            if tracker: await _safe_edit(status_msg, "📦 **Zipping playlist...**")
            playlist_name = (meta or {}).get("title", "playlist") if meta else "playlist"
            zip_path = await zip_folder(out_dir, f"/tmp/serena_dl/{user_id}", playlist_name)
            zip_size = os.path.getsize(zip_path)
            if tracker: await _safe_edit(status_msg, f"📤 **Uploading ZIP ({fmt_size(zip_size)})...**")
            await _flood_send(
                client.send_document(
                    chat_id=message.chat.id,
                    document=zip_path,
                    caption=f"📦 **{playlist_name}**\n`{len(file_path)} files` · `{fmt_size(zip_size)}`",
                    reply_to_message_id=message.id,
                )
            )
            await db.log_download(user_id, url, title=playlist_name, file_size=zip_size, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(zip_path, out_dir)
        else:
            await _upload_single(client, message, file_path, meta, url, user_id, tracker, status_msg)

        if status_msg:
            try: await status_msg.delete()
            except: pass

        return True

    except Exception as e:
        if tracker:
            await tracker.failed(str(e))
        else:
            if status_msg:
                await _safe_edit(status_msg, f"❌ **Error:**\n`{str(e)[:300]}`")
        await db.log_download(user_id, url, status="failed")
        return False
    finally:
        cleanup_files(out_dir)


async def _upload_single(
    client, message, fp, meta, url, user_id, tracker, status_msg
):
    if not os.path.exists(fp):
        raise RuntimeError("Downloaded file not found")

    file_size = os.path.getsize(fp)
    ext = _ext(fp)
    orig_name = os.path.basename(fp)

    # Build caption with metadata
    caption = _build_caption(orig_name, meta, file_size)

    # ── Video pipeline ──
    if ext in VIDEO_EXTS:
        # Remux to streamable MP4 with faststart
        if tracker: await _safe_edit(status_msg, "🔄 **Optimizing for Telegram...**")
        fp = await remux_to_mp4(fp)
        ext = _ext(fp)

        # Thumbnail: prefer original, then generate avoiding black frames
        thumb = find_thumbnail(fp)
        if not thumb:
            if tracker: await _safe_edit(status_msg, "🖼️ **Generating thumbnail...**")
            thumb = await generate_thumbnail(fp)

        w, h, dur = get_video_dimensions(fp)
        file_size = os.path.getsize(fp)
        if tracker: await _safe_edit(status_msg, f"📤 **Uploading video ({fmt_size(file_size)})...**")

        await _flood_send(
            client.send_video(
                chat_id=message.chat.id,
                video=fp,
                thumb=thumb,
                caption=caption,
                supports_streaming=True,
                width=w or None,
                height=h or None,
                duration=dur or None,
                reply_to_message_id=message.id,
            )
        )
        if thumb: cleanup_files(thumb)

    # ── Audio pipeline ──
    elif ext in AUDIO_EXTS:
        title = (meta or {}).get("title", orig_name) if meta else orig_name
        artist = (meta or {}).get("uploader", "") if meta else ""
        thumb = find_thumbnail(fp)
        if tracker: await _safe_edit(status_msg, f"📤 **Uploading audio ({fmt_size(file_size)})...**")
        await _flood_send(
            client.send_audio(
                chat_id=message.chat.id,
                audio=fp,
                thumb=thumb,
                caption=caption,
                title=title[:60] if title else None,
                performer=artist[:40] if artist else None,
                reply_to_message_id=message.id,
            )
        )
        if thumb: cleanup_files(thumb)

    # ── Image pipeline ──
    elif ext in IMAGE_EXTS:
        if tracker: await _safe_edit(status_msg, f"📤 **Uploading image...**")
        await _flood_send(
            client.send_photo(
                chat_id=message.chat.id,
                photo=fp,
                caption=caption,
                reply_to_message_id=message.id,
            )
        )

    # ── Document pipeline ──
    else:
        if tracker: await _safe_edit(status_msg, f"📤 **Uploading file ({fmt_size(file_size)})...**")
        await _flood_send(
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


def _build_caption(filename: str, meta: dict, file_size: int) -> str:
    """Build rich caption with metadata."""
    from utils.helpers import fmt_size, fmt_duration, BULLET
    if not meta:
        return f"📁 **{filename}**\n{BULLET} Size: `{fmt_size(file_size)}`"

    title     = meta.get("title", filename)[:60]
    uploader  = meta.get("uploader") or meta.get("channel") or ""
    duration  = meta.get("duration", 0)
    view_count= meta.get("view_count", 0)
    ext       = meta.get("ext", "")
    webpage   = meta.get("webpage_url", "")

    lines = [f"🎬 **{title}**"]
    if uploader:
        lines.append(f"{BULLET} Channel: `{uploader[:40]}`")
    if duration:
        lines.append(f"{BULLET} Duration: `{fmt_duration(int(duration))}`")
    if view_count:
        lines.append(f"{BULLET} Views: `{view_count:,}`")
    lines.append(f"{BULLET} Size: `{fmt_size(file_size)}`")
    if ext:
        lines.append(f"{BULLET} Format: `{ext}`")
    if webpage:
        lines.append(f"{BULLET} [Source]({webpage})")

    return "\n".join(lines)
