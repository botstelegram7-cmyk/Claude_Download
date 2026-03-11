"""
Serena Bot - Download Handler
- Dynamic quality selector for YouTube (fetches actual available formats)
- APK/ZIP → no quality prompt, direct download
- Queue: 1st download completes before 2nd starts
- Upload progress shown (fixed coroutine bug)
- Thumbnail from original source
- More format support
"""
import os, sys, asyncio, re

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import is_valid_url, detect_url_type
from queue_manager import queue_manager, DownloadJob
from downloader.media import process_download, handle_gdrive_choice, handle_large_file_choice
from config import PLANS, OWNER_IDS, QUEUE_DELAY
import config as _cfg

B  = "▸"
LN = "─" * 22

_pending_urls: dict = {}

_CMDS = [
    "start","help","ping","status","plans","mystats","history","settings",
    "audio","info","queue","cancel","feedback","cookies","speedtest","formats",
    "givepremium","removepremium","ban","unban","broadcast","stats","users",
    "banned","restart","lock","unlock"
]

# Platforms that support quality selection
_QUALITY_PLATFORMS = {"youtube"}

# APK/archive extensions — skip quality prompt
_ARCHIVE_EXTS = {"zip","rar","tar","7z","apk","exe","dmg","iso","bin","pkg","xapk"}

_PLATFORM_NAMES = {
    "youtube":      "YouTube",
    "instagram":    "Instagram",
    "tiktok":       "TikTok",
    "twitter":      "Twitter/X",
    "facebook":     "Facebook",
    "gdrive":       "Google Drive",
    "terabox":      "Terabox",
    "m3u8":         "Stream",
    "direct_video": "Direct Link",
    "direct_audio": "Direct Link",
    "direct_image": "Direct Link",
    "direct_doc":   "Direct Link",
    "generic":      "Unknown",
}


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
        await message.reply_text("🚫 You are banned.")
        return False
    if user_id in OWNER_IDS:
        return True
    plan  = user.get("plan","free")
    limit = PLANS.get(plan, PLANS["free"])["limit"]
    used  = user.get("daily_count",0)
    if used >= limit:
        pi = PLANS.get(plan, PLANS["free"])
        await message.reply_text(
            f"⚠️ **Daily limit reached!**\n\n"
            f"{B} Plan: `{pi['name']}`\n"
            f"{B} Limit: `{limit}` downloads/day\n\n"
            f"Contact @TechnicalSerena to upgrade 💎"
        )
        return False
    return True


