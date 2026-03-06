"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Download     ║
╚══════════════════════════════════════════╝
"""

import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import is_valid_url, detect_url_type, BULLET, DIVIDER, HEADER, FOOTER
from queue_manager import queue_manager, DownloadJob
from downloader.media import process_download
from config import PLANS, OWNER_IDS


# ─── Pending URL store (user_id -> url) ───
_pending_urls: dict = {}
_pending_audio: dict = {}


async def _guard(message: Message, user_id: int) -> bool:
    """Run ban/limit checks. Return True if OK to proceed."""
    await db.check_and_reset_daily(user_id)
    await db.check_plan_expiry(user_id)
    user = await db.get_user(user_id)
    if not user:
        await message.reply_text("❌ User record not found. Please /start first.")
        return False
    if user.get("is_banned"):
        await message.reply_text("🚫 You are banned. Contact @TechnicalSerena.")
        return False
    if user_id in OWNER_IDS:
        return True
    plan = user.get("plan", "free")
    plan_info = PLANS.get(plan, PLANS["free"])
    limit = plan_info["limit"]
    used = user.get("daily_count", 0)
    if used >= limit:
        await message.reply_text(
            f"⚠️ **Daily limit reached!**\n\n"
            f"{BULLET} Your Plan: `{plan_info['name']}`\n"
            f"{BULLET} Limit: `{limit}` downloads/day\n\n"
            f"Upgrade your plan or try again tomorrow!\n"
            f"{BULLET} Contact @TechnicalSerena"
        )
        return False
    return True


def _quality_keyboard(url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("144p", callback_data=f"q|144p|{url[:100]}"),
            InlineKeyboardButton("360p", callback_data=f"q|360p|{url[:100]}"),
            InlineKeyboardButton("720p", callback_data=f"q|720p|{url[:100]}"),
        ],
        [
            InlineKeyboardButton("1080p", callback_data=f"q|1080p|{url[:100]}"),
            InlineKeyboardButton("🎵 Audio", callback_data=f"q|audio|{url[:100]}"),
            InlineKeyboardButton("✨ Best", callback_data=f"q|best|{url[:100]}"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="q|cancel|")],
    ])


# ─── URL message handler ───
@Client.on_message(
    filters.text & ~filters.outgoing & ~filters.command(
        ["start","help","ping","status","plans","mystats","history",
         "settings","audio","info","queue","cancel","feedback",
         "givepremium","removepremium","ban","unban","broadcast",
         "stats","users","banned","restart"]
    )
)
@ensure_registered
@not_banned
async def handle_url(client: Client, message: Message):
    text = message.text.strip()
    if not is_valid_url(text):
        return  # ignore non-URL text silently

    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return

    _pending_urls[user_id] = text
    url_type = detect_url_type(text)
    type_labels = {
        "youtube": "YouTube 🎬", "instagram": "Instagram 📸",
        "tiktok": "TikTok 🎵", "twitter": "Twitter/X 🐦",
        "facebook": "Facebook 👥", "gdrive": "Google Drive 📁",
        "terabox": "Terabox ☁️", "m3u8": "M3U8 Stream 📡",
        "direct_video": "Direct Video 🎬", "direct_audio": "Direct Audio 🎵",
        "direct_image": "Direct Image 🖼️", "direct_doc": "Direct Document 📄",
        "generic": "Media 🌐",
    }
    label = type_labels.get(url_type, "Media 🌐")

    await message.reply_text(
        f"🔍 **{label} detected!**\n\n"
        f"{BULLET} URL: `{text[:60]}...`\n\n"
        f"Select quality:",
        reply_markup=_quality_keyboard(text)
    )


# ─── Quality callback ───
@Client.on_callback_query(filters.regex(r"^q\|"))
async def quality_callback(client: Client, query: CallbackQuery):
    await query.answer()
    parts = query.data.split("|", 2)
    if len(parts) < 3:
        await query.message.delete()
        return

    _, quality, url_short = parts

    if quality == "cancel":
        _pending_urls.pop(query.from_user.id, None)
        await query.message.edit_text("❌ Download cancelled.")
        return

    user_id = query.from_user.id
    url = _pending_urls.pop(user_id, None) or url_short

    if not await _guard(query.message, user_id):
        return

    audio_only = (quality == "audio")

    status_msg = await query.message.edit_text(
        f"⏳ **Adding to queue...**\n\n"
        f"{BULLET} Quality: `{quality}`\n"
        f"{BULLET} URL: `{url[:60]}...`"
    )

    job = DownloadJob(
        user_id=user_id,
        url=url,
        quality=quality,
        audio_only=audio_only,
        msg_id=status_msg.id
    )

    async def handler(j: DownloadJob):
        await process_download(
            client=client,
            message=query.message,
            url=j.url,
            quality=j.quality,
            audio_only=j.audio_only,
            status_msg=status_msg
        )

    pos = await queue_manager.enqueue(job, handler)
    await status_msg.edit_text(
        f"📋 **Added to queue!**\n\n"
        f"{BULLET} Position: `#{pos}`\n"
        f"{BULLET} Quality: `{quality}`"
    )


# ─── /audio command ───
@Client.on_message(filters.command("audio") & ~filters.outgoing)
@ensure_registered
@not_banned
async def audio_cmd(client: Client, message: Message):
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text(
            "🎵 **Audio Extractor**\n\n"
            "Usage: `/audio [URL]`\n\n"
            "Example:\n`/audio https://youtu.be/...`"
        )
        return

    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return

    status_msg = await message.reply_text("🎵 **Extracting audio...**")

    job = DownloadJob(
        user_id=user_id,
        url=url,
        quality="audio",
        audio_only=True,
        msg_id=status_msg.id
    )

    async def handler(j: DownloadJob):
        await process_download(
            client=client,
            message=message,
            url=j.url,
            quality="audio",
            audio_only=True,
            status_msg=status_msg
        )

    pos = await queue_manager.enqueue(job, handler)
    await status_msg.edit_text(f"📋 **Queue position:** `#{pos}`\n🎵 Audio extraction queued!")


# ─── /info command ───
@Client.on_message(filters.command("info") & ~filters.outgoing)
@ensure_registered
@not_banned
async def info_cmd(client: Client, message: Message):
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text("ℹ️ Usage: `/info [URL]`")
        return

    msg = await message.reply_text("🔍 **Fetching media info...**")
    try:
        import yt_dlp
        loop = asyncio.get_event_loop()

        def _extract():
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, _extract)
        if not info:
            await msg.edit_text("❌ Could not fetch media info.")
            return

        title = info.get("title", "Unknown")
        duration = info.get("duration", 0)
        uploader = info.get("uploader", "Unknown")
        view_count = info.get("view_count", 0)
        ext = info.get("ext", "?")

        from utils.helpers import fmt_duration
        dur_str = fmt_duration(int(duration)) if duration else "N/A"
        views_str = f"{view_count:,}" if view_count else "N/A"

        await msg.edit_text(
            f"{HEADER}\n**Media Info** ℹ️\n{DIVIDER}\n\n"
            f"{BULLET} **Title:** `{title[:60]}`\n"
            f"{BULLET} **Duration:** `{dur_str}`\n"
            f"{BULLET} **Uploader:** `{uploader}`\n"
            f"{BULLET} **Views:** `{views_str}`\n"
            f"{BULLET} **Format:** `{ext}`\n\n"
            f"{FOOTER}"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error fetching info: `{str(e)[:200]}`")


# ─── /cancel command ───
@Client.on_message(filters.command("cancel") & ~filters.outgoing)
async def cancel_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    _pending_urls.pop(user_id, None)
    await message.reply_text("❌ **Cancelled.** Any pending URL selection cleared.")


# ─── Document (bulk .txt) handler ───
@Client.on_message(filters.document & ~filters.outgoing)
@ensure_registered
@not_banned
async def handle_document(client: Client, message: Message):
    doc = message.document
    if not doc or not doc.file_name.endswith(".txt"):
        return

    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return

    status_msg = await message.reply_text("📄 **Processing bulk URL file...**")

    try:
        file_path = await client.download_media(message, file_name=f"/tmp/{user_id}_bulk.txt")
        with open(file_path, "r") as f:
            lines = [l.strip() for l in f.readlines() if l.strip() and is_valid_url(l.strip())]
        os.remove(file_path)

        if not lines:
            await status_msg.edit_text("❌ No valid URLs found in the file.")
            return

        await status_msg.edit_text(
            f"📋 **Bulk Download Started!**\n\n"
            f"{BULLET} Found `{len(lines)}` URLs\n"
            f"{BULLET} Processing one by one..."
        )

        for i, url in enumerate(lines, 1):
            job = DownloadJob(
                user_id=user_id,
                url=url,
                quality="best",
                msg_id=message.id + i
            )
            s = await message.reply_text(f"⏳ `[{i}/{len(lines)}]` Queuing...")

            async def make_handler(j, sm):
                async def handler(_j):
                    await process_download(client, message, _j.url, status_msg=sm)
                return handler

            h = await make_handler(job, s)
            await queue_manager.enqueue(job, h)

        await status_msg.edit_text(
            f"✅ **All {len(lines)} URLs queued!**\n"
            f"Downloads will process shortly."
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: `{str(e)[:200]}`")
