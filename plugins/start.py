"""
Serena Downloader Bot - Start & User Commands
"""
import os, sys, time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import BULLET, DIVIDER, HEADER, FOOTER, fmt_size, fmt_duration
from config import (
    BOT_NAME, BOT_USERNAME, SUPPORT_USERNAME, OWNER_USERNAME,
    PLANS, FREE_LIMIT, BASIC_LIMIT, PREMIUM_LIMIT, FORCE_SUB_CHANNEL
)
from queue_manager import queue_manager
import config as _cfg

BOT_START_TIME = time.time()


def _main_kb(support_url: str, channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Plans", callback_data="plans"),
         InlineKeyboardButton("❓ Help",  callback_data="help")],
        [InlineKeyboardButton("📊 My Stats",   callback_data="mystats"),
         InlineKeyboardButton("📜 History",    callback_data="history_cb")],
        [InlineKeyboardButton("🍪 Cookies",    callback_data="cookie_status"),
         InlineKeyboardButton("⚙️ Settings",   callback_data="settings_cb")],
        [InlineKeyboardButton("💬 Support",    url=support_url),
         InlineKeyboardButton("📢 Channel",    url=channel_url)],
        [InlineKeyboardButton("👤 Owner",      url=f"https://t.me/{OWNER_USERNAME}")],
    ])


async def _check_force_sub(client: Client, user_id: int) -> bool:
    """Return True if user is subscribed or force sub not set."""
    if not FORCE_SUB_CHANNEL:
        return True
    try:
        member = await client.get_chat_member(f"@{FORCE_SUB_CHANNEL}", user_id)
        return member.status.value not in ("kicked", "left")
    except Exception:
        return True  # if can't check, allow


@Client.on_message(filters.command("start") & ~filters.outgoing)
@ensure_registered
@not_banned
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    name = user.first_name or "User"

    # Force sub check
    if not await _check_force_sub(client, user.id):
        await message.reply_text(
            f"{HEADER}\n**Join Required!** 🔔\n{DIVIDER}\n\n"
            f"Please join our channel to use this bot.\n",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")],
                [InlineKeyboardButton("✅ I Joined", callback_data="check_sub")],
            ])
        )
        return

    support_url = f"https://t.me/{SUPPORT_USERNAME}"
    channel_url = f"https://t.me/{FORCE_SUB_CHANNEL}" if FORCE_SUB_CHANNEL else support_url

    locked = getattr(_cfg, "BOT_LOCK", False)
    lock_notice = "\n⚠️ **Bot is currently locked by owner.**" if locked else ""

    await message.reply_text(
        f"{HEADER}\n**Welcome to {BOT_NAME}!** 🎉\n{DIVIDER}\n\n"
        f"Hello **{name}**! I can download from:\n\n"
        f"{BULLET} YouTube, Instagram, TikTok\n"
        f"{BULLET} Twitter/X, Facebook, Terabox\n"
        f"{BULLET} Google Drive, M3U8 Streams\n"
        f"{BULLET} Direct Links (Video/Audio/Image/Doc)\n\n"
        f"Just send any URL! ✨{lock_notice}\n\n"
        f"{DIVIDER}\n{FOOTER}",
        reply_markup=_main_kb(support_url, channel_url)
    )


@Client.on_callback_query(filters.regex("^check_sub$"))
async def cb_check_sub(client: Client, query: CallbackQuery):
    await query.answer()
    if await _check_force_sub(client, query.from_user.id):
        name = query.from_user.first_name or "User"
        support_url = f"https://t.me/{SUPPORT_USERNAME}"
        channel_url = f"https://t.me/{FORCE_SUB_CHANNEL}" if FORCE_SUB_CHANNEL else support_url
        await query.message.edit_text(
            f"{HEADER}\n**Welcome, {name}!** 🎉\n{DIVIDER}\n\n"
            f"✅ Subscription verified! Send me any URL!\n\n{FOOTER}",
            reply_markup=_main_kb(support_url, channel_url)
        )
    else:
        await query.answer("❌ You haven't joined yet!", show_alert=True)


@Client.on_message(filters.command("help") & ~filters.outgoing)
@ensure_registered
@not_banned
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n**Help Guide** 📖\n{DIVIDER}\n\n"
        f"**User Commands:**\n"
        f"`/start` — Home menu\n"
        f"`/help` — This guide\n"
        f"`/ping` — Latency & uptime\n"
        f"`/status` — Bot status\n"
        f"`/plans` — Subscription plans\n"
        f"`/mystats` — Your stats\n"
        f"`/history` — Recent downloads\n"
        f"`/audio [url]` — Audio only\n"
        f"`/info [url]` — Media info\n"
        f"`/formats [url]` — List formats\n"
        f"`/speedtest` — Speed test\n"
        f"`/cookies` — Cookie status\n"
        f"`/queue` — Queue status\n"
        f"`/cancel` — Cancel selection\n"
        f"`/feedback [text]` — Send feedback\n\n"
        f"**Quality Options:**\n"
        f"`144p | 360p | 720p | 1080p | Audio | Best`\n\n"
        f"**Bulk:** Send a `.txt` file with URLs!\n\n"
        f"{DIVIDER}\n"
        f"{BULLET} Support: @{SUPPORT_USERNAME}\n"
        f"{BULLET} Owner: @{OWNER_USERNAME}\n{FOOTER}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
             InlineKeyboardButton("👤 Owner",   url=f"https://t.me/{OWNER_USERNAME}")],
        ])
    )