def _default_quality_kb() -> InlineKeyboardMarkup:
    """Fallback fixed quality keyboard."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("144p",     callback_data="dl_q:144p"),
         InlineKeyboardButton("360p",     callback_data="dl_q:360p"),
         InlineKeyboardButton("480p",     callback_data="dl_q:480p")],
        [InlineKeyboardButton("720p HD",  callback_data="dl_q:720p"),
         InlineKeyboardButton("1080p FHD",callback_data="dl_q:1080p"),
         InlineKeyboardButton("1440p 2K", callback_data="dl_q:1440p")],
        [InlineKeyboardButton("4K",       callback_data="dl_q:2160p"),
         InlineKeyboardButton("🎵 Audio", callback_data="dl_q:audio"),
         InlineKeyboardButton("✨ Best",  callback_data="dl_q:best")],
        [InlineKeyboardButton("❌ Cancel", callback_data="dl_q:cancel")],
    ])


async def _fetch_yt_formats(url: str) -> list:
    """
    Fetch available video heights from yt-dlp.
    Returns list of heights like [144, 360, 720, 1080] sorted ascending.
    """
    try:
        import yt_dlp
        loop = asyncio.get_event_loop()
        def _run():
            opts = {"quiet":True,"no_warnings":True,"skip_download":True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return []
                fmts = info.get("formats") or []
                heights = set()
                for f in fmts:
                    h = f.get("height")
                    if h and isinstance(h, int) and h >= 144:
                        heights.add(h)
                return sorted(heights)
        return await asyncio.wait_for(loop.run_in_executor(None, _run), timeout=15)
    except Exception:
        return []


def _dynamic_quality_kb(heights: list) -> InlineKeyboardMarkup:
    """Build quality keyboard from available heights."""
    # Map height → label
    labels = {
        144:"144p", 240:"240p", 360:"360p", 480:"480p",
        720:"720p HD", 1080:"1080p FHD", 1440:"1440p 2K", 2160:"4K",
        4320:"8K"
    }
    buttons = []
    row = []
    for h in heights:
        label = labels.get(h, f"{h}p")
        row.append(InlineKeyboardButton(label, callback_data=f"dl_q:{h}p"))
        if len(row) == 3:
            buttons.append(row); row = []
    if row:
        buttons.append(row)
    # Always add audio + best + cancel
    buttons.append([
        InlineKeyboardButton("🎵 Audio", callback_data="dl_q:audio"),
        InlineKeyboardButton("✨ Best",  callback_data="dl_q:best"),
    ])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="dl_q:cancel")])
    return InlineKeyboardMarkup(buttons)


async def _pin_and_reply(client, message, status_msg):
    try:
        if message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            await client.pin_chat_message(
                message.chat.id, message.id, disable_notification=True
            )
    except Exception:
        pass


async def _start_download(client, orig_msg, url, quality, audio_only, status_msg):
    await asyncio.sleep(QUEUE_DELAY)
    await process_download(
        client=client, message=orig_msg, url=url,
        quality=quality, audio_only=audio_only,
        status_msg=status_msg,
        platform=_PLATFORM_NAMES.get(detect_url_type(url), "Unknown"),
    )


def _is_archive_url(url: str) -> bool:
    """Check if URL points to an archive/binary (no quality choice needed)."""
    path = url.split("?")[0].lower()
    ext  = path.rsplit(".", 1)[-1] if "." in path else ""
    return ext in _ARCHIVE_EXTS


# ── URL handler ───────────────────────────────────────────────────────────

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

    url_type = detect_url_type(text)
    _pending_urls[user_id] = text

    platform_labels = {
        "youtube":      "YouTube 🎬",
        "instagram":    "Instagram 📸",
        "tiktok":       "TikTok 🎵",
        "twitter":      "Twitter/X 🐦",
        "facebook":     "Facebook 👥",
        "gdrive":       "Google Drive 📁",
        "terabox":      "Terabox ☁️",
        "m3u8":         "Stream 📡",
        "direct_video": "Direct Video 🎬",
        "direct_audio": "Direct Audio 🎵",
        "direct_image": "Direct Image 🖼️",
        "direct_doc":   "Direct File 📄",
        "generic":      "Media 🌐",
    }
    label = platform_labels.get(url_type, "Media 🌐")
    short = text[:55] + "..." if len(text) > 55 else text

    # Google Drive folder
    if url_type == "gdrive" and "/drive/folders/" in text:
        await message.reply_text(
            f"📁 **{label} detected!**\n\n{B} `{short}`\n\n**How to receive files?**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📦 ZIP Archive",      callback_data="dl_gdrive:zip"),
                 InlineKeyboardButton("📂 Individual Files", callback_data="dl_gdrive:individual")],
                [InlineKeyboardButton("❌ Cancel",           callback_data="dl_gdrive:cancel")],
            ])
        )
        return

    # APK / archive / binary — skip quality, download directly
    if _is_archive_url(text) or url_type == "direct_doc":
        sm = await message.reply_text(f"⏳ **Queuing {label} download...**")
        await _pin_and_reply(client, message, sm)
        job  = DownloadJob(user_id=user_id, url=text, quality="best", msg_id=sm.id)
        _sm  = sm; _msg = message; _url = text

        async def handler(j):
            await _start_download(client, _msg, j.url, "best", False, _sm)

        pos = await queue_manager.enqueue(job, handler)
        try:
            await sm.edit_text(
                f"📋 **Queued!**\n\n"
                f"{B} File: `{label}`\n"
                f"{B} Position: `#{pos}`\n"
                f"{B} URL: `{_url[:50]}`"
            )
        except Exception: pass
        return

    # YouTube — fetch actual available formats, then show quality selector
    if url_type in _QUALITY_PLATFORMS:
        sm = await message.reply_text(
            f"🔍 **{label} detected!**\n\n{B} `{short}`\n\n⏳ **Fetching available qualities...**"
        )
        heights = await _fetch_yt_formats(text)
        if heights:
            kb = _dynamic_quality_kb(heights)
            qual_text = " · ".join(
                {144:"144p",240:"240p",360:"360p",480:"480p",
                 720:"720p",1080:"1080p",1440:"1440p",2160:"4K",4320:"8K"}.get(h, f"{h}p")
                for h in heights
            )
            try:
                await sm.edit_text(
                    f"🔍 **{label} detected!**\n\n"
                    f"{B} `{short}`\n\n"
                    f"✅ **Available:** `{qual_text}`\n\n"
                    f"⚡ **Choose quality:**",
                    reply_markup=kb
                )
            except Exception:
                await sm.edit_text(
                    f"🔍 **{label} detected!**\n\n{B} `{short}`\n\n⚡ **Choose quality:**",
                    reply_markup=_default_quality_kb()
                )
        else:
            # Fallback to default keyboard
            try:
                await sm.edit_text(
                    f"🔍 **{label} detected!**\n\n{B} `{short}`\n\n⚡ **Choose quality:**",
                    reply_markup=_default_quality_kb()
                )
            except Exception: pass
        return

    # All other platforms — best quality, queue immediately
    sm = await message.reply_text(f"⏳ **Queuing {label} download...**")
    await _pin_and_reply(client, message, sm)

    job  = DownloadJob(user_id=user_id, url=text, quality="best", msg_id=sm.id)
    _sm  = sm; _msg = message; _url = text

    async def handler(j):
        await _start_download(client, _msg, j.url, "best", False, _sm)

    pos = await queue_manager.enqueue(job, handler)
    try:
        await sm.edit_text(
            f"📋 **Queued!**\n\n"
            f"{B} Platform: `{label}`\n"
            f"{B} Position: `#{pos}`\n"
            f"{B} URL: `{_url[:50]}`"
        )
    except Exception: pass


# ── Quality callback ──────────────────────────────────────────────────────

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
        sm = await query.message.edit_text(
            f"⏳ **Queuing...**\n{B} Quality: `{quality}`"
        )
    except Exception:
        sm = await query.message.reply_text("⏳ Queuing...")

    await _pin_and_reply(client, query.message, sm)

    job  = DownloadJob(user_id=user_id, url=url, quality=quality,
                      audio_only=audio_only, msg_id=sm.id)
    _sm  = sm; _msg = query.message; _url = url; _q = quality; _ao = audio_only

    async def handler(j):
        await _start_download(client, _msg, j.url, _q, _ao, _sm)

    pos = await queue_manager.enqueue(job, handler)
    try:
        await sm.edit_text(
            f"📋 **Added to queue!**\n\n"
            f"{B} Position: `#{pos}`\n"
            f"{B} Quality: `{quality}`\n"
            f"{B} URL: `{url[:50]}`"
        )
    except Exception: pass


# ── Google Drive callbacks ─────────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^dl_gdrive:"))
async def gdrive_choice_cb(client: Client, query: CallbackQuery):
    await query.answer()
    choice  = query.data.split(":",1)[1]
    user_id = query.from_user.id

    if choice == "cancel":
        _pending_urls.pop(user_id, None)
        try: await query.message.edit_text("❌ Cancelled.")
        except: pass
        return

    url = _pending_urls.pop(user_id, None)
    if not url:
        try: await query.message.edit_text("⚠️ Session expired.")
        except: pass
        return

    if not await _guard(query.message, user_id):
        return

    try:
        sm = await query.message.edit_text(
            f"⏳ **Queuing Drive download...**\n{B} Mode: `{choice}`"
        )
    except Exception:
        sm = await query.message.reply_text("⏳ Queuing...")

    _sm  = sm; _msg = query.message; _url = url
    job  = DownloadJob(user_id=user_id, url=_url, quality="best", msg_id=sm.id)

    async def handler(j):
        await asyncio.sleep(QUEUE_DELAY)
        await process_download(client=client, message=_msg, url=j.url,
                               quality="best", status_msg=_sm,
                               platform="Google Drive")

    pos = await queue_manager.enqueue(job, handler)
    try:
        await sm.edit_text(
            f"📋 **Queued!**\n\n"
            f"{B} Position: `#{pos}`\n"
            f"{B} Mode: `{'ZIP Archive' if choice == 'zip' else 'Individual Files'}`"
        )
    except Exception: pass


@Client.on_callback_query(filters.regex(r"^gdrive_(zip|individual)$"))
async def gdrive_receive_cb(client: Client, query: CallbackQuery):
    choice = "zip" if "zip" in query.data else "individual"
    await handle_gdrive_choice(client, query, choice)


# ── /audio ────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("audio") & ~filters.outgoing)
@ensure_registered
@not_banned
async def audio_cmd(client: Client, message: Message):
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text(
            f"🎵 **Usage:** `/audio [URL]`\n\n"
            f"**Example:** `/audio https://youtu.be/abc123`\n\n"
            f"Extracts audio as MP3 from any supported platform."
        )
        return
    user_id = message.from_user.id
    if not await _guard(message, user_id):
        return
    sm  = await message.reply_text("🎵 **Queuing audio extraction...**")
    job = DownloadJob(user_id=user_id, url=url, quality="audio", audio_only=True, msg_id=sm.id)
    _sm = sm

    async def handler(j):
        await asyncio.sleep(QUEUE_DELAY)
        await process_download(client, message, j.url, quality="audio",
                               audio_only=True, status_msg=_sm,
                               platform=_PLATFORM_NAMES.get(detect_url_type(j.url),"Unknown"))

    pos = await queue_manager.enqueue(job, handler)
    try: await sm.edit_text(f"📋 Queue `#{pos}` — 🎵 Audio extraction queued!")
    except: pass


# ── /info ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("info") & ~filters.outgoing)
@ensure_registered
@not_banned
async def info_cmd(client: Client, message: Message):
    import yt_dlp
    url = " ".join(message.command[1:]).strip()
    if not url or not is_valid_url(url):
        await message.reply_text(
            f"ℹ️ **Usage:** `/info [URL]`\n\n"
            f"**Example:** `/info https://youtu.be/abc123`\n\n"
            f"Shows title, duration, views before downloading."
        )
        return
    msg = await message.reply_text("🔍 Fetching info...")
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
            f"**✦ Media Info ✦**\n`{LN}`\n\n"
            f"{B} **Title:** `{title}`\n"
            f"{B} **Duration:** `{fmt_duration(int(duration)) if duration else 'N/A'}`\n"
            f"{B} **Uploader:** `{uploader}`\n"
            f"{B} **Views:** `{views:,}`\n"
            f"{B} **Likes:** `{likes:,}`\n"
            f"{B} **Format:** `{ext}`\n\n`{LN}`",
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
    url     = query.data.split(":",1)[1]
    user_id = query.from_user.id
    if not await _guard(query.message, user_id):
        return
    _pending_urls[user_id] = url
    url_type = detect_url_type(url)
    if url_type in _QUALITY_PLATFORMS and not _is_archive_url(url):
        sm = await query.message.edit_text("⏳ **Fetching available qualities...**")
        heights = await _fetch_yt_formats(url)
        kb = _dynamic_quality_kb(heights) if heights else _default_quality_kb()
        try:
            await sm.edit_text("⚡ **Choose quality:**", reply_markup=kb)
        except Exception: pass
    else:
        sm = await query.message.edit_text("⏳ Queuing...")
        job = DownloadJob(user_id=user_id, url=url, quality="best", msg_id=sm.id)
        _sm = sm; _msg = query.message

        async def handler(j):
            await _start_download(client, _msg, j.url, "best", False, _sm)

        pos = await queue_manager.enqueue(job, handler)
        try: await sm.edit_text(f"📋 Queue `#{pos}` — Downloading...")
        except: pass


# ── /cancel ───────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cancel") & ~filters.outgoing)
async def cancel_cmd(client: Client, message: Message):
    _pending_urls.pop(message.from_user.id, None)
    await message.reply_text("❌ **Cancelled.**")


# ── Large file choice callback ─────────────────────────────────────────────

@Client.on_callback_query(filters.regex(r"^lf:"))
async def large_file_cb(client: Client, query: CallbackQuery):
    await query.answer()
    choice = query.data.split(":",1)[1]
    await handle_large_file_choice(client, query, choice)


# ── Bulk .txt ─────────────────────────────────────────────────────────────

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
    sm = await message.reply_text("📄 Processing URL file...")
    try:
        path = await client.download_media(message, file_name=f"/tmp/{user_id}_bulk.txt")
        with open(path) as f:
            lines = [l.strip() for l in f
                     if l.strip() and not l.startswith("#") and is_valid_url(l.strip())]
        os.remove(path)
        if not lines:
            await sm.edit_text("❌ No valid URLs found in file.")
            return
        await sm.edit_text(f"📋 **{len(lines)} URLs found!** Queueing...")
        for i, url in enumerate(lines, 1):
            s = await message.reply_text(f"⏳ `[{i}/{len(lines)}]` Queuing `{url[:40]}`...")
            job = DownloadJob(user_id=user_id, url=url, quality="best", msg_id=s.id)
            _s = s; _u = url

            async def make_h(_s=_s, _u=_u):
                async def h(j):
                    await asyncio.sleep(QUEUE_DELAY)
                    await process_download(client, message, j.url, status_msg=_s,
                                           platform=_PLATFORM_NAMES.get(detect_url_type(j.url),"Unknown"))
                return h

            await queue_manager.enqueue(job, await make_h())
            await asyncio.sleep(0.3)
        await sm.edit_text(f"✅ **All {len(lines)} URLs queued!**")
    except Exception as e:
        try: await sm.edit_text(f"❌ Error: `{str(e)[:200]}`")
        except: pass
