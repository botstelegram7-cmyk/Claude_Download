"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Media        ║
╚══════════════════════════════════════════╝
"""

import os
import asyncio
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from downloader.core import (
    download_with_ytdlp, download_m3u8, download_direct,
    generate_thumbnail, remux_video, cleanup_files
)
from utils.helpers import detect_url_type, _fmt_size
from utils.progress import ProgressTracker, YtdlpProgressHook, build_progress_text
import database as db

YTDLP_TYPES = {"youtube", "instagram", "tiktok", "twitter", "facebook", "terabox", "generic"}
DIRECT_TYPES = {"direct_video", "direct_audio", "direct_image", "direct_doc"}

# Flood-safe send helper
async def _safe_send(coro, retries: int = 3):
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
    out_dir = f"/tmp/serena_dl/{user_id}"
    os.makedirs(out_dir, exist_ok=True)

    # Determine title for progress display
    short_url = url.split("/")[-1][:30] or "media"

    tracker = ProgressTracker(
        message=status_msg,
        title=short_url,
        action="Downloading",
        interval=3.5
    ) if status_msg else None

    loop = asyncio.get_event_loop()

    try:
        file_path = None

        if url_type == "m3u8":
            if tracker:
                await tracker._safe_edit("📡 **Fetching M3U8 stream...**\n\n`Please wait, this may take a moment.`")
            file_path = await download_m3u8(url, out_dir)

        elif url_type in DIRECT_TYPES:
            async def direct_hook(current: int, total: int):
                if tracker:
                    await tracker.hook(current, total)

            if tracker:
                await tracker._safe_edit("⬇️ **Starting direct download...**")
            file_path = await download_direct(url, out_dir, progress_hook=direct_hook)

        else:
            # Try to get title first
            if tracker:
                await tracker._safe_edit("🔍 **Fetching media info...**")
            try:
                import yt_dlp
                def _get_title():
                    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                        info = ydl.extract_info(url, download=False)
                        return info.get("title", short_url)[:40] if info else short_url
                t = await loop.run_in_executor(None, _get_title)
                if tracker:
                    tracker.title = t
            except Exception:
                pass

            ytdlp_hook = YtdlpProgressHook(tracker, loop) if tracker else None
            file_path = await download_with_ytdlp(
                url, out_dir,
                quality=quality,
                audio_only=audio_only,
                progress_hook=ytdlp_hook,
            )

        if not file_path:
            if tracker:
                await tracker.failed("Media could not be retrieved.")
            await db.log_download(user_id, url, status="failed")
            return False

        file_paths = file_path if isinstance(file_path, list) else [file_path]

        for fp in file_paths:
            if not os.path.exists(fp):
                continue

            file_size = os.path.getsize(fp)
            title = os.path.basename(fp)
            ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""

            # Remux if needed
            if ext in ("webm", "mkv") and not audio_only:
                if tracker:
                    await tracker._safe_edit("🔄 **Remuxing video to MP4...**")
                fp = await remux_video(fp)

            # Thumbnail
            thumb = None
            if ext in ("mp4", "mkv", "webm", "avi", "mov", "ts"):
                thumb = await generate_thumbnail(fp)

            # Upload progress
            size_str = _fmt_size(file_size)
            if tracker:
                await tracker._safe_edit(
                    f"📤 **Uploading to Telegram...**\n\n"
                    f"`{title[:40]}`\n"
                    f"◌ Size: 〘 **{size_str}** 〙"
                )

            await _upload_file(client, message.chat.id, fp, thumb, title, message.id)

            await db.log_download(user_id, url, title=title, file_size=file_size, status="done")
            await db.increment_daily_count(user_id)
            cleanup_files(fp, thumb)

        if tracker:
            try:
                await status_msg.delete()
            except Exception:
                pass

        return True

    except Exception as e:
        if tracker:
            await tracker.failed(str(e))
        await db.log_download(user_id, url, status="failed")
        return False


async def _upload_file(client, chat_id, file_path, thumb, title, reply_to):
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""
    video_exts = {"mp4", "mkv", "webm", "avi", "mov", "flv", "ts"}
    audio_exts = {"mp3", "aac", "flac", "wav", "ogg", "m4a"}
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}

    kwargs = dict(chat_id=chat_id, reply_to_message_id=reply_to)

    for attempt in range(3):
        try:
            if ext in video_exts:
                await client.send_video(**kwargs, video=file_path, thumb=thumb,
                    caption=f"🎬 `{title}`", supports_streaming=True)
            elif ext in audio_exts:
                await client.send_audio(**kwargs, audio=file_path, title=title, thumb=thumb)
            elif ext in image_exts:
                await client.send_photo(**kwargs, photo=file_path, caption=f"🖼️ `{title}`")
            else:
                await client.send_document(**kwargs, document=file_path,
                    caption=f"📁 `{title}`", thumb=thumb)
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(2)