@Client.on_message(filters.command("ping") & ~filters.outgoing)
async def ping_cmd(client: Client, message: Message):
    import shutil
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    latency = (time.time() - start) * 1000

    uptime_sec = int(time.time() - BOT_START_TIME)
    d, r = divmod(uptime_sec, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    uptime_str = f"{d}d {h}h {m}m {s}s" if d else f"{h}h {m}m {s}s" if h else f"{m}m {s}s"

    # Disk usage
    total, used, free = shutil.disk_usage("/tmp")

    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    await msg.edit_text(
        f"{HEADER}\n**Bot Info** 🏓\n{DIVIDER}\n\n"
        f"{BULLET} Status: `🟢 Online`\n"
        f"{BULLET} Latency: `{latency:.2f}ms`\n"
        f"{BULLET} Uptime: `{uptime_str}`\n"
        f"{BULLET} Date/Time: `{now}`\n"
        f"{BULLET} Active DLs: `{queue_manager.active_count()}`\n"
        f"{BULLET} Queue: `{queue_manager.queue_size()}`\n"
        f"{BULLET} /tmp Free: `{fmt_size(free)}`\n"
        f"{BULLET} /tmp Used: `{fmt_size(used)}`\n"
        f"{BULLET} Lock: `{'🔒 Locked' if getattr(_cfg,'BOT_LOCK',False) else '🔓 Open'}`\n\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("status") & ~filters.outgoing)
@ensure_registered
async def status_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    await message.reply_text(
        f"{HEADER}\n**Bot Status** ⚡\n{DIVIDER}\n\n"
        f"{BULLET} Status: `🟢 Online`\n"
        f"{BULLET} Total Users: `{stats['total_users']}`\n"
        f"{BULLET} Total Downloads: `{stats['total_downloads']}`\n"
        f"{BULLET} Successful: `{stats['successful_downloads']}`\n"
        f"{BULLET} Active: `{queue_manager.active_count()}`\n"
        f"{BULLET} Queued: `{queue_manager.queue_size()}`\n\n{FOOTER}"
    )


@Client.on_message(filters.command("plans") & ~filters.outgoing)
@ensure_registered
@not_banned
async def plans_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n**Subscription Plans** 💎\n{DIVIDER}\n\n"
        f"**Free 🆓**\n{BULLET} `{FREE_LIMIT}` downloads/day\n\n"
        f"**Basic 🥉**\n{BULLET} `{BASIC_LIMIT}` downloads/day · 30 days\n\n"
        f"**Premium 💎**\n{BULLET} `{PREMIUM_LIMIT}` downloads/day · 365 days\n{BULLET} All qualities\n\n"
        f"**Owner 👑**\n{BULLET} Unlimited · Lifetime\n\n"
        f"{DIVIDER}\n{BULLET} Contact @{SUPPORT_USERNAME} to upgrade!\n{FOOTER}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Upgrade", url=f"https://t.me/{SUPPORT_USERNAME}")
        ]])
    )


@Client.on_message(filters.command("mystats") & ~filters.outgoing)
@ensure_registered
@not_banned
async def mystats_cmd(client: Client, message: Message):
    uid = message.from_user.id
    await db.check_and_reset_daily(uid)
    await db.check_plan_expiry(uid)
    user = await db.get_user(uid)
    if not user:
        await message.reply_text("❌ Not found. Try /start first.")
        return
    plan = user.get("plan","free")
    pi = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count", 0)
    rem = "Unlimited" if pi["limit"] >= 999999 else str(max(0, pi["limit"] - used))
    history = await db.get_user_history(uid, limit=9999)
    success = sum(1 for h in history if h.get("status") == "done")
    await message.reply_text(
        f"{HEADER}\n**Your Stats** 📊\n{DIVIDER}\n\n"
        f"{BULLET} Plan: `{pi['name']}`\n"
        f"{BULLET} Used Today: `{used}`\n"
        f"{BULLET} Remaining: `{rem}`\n"
        f"{BULLET} Total Downloads: `{len(history)}`\n"
        f"{BULLET} Successful: `{success}`\n"
        f"{BULLET} Expiry: `{user.get('plan_expiry') or 'N/A'}`\n"
        f"{BULLET} Joined: `{user.get('joined_at','N/A')[:10]}`\n\n{FOOTER}"
    )


