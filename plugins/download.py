"""
Serena Downloader Bot - Download Handler
"""
import os, sys, asyncio

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import is_valid_url, detect_url_type, BULLET
from queue_manager import queue_manager, DownloadJob
from downloader.media import process_download, handle_gdrive_choice
from config import PLANS, OWNER_IDS
import config as _cfg

_pending_urls: dict = {}

_CMDS = [
    "start","help","ping","status","plans","mystats","history","settings",
    "audio","info","queue","cancel","feedback","cookies","speedtest","formats",
    "givepremium","removepremium","ban","unban","broadcast","stats","users",
    "banned","restart","lock","unlock"
]


async def _guard(message: Message, user_id: int) -> bool:
    if getattr(_cfg, "BOT_LOCK", False) and user_id not in OWNER_IDS:
        await message.reply_text("🔒 **Bot is currently locked.** Try again later.")
        return False
    await db.check_and_reset_daily(user_id)
    await db.check_plan_expiry(user_id)
    user = await db.get_user(user_id)
    if not user:
        await message.reply_text("❌ Please /start first.")
        return False
    if user.get("is_banned"):
        await message.reply_text("🚫 You are banned. Contact @TechnicalSerena.")
        return False
    if user_id in OWNER_IDS:
        return True
    plan = user.get("plan","free")
    limit = PLANS.get(plan, PLANS["free"])["limit"]
    if user.get("daily_count", 0) >= limit:
        await message.reply_text(
            f"⚠️ **Daily limit reached!**\n\n"
            f"{BULLET} Limit: `{limit}` downloads/day\n"
            f"{BULLET} Upgrade: @TechnicalSerena"
        )
        return False
    return True


def _quality_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("144p",     callback_data="dl_q:144p"),
         InlineKeyboardButton("360p",     callback_data="dl_q:360p"),
         InlineKeyboardButton("720p",     callback_data="dl_q:720p")],
        [InlineKeyboardButton("1080p",    callback_data="dl_q:1080p"),
         InlineKeyboardButton("🎵 Audio", callback_data="dl_q:audio"),
         InlineKeyboardButton("✨ Best",  callback_data="dl_q:best")],
        [InlineKeyboardButton("❌ Cancel",callback_data="dl_q:cancel")],
    ])


async def _try_pin(client, chat_id, msg_id):
    try:
        from pyrogram.enums import ChatType
        await client.pin_chat_message(chat_id, msg_id, disable_notification=True)
    except Exception:
        pass


@Client.on_message(
    filters.text & ~filters.outgoing & ~filters.command(_CMDS),
    group=1
)
@ensure_registered
@not_banned
async def handle_url(client: Client, message: Message):
    text = (message.text or "").strip()
    if not is_valid_url(text):
        return
    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return
    _pending_urls[user_id] = text
    url_type = detect_url_type(text)
    labels = {
        "youtube":"YouTube 🎬","instagram":"Instagram 📸","tiktok":"TikTok 🎵",
        "twitter":"Twitter/X 🐦","facebook":"Facebook 👥","gdrive":"Google Drive 📁",
        "terabox":"Terabox ☁️","m3u8":"M3U8 Stream 📡","direct_video":"Direct Video 🎬",
        "direct_audio":"Direct Audio 🎵","direct_image":"Direct Image 🖼️",
        "direct_doc":"Direct Document 📄","generic":"Media 🌐",
    }
    label = labels.get(url_type, "Media 🌐")
    short = text[:55] + "..." if len(text) > 55 else text

    # Google Drive folder — show ZIP/individual choice immediately
    if url_type == "gdrive" and "/drive/folders/" in text:
        sm = await message.reply_text(
            f"📁 **{label} detected!**\n\n{BULLET} `{short}`\n\n"
            f"**How to receive files?**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 ZIP Archive",      callback_data="dl_gdrive:zip"),
                 InlineKeyboardButton("📂 Individual Files", callback_data="dl_gdrive:individual")],
                [InlineKeyboardButton("❌ Cancel",           callback_data="dl_gdrive:cancel")],
            ])
        )
        return

    await message.reply_text(
        f"🔍 **{label} detected!**\n\n{BULLET} `{short}`\n\n⚡ Select quality:",
        reply_markup=_quality_kb()
    )


