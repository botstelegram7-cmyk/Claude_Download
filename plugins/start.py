"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Start        ║
╚══════════════════════════════════════════╝
"""

import os
import sys
import time

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import BULLET, DIVIDER, HEADER, FOOTER, fmt_size
from config import BOT_NAME, SUPPORT_USERNAME, PLANS, FREE_LIMIT, BASIC_LIMIT, PREMIUM_LIMIT
from queue_manager import queue_manager


@Client.on_message(filters.command("start") & ~filters.outgoing)
@ensure_registered
@not_banned
async def start_cmd(client: Client, message: Message):
    name = message.from_user.first_name or "User"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Plans", callback_data="plans"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
         InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🍪 Cookie Status", callback_data="cookie_status")],
    ])
    await message.reply_text(
        f"{HEADER}\n**Welcome to {BOT_NAME}!** 🎉\n{DIVIDER}\n\n"
        f"Hello **{name}**! I can download from:\n\n"
        f"{BULLET} YouTube, Instagram, TikTok\n"
        f"{BULLET} Twitter/X, Facebook\n"
        f"{BULLET} Google Drive, Terabox\n"
        f"{BULLET} M3U8 Streams & Direct Links\n\n"
        f"Just send me any URL! ✨\n\n{DIVIDER}\n{FOOTER}",
        reply_markup=kb
    )


@Client.on_message(filters.command("help") & ~filters.outgoing)
@ensure_registered
@not_banned
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n**{BOT_NAME} — Help Guide** 📖\n{DIVIDER}\n\n"
        f"**User Commands:**\n"
        f"`/start` — Welcome\n"
        f"`/help` — This guide\n"
        f"`/ping` — Latency check\n"
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
        f"`/feedback [text]` — Feedback\n\n"
        f"**Quality Options:**\n"
        f"`144p | 360p | 720p | 1080p | Audio | Best`\n\n"
        f"**Bulk:** Send a `.txt` file with URLs!\n\n"
        f"{DIVIDER}\n{BULLET} Support: @{SUPPORT_USERNAME}\n{FOOTER}"
    )


@Client.on_message(filters.command("ping") & ~filters.outgoing)
async def ping_cmd(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    ms = (time.time() - start) * 1000
    await msg.edit_text(f"🏓 **Pong!**\n\n{BULLET} Latency: `{ms:.2f}ms`\n{BULLET} Status: `🟢 Online`")


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
        f"**Premium 💎**\n{BULLET} `{PREMIUM_LIMIT}` downloads/day · 365 days\n\n"
        f"**Owner 👑**\n{BULLET} Unlimited · Lifetime\n\n"
        f"{DIVIDER}\n{BULLET} Contact @{SUPPORT_USERNAME} to upgrade!\n{FOOTER}"
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
    plan = user.get("plan", "free")
    pi = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count", 0)
    rem = "Unlimited" if pi["limit"] >= 999999 else str(max(0, pi["limit"] - used))
    await message.reply_text(
        f"{HEADER}\n**Your Stats** 📊\n{DIVIDER}\n\n"
        f"{BULLET} Plan: `{pi['name']}`\n"
        f"{BULLET} Used Today: `{used}`\n"
        f"{BULLET} Remaining: `{rem}`\n"
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
        f"{BULLET} Auto Thumbnail: `Enabled`\n"
        f"{BULLET} FFmpeg Remux: `Enabled`\n"
        f"{BULLET} Progress Interval: `3.5s`\n"
        f"{BULLET} Flood Protection: `Enabled`\n\n{FOOTER}"
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
    await message.reply_text(f"✅ **Feedback received!** 💎\n{BULLET} Support: @{SUPPORT_USERNAME}")


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
        f"**How to refresh cookies:**\n"
        f"`1.` Install **Get cookies.txt LOCALLY** extension\n"
        f"`2.` Login to YouTube in browser\n"
        f"`3.` Export cookies as **Netscape format**\n"
        f"`4.` Paste into `YT_COOKIES` env on Render\n"
        f"`5.` Redeploy ✅\n\n{FOOTER}"
    )


@Client.on_message(filters.command("speedtest") & ~filters.outgoing)
@ensure_registered
@not_banned
async def speedtest_cmd(client: Client, message: Message):
    import aiohttp
    msg = await message.reply_text("⚡ **Testing download speed...**")
    try:
        start = time.time()
        downloaded = 0
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://speed.cloudflare.com/__down?bytes=5000000",
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                async for chunk in resp.content.iter_chunked(65536):
                    downloaded += len(chunk)
        elapsed = time.time() - start
        speed_mb = downloaded / elapsed / 1_000_000
        speed_mbps = speed_mb * 8
        await msg.edit_text(
            f"{HEADER}\n**Speed Test** ⚡\n{DIVIDER}\n\n"
            f"{BULLET} Downloaded: `{fmt_size(downloaded)}`\n"
            f"{BULLET} Time: `{elapsed:.2f}s`\n"
            f"{BULLET} Speed: `{speed_mb:.2f} MB/s` · `{speed_mbps:.1f} Mbps`\n\n{FOOTER}"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Speed test failed: `{e}`")


@Client.on_message(filters.command("formats") & ~filters.outgoing)
@ensure_registered
@not_banned
async def formats_cmd(client: Client, message: Message):
    import asyncio
    url = " ".join(message.command[1:]).strip()
    if not url:
        await message.reply_text("ℹ️ Usage: `/formats [URL]`")
        return
    msg = await message.reply_text("🔍 **Fetching available formats...**")
    try:
        import yt_dlp
        loop = asyncio.get_event_loop()

        def _get():
            with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    return []
                seen, result = set(), []
                for f in reversed(info.get("formats", [])):
                    h = f.get("height")
                    ext = f.get("ext", "?")
                    note = f.get("format_note", "")
                    if h and h not in seen:
                        seen.add(h)
                        result.append(f"`{h}p` · `{ext}` · {note}")
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
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^help$"))
async def cb_help(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"Send any URL to download!\n\nUse `/help` for commands.\nUse `/cookies` for cookie status.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^mystats$"))
async def cb_mystats(client: Client, query: CallbackQuery):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    plan = user.get("plan","free") if user else "free"
    pi = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count", 0) if user else 0
    rem = "∞" if pi["limit"] >= 999999 else str(max(0, pi["limit"] - used))
    await query.message.edit_text(
        f"**Stats** 📊\n\n{BULLET} Plan: `{pi['name']}`\n{BULLET} Used: `{used}`\n{BULLET} Left: `{rem}`",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_start")]])
    )


@Client.on_callback_query(filters.regex("^back_start$"))
async def cb_back_start(client: Client, query: CallbackQuery):
    await query.answer()
    name = query.from_user.first_name or "User"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Plans", callback_data="plans"),
         InlineKeyboardButton("❓ Help", callback_data="help")],
        [InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
         InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
        [InlineKeyboardButton("🍪 Cookie Status", callback_data="cookie_status")],
    ])
    await query.message.edit_text(
        f"{HEADER}\n**{BOT_NAME}** 🎉\n{DIVIDER}\n\nHello **{name}**! Send a URL to download! ✨\n\n{FOOTER}",
        reply_markup=kb
    )