@Client.on_message(filters.command("history") & ~filters.outgoing)
@ensure_registered
@not_banned
async def history_cmd(client: Client, message: Message):
    history = await db.get_user_history(message.from_user.id, limit=10)
    if not history:
        await message.reply_text("📭 No download history yet.")
        return
    lines = [f"{HEADER}\n**Recent Downloads** 📜\n{DIVIDER}\n"]
    for i, dl in enumerate(history, 1):
        title = (dl.get("title") or dl.get("url",""))[:38]
        icon = "✅" if dl.get("status") == "done" else "❌"
        date = (dl.get("created_at") or "")[:10]
        lines.append(f"`{i}.` {icon} `{title}`\n    `{date}`")
    lines.append(f"\n{FOOTER}")
    await message.reply_text("\n\n".join(lines))


@Client.on_message(filters.command("settings") & ~filters.outgoing)
@ensure_registered
async def settings_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n**Settings** ⚙️\n{DIVIDER}\n\n"
        f"{BULLET} Default Quality: `Best Available`\n"
        f"{BULLET} Auto Thumbnail: `Enabled (smart seek)`\n"
        f"{BULLET} Original Thumbnail: `Enabled`\n"
        f"{BULLET} FFmpeg Faststart: `Enabled`\n"
        f"{BULLET} Metadata Caption: `Enabled`\n"
        f"{BULLET} Playlist ZIP: `Enabled`\n"
        f"{BULLET} Progress Interval: `3.5s`\n"
        f"{BULLET} Flood Protection: `Enabled`\n"
        f"{BULLET} Force Sub: `{'@'+FORCE_SUB_CHANNEL if FORCE_SUB_CHANNEL else 'Disabled'}`\n\n{FOOTER}"
    )


@Client.on_message(filters.command("queue") & ~filters.outgoing)
async def queue_cmd(client: Client, message: Message):
    await message.reply_text(
        f"📋 **Queue Status**\n\n"
        f"{BULLET} Active: `{queue_manager.active_count()}`\n"
        f"{BULLET} Waiting: `{queue_manager.queue_size()}`"
    )


@Client.on_message(filters.command("feedback") & ~filters.outgoing)
@ensure_registered
@not_banned
async def feedback_cmd(client: Client, message: Message):
    text = " ".join(message.command[1:]).strip()
    if not text:
        await message.reply_text("💬 Usage: `/feedback Your message here`")
        return
    await db.save_feedback(message.from_user.id, text)
    await message.reply_text(
        f"✅ **Feedback received!** 💎\n{BULLET} Support: @{SUPPORT_USERNAME}"
    )


@Client.on_message(filters.command("cookies") & ~filters.outgoing)
@ensure_registered
async def cookies_cmd(client: Client, message: Message):
    msg = await message.reply_text("🍪 **Checking YouTube cookie status...**")
    from downloader.core import check_yt_cookies_status
    result = await check_yt_cookies_status()
    icon = "✅" if result["valid"] else ("⚠️" if result["expired"] else "❌")
    await msg.edit_text(
        f"{HEADER}\n**Cookie Status** 🍪\n{DIVIDER}\n\n"
        f"{icon} {result['message']}\n\n"
        f"**How to set cookies on Render:**\n"
        f"`1.` Install **Get cookies.txt LOCALLY** browser extension\n"
        f"`2.` Open YouTube while logged in\n"
        f"`3.` Click extension → Export as **Netscape format**\n"
        f"`4.` Copy **entire file content**\n"
        f"`5.` Render Dashboard → Service → Environment\n"
        f"`6.` Set `YT_COOKIES` = paste content\n"
        f"⚠️ In Render, multi-line values auto-handled ✅\n\n{FOOTER}"
    )