# ── Google Drive folder callback ──
@Client.on_callback_query(filters.regex(r"^dl_gdrive:"))
async def gdrive_choice_cb(client: Client, query: CallbackQuery):
    await query.answer()
    choice = query.data.split(":",1)[1]
    user_id = query.from_user.id

    if choice == "cancel":
        _pending_urls.pop(user_id, None)
        try: await query.message.edit_text("❌ Cancelled.")
        except: pass
        return

    url = _pending_urls.pop(user_id, None)
    if not url:
        try: await query.message.edit_text("⚠️ Session expired. Resend the URL.")
        except: pass
        return

    if not await _guard(query.message, user_id):
        return

    try:
        status_msg = await query.message.edit_text(
            f"⏳ **Queuing Google Drive download...**\n{BULLET} Mode: `{choice}`"
        )
    except Exception:
        status_msg = await query.message.reply_text("⏳ Queuing...")

    _sm = status_msg
    _url = url
    _choice = choice

    job = DownloadJob(user_id=user_id, url=url, quality="best", msg_id=status_msg.id)

    async def handler(j: DownloadJob):
        await process_download(
            client=client, message=query.message,
            url=j.url, quality="best",
            status_msg=_sm
        )

    pos = await queue_manager.enqueue(job, handler)
    try:
        await status_msg.edit_text(
            f"📋 **Queued!**\n\n"
            f"{BULLET} Position: `#{pos}`\n"
            f"{BULLET} Mode: `{'ZIP Archive' if choice == 'zip' else 'Individual Files'}`"
        )
    except Exception:
        pass


# ── Quality callback ──
@Client.on_callback_query(filters.regex(r"^dl_q:"))
async def quality_cb(client: Client, query: CallbackQuery):
    await query.answer()
    quality = query.data.split(":",1)[1]
    user_id = query.from_user.id

    if quality == "cancel":
        _pending_urls.pop(user_id, None)
        try: await query.message.edit_text("❌ Cancelled.")
        except: pass
        return

    url = _pending_urls.pop(user_id, None)
    if not url:
        try: await query.message.edit_text("⚠️ Session expired. Resend the URL.")
        except: pass
        return

    if not await _guard(query.message, user_id):
        return

    audio_only = (quality == "audio")
    try:
        status_msg = await query.message.edit_text(
            f"⏳ **Queuing...**\n{BULLET} Quality: `{quality}`"
        )
    except Exception:
        status_msg = await query.message.reply_text("⏳ Queuing...")

    job = DownloadJob(user_id=user_id, url=url, quality=quality,
                     audio_only=audio_only, msg_id=status_msg.id)
    _sm = status_msg
    _orig = query.message

    async def handler(j: DownloadJob):
        await process_download(
            client=client, message=_orig,
            url=j.url, quality=j.quality,
            audio_only=j.audio_only, status_msg=_sm
        )
        try:
            from pyrogram.enums import ChatType
            if _orig.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
                await _try_pin(client, _orig.chat.id, _orig.id)
        except Exception:
            pass

    pos = await queue_manager.enqueue(job, handler)
    try:
        await status_msg.edit_text(
            f"📋 **Added to queue!**\n\n"
            f"{BULLET} Position: `#{pos}`\n"
            f"{BULLET} Quality: `{quality}`\n"
            f"{BULLET} URL: `{url[:50]}`"
        )
    except Exception:
        pass


# ── Google Drive ZIP/Individual callback (from media.py pending) ──
@Client.on_callback_query(filters.regex(r"^gdrive_(zip|individual)$"))
async def gdrive_receive_cb(client: Client, query: CallbackQuery):
    choice = "zip" if "zip" in query.data else "individual"
    await handle_gdrive_choice(client, query, choice)


@Client.on_message(filters.command("audio") & ~filters.outgoing)
@ensure_registered
@not_banned
async def audio_cmd(client: Client, message: Message):
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text("🎵 Usage: `/audio [URL]`")
        return
    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return
    sm = await message.reply_text("🎵 **Queuing audio extraction...**")
    job = DownloadJob(user_id=user_id, url=url, quality="audio", audio_only=True, msg_id=sm.id)
    _sm = sm
    async def handler(j):
        await process_download(client, message, j.url, quality="audio", audio_only=True, status_msg=_sm)
    pos = await queue_manager.enqueue(job, handler)
    try: await sm.edit_text(f"📋 Queue `#{pos}` — 🎵 Audio queued!")
    except: pass


