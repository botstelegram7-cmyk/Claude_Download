"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Media        ║
╚══════════════════════════════════════════╝
"""

import os
from typing import Optional, List
from pyrogram import Client
from pyrogram.types import Message
from downloader.core import (
    download_with_ytdlp, download_m3u8, download_direct,
    generate_thumbnail, remux_video, cleanup_files
)
from utils.helpers import detect_url_type, fmt_size
import database as db


YTDLP_TYPES = {"youtube", "instagram", "tiktok", "twitter", "facebook", "terabox", "generic"}
DIRECT_TYPES = {"direct_video", "direct_audio", "direct_image", "direct_doc"}


async def process_download(
    client: Client,
    message: Message,
    url: str,
    quality: str = "best",
    audio_only: bool = False,
    status_msg: Optional[Message] = None,
) -> bool:
    """
    Full download pipeline:
    detect → download → thumbnail → upload → log → cleanup
    Returns True on success.
    """
    user_id = message.from_user.id
    url_type = detect_url_type(url)
    out_dir = f"/tmp/serena_dl/{user_id}"
    os.makedirs(out_dir, exist_ok=True)

    downloaded_size = [0]
    total_size = [0]
    last_pct = [-1]

    async def progress_hook(current: int, total: int):
        downloaded_size[0] = current
        total_size[0] = total
        if status_msg and total > 0:
            pct = int(current / total * 100)
            if pct != last_pct[0] and pct % 10 == 0:
                last_pct[0] = pct
                bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                size_str = fmt_size(current)
                total_str = fmt_size(total)
                try:
                    await status_msg.edit_text(
                        f"⬇️ **Downloading...**\n\n"
                        f"`[{bar}]` `{pct}%`\n\n"
                        f"▸ `{size_str}` / `{total_str}`"
                    )
                except Exception:
                    pass

    def ydl_progress_hook(d):
        import asyncio
        if d["status"] == "downloading":
            current = d.get("downloaded_bytes", 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
            if status_msg and total:
                pct = int(current / total * 100)
                if pct != last_pct[0] and pct % 10 == 0:
                    last_pct[0] = pct
                    bar = "█" * (pct // 10) + "░" * (10 - pct // 10)
                    speed = d.get("speed", 0) or 0
                    eta = d.get("eta", 0) or 0
                    speed_str = fmt_size(int(speed)) + "/s" if speed else ""
                    eta_str = f"{eta}s" if eta else ""
                    size_done = fmt_size(current)
                    size_total = fmt_size(total)
                    loop = asyncio.get_event_loop()
                    if not loop.is_closed():
                        asyncio.run_coroutine_threadsafe(
                            status_msg.edit_text(
                                f"⬇️ **Downloading...**\n\n"
                                f"`[{bar}]` `{pct}%`\n\n"
                                f"▸ Size: `{size_done}` / `{size_total}`\n"
                                f"▸ Speed: `{speed_str}`\n"
                                f"▸ ETA: `{eta_str}`"
                            ),
                            loop
                        )

    try:
        file_path = None
        title = "Media"

        if url_type == "m3u8":
            if status_msg:
                await status_msg.edit_text("📡 **Downloading M3U8 stream...**")
            file_path = await download_m3u8(url, out_dir)

        elif url_type in DIRECT_TYPES:
            if status_msg:
                await status_msg.edit_text("⬇️ **Downloading direct file...**")
            file_path = await download_direct(url, out_dir, progress_hook=progress_hook)

        else:
            if status_msg:
                await status_msg.edit_text("🔍 **Fetching media info...**")
            file_path = await download_with_ytdlp(
                url, out_dir,
                quality=quality,
                audio_only=audio_only,
                progress_hook=ydl_progress_hook
            )

        if not file_path:
            if status_msg:
                await status_msg.edit_text("❌ **Download failed.** Media could not be retrieved.")
            await db.log_download(user_id, url, status="failed")
            return False

        # Handle playlist (list of files)
        if isinstance(file_path, list):
            file_paths = file_path
        else:
            file_paths = [file_path]

        for fp in file_paths:
            if not os.path.exists(fp):
                continue

            file_size = os.path.getsize(fp)
            title = os.path.basename(fp)
            ext = fp.rsplit(".", 1)[-1].lower() if "." in fp else ""

            # Remux if needed
            if ext in ("webm", "mkv") and not audio_only:
                if status_msg:
                    await status_msg.edit_text("🔄 **Remuxing video...**")
                fp = await remux_video(fp)

            # Generate thumbnail
            thumb = None
            if ext in ("mp4", "mkv", "webm", "avi", "mov", "ts"):
                thumb = await generate_thumbnail(fp)

            if status_msg:
                await status_msg.edit_text("📤 **Uploading to Telegram...**")

            # Upload
            await _upload_file(client, message.chat.id, fp, thumb, title, message.id)

            # Log
            await db.log_download(user_id, url, title=title, file_size=file_size, status="done")
            await db.increment_daily_count(user_id)

            # Cleanup
            cleanup_files(fp, thumb)

        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass

        return True

    except Exception as e:
        if status_msg:
            try:
                await status_msg.edit_text(f"❌ **Error:** `{str(e)[:200]}`")
            except Exception:
                pass
        await db.log_download(user_id, url, status="failed")
        return False


async def _upload_file(
    client: Client,
    chat_id: int,
    file_path: str,
    thumb: Optional[str],
    title: str,
    reply_to: int = None
):
    """Upload a file to Telegram based on its type."""
    ext = file_path.rsplit(".", 1)[-1].lower() if "." in file_path else ""

    video_exts = {"mp4", "mkv", "webm", "avi", "mov", "flv", "ts"}
    audio_exts = {"mp3", "aac", "flac", "wav", "ogg", "m4a"}
    image_exts = {"jpg", "jpeg", "png", "gif", "webp", "bmp"}

    kwargs = dict(
        chat_id=chat_id,
        reply_to_message_id=reply_to
    )

    if ext in video_exts:
        await client.send_video(
            **kwargs,
            video=file_path,
            thumb=thumb,
            caption=f"🎬 `{title}`",
            supports_streaming=True,
        )
    elif ext in audio_exts:
        await client.send_audio(
            **kwargs,
            audio=file_path,
            title=title,
            thumb=thumb,
        )
    elif ext in image_exts:
        await client.send_photo(
            **kwargs,
            photo=file_path,
            caption=f"🖼️ `{title}`",
        )
    else:
        await client.send_document(
            **kwargs,
            document=file_path,
            caption=f"📁 `{title}`",
            thumb=thumb,
        )