@Client.on_message(filters.command("speedtest") & ~filters.outgoing)
@ensure_registered
@not_banned
async def speedtest_cmd(client: Client, message: Message):
    import aiohttp
    msg = await message.reply_text("⚡ **Testing download speed...**")
    try:
        start = time.time()
        done = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://speed.cloudflare.com/__down?bytes=5000000",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                async for chunk in resp.content.iter_chunked(65536):
                    done += len(chunk)
        elapsed = time.time() - start
        speed_mb = done / elapsed / 1_000_000
        await msg.edit_text(
            f"{HEADER}\n**Speed Test** ⚡\n{DIVIDER}\n\n"
            f"{BULLET} File: `{fmt_size(done)}`\n"
            f"{BULLET} Time: `{elapsed:.2f}s`\n"
            f"{BULLET} Speed: `{speed_mb:.2f} MB/s` · `{speed_mb*8:.1f} Mbps`\n\n{FOOTER}"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Speed test failed: `{e}`")


@Client.on_message(filters.command("formats") & ~filters.outgoing)
@ensure_registered
@not_banned
async def formats_cmd(client: Client, message: Message):
    import asyncio, yt_dlp
    url = " ".join(message.command[1:]).strip()
    if not url:
        await message.reply_text("ℹ️ Usage: `/formats [URL]`")
        return
    msg = await message.reply_text("🔍 **Fetching available formats...**")
    try:
        loop = asyncio.get_event_loop()
        def _get():
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info: return []
                seen, result = set(), []
                for f in reversed(info.get("formats",[])):
                    h = f.get("height")
                    ext = f.get("ext","?")
                    note = f.get("format_note","")
                    tbr = f.get("tbr", 0)
                    if h and h not in seen:
                        seen.add(h)
                        result.append(f"`{h}p` · `{ext}` · {note}" + (f" · `{int(tbr)}kbps`" if tbr else ""))
                return result[:15]
        fmts = await loop.run_in_executor(None, _get)
        if not fmts:
            await msg.edit_text("❌ No formats found.")
            return
        lines = "\n".join(f"{BULLET} {f}" for f in fmts)
        await msg.edit_text(f"{HEADER}\n**Available Formats** 📋\n{DIVIDER}\n\n{lines}\n\n{FOOTER}")
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`")


# ── Callbacks ──

@Client.on_callback_query(filters.regex("^cookie_status$"))
async def cb_cookie_status(client: Client, query: CallbackQuery):
    await query.answer("Checking...")
    from downloader.core import check_yt_cookies_status
    result = await check_yt_cookies_status()
    icon = "✅" if result["valid"] else ("⚠️" if result["expired"] else "❌")
    await query.message.edit_text(
        f"**Cookie Status** 🍪\n\n{icon} {result['message']}\n\nUse `/cookies` for full details.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^settings_cb$"))
async def cb_settings(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"**Settings** ⚙️\n\n"
        f"{BULLET} Thumbnail: `Smart (no black frames)`\n"
        f"{BULLET} Metadata: `Enabled`\n"
        f"{BULLET} Faststart: `Enabled`\n"
        f"{BULLET} Playlist ZIP: `Enabled`\n"
        f"{BULLET} Force Sub: `{'@'+FORCE_SUB_CHANNEL if FORCE_SUB_CHANNEL else 'Off'}`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^history_cb$"))
async def cb_history(client: Client, query: CallbackQuery):
    await query.answer()
    history = await db.get_user_history(query.from_user.id, limit=5)
    if not history:
        await query.message.edit_text(
            "📭 No downloads yet!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
        )
        return
    lines = ["**Recent Downloads** 📜\n"]
    for i, dl in enumerate(history, 1):
        title = (dl.get("title") or "")[:30]
        icon = "✅" if dl.get("status") == "done" else "❌"
        lines.append(f"`{i}.` {icon} `{title}`")
    await query.message.edit_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^plans$"))
async def cb_plans(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"{HEADER}\n**Plans** 💎\n{DIVIDER}\n\n"
        f"**Free 🆓** — `{FREE_LIMIT}`/day\n"
        f"**Basic 🥉** — `{BASIC_LIMIT}`/day · 30 days\n"
        f"**Premium 💎** — `{PREMIUM_LIMIT}`/day · 365 days\n"
        f"**Owner 👑** — Unlimited\n\n"
        f"{BULLET} Contact @{SUPPORT_USERNAME}\n{FOOTER}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Upgrade", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_start")]
        ])
    )


@Client.on_callback_query(filters.regex("^help$"))
async def cb_help(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"Send any URL to download!\n\n`/help` for full commands.\n`/cookies` for cookie status.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^mystats$"))
async def cb_mystats(client: Client, query: CallbackQuery):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    plan = user.get("plan","free") if user else "free"
    pi = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count",0) if user else 0
    rem = "∞" if pi["limit"]>=999999 else str(max(0, pi["limit"]-used))
    await query.message.edit_text(
        f"**Stats** 📊\n\n{BULLET} Plan: `{pi['name']}`\n{BULLET} Used: `{used}`\n{BULLET} Left: `{rem}`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^back_start$"))
async def cb_back_start(client: Client, query: CallbackQuery):
    await query.answer()
    name = query.from_user.first_name or "User"
    support_url = f"https://t.me/{SUPPORT_USERNAME}"
    channel_url = f"https://t.me/{FORCE_SUB_CHANNEL}" if FORCE_SUB_CHANNEL else support_url
    await query.message.edit_text(
        f"{HEADER}\n**{BOT_NAME}** 🎉\n{DIVIDER}\n\nHello **{name}**! Send a URL to download! ✨\n\n{FOOTER}",
        reply_markup=_main_kb(support_url, channel_url)
    )