@Client.on_message(filters.command("info") & ~filters.outgoing)
@ensure_registered
@not_banned
async def info_cmd(client: Client, message: Message):
    import yt_dlp
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text("ℹ️ Usage: `/info [URL]`")
        return
    msg = await message.reply_text("🔍 **Fetching media info...**")
    try:
        loop = asyncio.get_event_loop()
        def _extract():
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                return ydl.extract_info(url, download=False)
        info = await loop.run_in_executor(None, _extract)
        if not info:
            await msg.edit_text("❌ Could not fetch info.")
            return
        from utils.helpers import fmt_duration, fmt_size
        title    = info.get("title","Unknown")[:60]
        duration = info.get("duration",0)
        uploader = info.get("uploader","Unknown")
        views    = info.get("view_count",0)
        likes    = info.get("like_count",0)
        ext      = info.get("ext","?")
        await msg.edit_text(
            f"⋆｡° ✮ °｡⋆\n**Media Info** ℹ️\n»»──── ✦ ────««\n\n"
            f"{BULLET} **Title:** `{title}`\n"
            f"{BULLET} **Duration:** `{fmt_duration(int(duration)) if duration else 'N/A'}`\n"
            f"{BULLET} **Uploader:** `{uploader}`\n"
            f"{BULLET} **Views:** `{views:,}`\n"
            f"{BULLET} **Likes:** `{likes:,}`\n"
            f"{BULLET} **Format:** `{ext}`\n\n⋆ ｡˚ ˚｡ ⋆",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬇️ Download", callback_data=f"info_dl:{url[:80]}")
            ]])
        )
    except Exception as e:
        try: await msg.edit_text(f"❌ Error: `{str(e)[:200]}`")
        except: pass


@Client.on_callback_query(filters.regex(r"^info_dl:"))
async def info_dl_cb(client: Client, query: CallbackQuery):
    await query.answer()
    url = query.data.split(":",1)[1]
    user_id = query.from_user.id
    if not await _guard(query.message, user_id):
        return
    _pending_urls[user_id] = url
    try:
        await query.message.edit_text(
            f"🔍 **URL loaded!**\n\n{BULLET} `{url[:55]}`\n\n⚡ Select quality:",
            reply_markup=_quality_kb()
        )
    except Exception:
        pass


@Client.on_message(filters.command("cancel") & ~filters.outgoing)
async def cancel_cmd(client: Client, message: Message):
    _pending_urls.pop(message.from_user.id, None)
    await message.reply_text("❌ **Cancelled.**")


@Client.on_message(filters.document & ~filters.outgoing, group=1)
@ensure_registered
@not_banned
async def handle_txt(client: Client, message: Message):
    doc = message.document
    if not doc or not (doc.file_name or "").endswith(".txt"):
        return
    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return
    sm = await message.reply_text("📄 **Processing bulk URL file...**")
    try:
        path = await client.download_media(message, file_name=f"/tmp/{user_id}_bulk.txt")
        with open(path) as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#") and is_valid_url(l.strip())]
        os.remove(path)
        if not lines:
            await sm.edit_text("❌ No valid URLs found.")
            return
        await sm.edit_text(f"📋 **{len(lines)} URLs found!** Queueing all...")
        for i, url in enumerate(lines, 1):
            s = await message.reply_text(f"⏳ `[{i}/{len(lines)}]` Queuing...")
            job = DownloadJob(user_id=user_id, url=url, quality="best", msg_id=s.id)
            _s = s
            async def make_h(_s=_s):
                async def h(j):
                    await process_download(client, message, j.url, status_msg=_s)
                return h
            await queue_manager.enqueue(job, await make_h())
            await asyncio.sleep(0.3)
        await sm.edit_text(f"✅ **All {len(lines)} URLs queued!**")
    except Exception as e:
        try: await sm.edit_text(f"❌ Error: `{str(e)[:200]}`")
        except: pass
