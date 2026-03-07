"""
Serena Bot - Start & User Commands
"""
import os, sys, time, shutil

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import fmt_size, fmt_duration
from config import (
    BOT_NAME, BOT_USERNAME, SUPPORT_USERNAME, SUPPORT_CHANNEL,
    OWNER_USERNAME, PLANS, FREE_LIMIT, BASIC_LIMIT, PREMIUM_LIMIT,
    FORCE_SUB_CHANNEL
)
from queue_manager import queue_manager
import config as _cfg

BOT_START_TIME = time.time()

# ── Theme ────────────────────────────────────────────────────────────────────
H  = "✦"
LN = "─" * 22
B  = "▸"
SP = "  "


def _kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Help",  callback_data="help_dl"),
         InlineKeyboardButton("📋 All Commands",   callback_data="help_cmds")],
        [InlineKeyboardButton("💎 Plans",          callback_data="plans"),
         InlineKeyboardButton("📊 My Stats",       callback_data="mystats")],
        [InlineKeyboardButton("🍪 Cookie Status",  callback_data="cookie_status"),
         InlineKeyboardButton("📜 History",        callback_data="history_cb")],
        [InlineKeyboardButton("💬 Support",        url=f"https://t.me/{SUPPORT_USERNAME}"),
         InlineKeyboardButton("📢 Channel",        url=f"https://t.me/{SUPPORT_CHANNEL}")],
        [InlineKeyboardButton("👤 Owner",          url=f"https://t.me/{OWNER_USERNAME}")],
    ])


def _kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="back_home")]])


async def _check_force_sub(client, user_id) -> bool:
    if not FORCE_SUB_CHANNEL: return True
    try:
        m = await client.get_chat_member(f"@{FORCE_SUB_CHANNEL}", user_id)
        return m.status.value not in ("kicked","left")
    except Exception:
        return True


# ── /start ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("start") & ~filters.outgoing)
@ensure_registered
@not_banned
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    if not await _check_force_sub(client, user.id):
        await message.reply_text(
            f"**🔔 Join Required!**\n\n"
            f"Please join our channel to use {BOT_NAME}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_SUB_CHANNEL}")],
                [InlineKeyboardButton("✅ I Joined", callback_data="check_sub")],
            ])
        )
        return

    locked = getattr(_cfg, "BOT_LOCK", False)
    lock_notice = "\n\n⚠️ **Bot is currently locked by owner.**" if locked else ""

    await message.reply_text(
        f"**{H} Welcome to {BOT_NAME}! {H}**\n"
        f"`{LN}`\n\n"
        f"👋 Hello **{user.first_name}**!\n\n"
        f"**What I can do:**\n"
        f"{B} Download videos from **100+ platforms**\n"
        f"{B} TikTok, Twitter/X, Facebook\n"
        f"{B} Direct Links & M3U8 Streams\n"
        f"{B} Google Drive files & folders\n"
        f"{B} Encrypted stream downloads\n\n"
        f"**Just send any URL!** ✨{lock_notice}\n\n"
        f"`{LN}`",
        reply_markup=_kb_main()
    )


@Client.on_callback_query(filters.regex("^check_sub$"))
async def cb_check_sub(client: Client, query: CallbackQuery):
    await query.answer()
    if await _check_force_sub(client, query.from_user.id):
        await query.message.edit_text(
            f"**✅ Verified! Welcome!**\n\nSend me any URL to download!",
            reply_markup=_kb_main()
        )
    else:
        await query.answer("❌ Please join first!", show_alert=True)


# ── /help ─────────────────────────────────────────────────────────────────────

HELP_DL_TEXT = f"""**{H} Download Guide {H}**
`{LN}`

**How to Download:**
{B} Send any URL directly
{B} Bot auto-detects the platform
{B} Choose quality (YouTube only)
{B} File is sent with metadata

**Supported Platforms:**
{B} **TikTok** — Videos, Slideshows
{B} **Twitter/X** — Videos, GIFs
{B} **Facebook** — Videos, Reels
{B} **Google Drive** — Files, Folders
{B} **Direct Links** — MP4, MP3, ZIP, PDF...
{B} **M3U8 Streams** — Including encrypted

**Bulk Download:**
{B} Send a `.txt` file with one URL per line

**Audio Only:**
{B} Use `/audio [url]` for MP3 extraction

**Quality (YouTube & similar):**
`144p | 360p | 720p | 1080p | Audio | Best`

`{LN}`"""

ALL_CMDS_TEXT = f"""**{H} All Commands {H}**
`{LN}`

**Downloads:**
`/audio [url]` — Extract audio as MP3
`/info [url]` — Media info before download
`/formats [url]` — List available formats

**Account:**
`/plans` — View subscription plans
`/mystats` — Your download stats
`/history` — Recent 10 downloads
`/feedback [text]` — Send feedback

**Tools:**
`/ping` — Bot latency & uptime info
`/status` — Bot stats overview
`/speedtest` — Test bot download speed
`/cookies` — YouTube cookie status
`/queue` — Current download queue
`/cancel` — Cancel pending URL selection

**Admin Only:**
`/lock` `/unlock` — Lock/unlock bot
`/ban [id]` `/unban [id]` — Manage users
`/givepremium [id] [plan]` — Upgrade user
`/broadcast [msg]` — Message all users
`/stats` — Full bot statistics
`/restart` — Restart bot

`{LN}`
**Wrong command?** Just send the URL directly!
**Example:** `https://x.com/user/status/123`"""


@Client.on_message(filters.command("help") & ~filters.outgoing)
@ensure_registered
@not_banned
async def help_cmd(client: Client, message: Message):
    await message.reply_text(
        ALL_CMDS_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📥 Download Guide", callback_data="help_dl"),
             InlineKeyboardButton("🔙 Home", callback_data="back_home")],
        ])
    )


@Client.on_callback_query(filters.regex("^help_dl$"))
async def cb_help_dl(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(HELP_DL_TEXT, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 All Commands", callback_data="help_cmds"),
         InlineKeyboardButton("🔙 Home", callback_data="back_home")],
    ]))


@Client.on_callback_query(filters.regex("^help_cmds$"))
async def cb_help_cmds(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(ALL_CMDS_TEXT, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Download Guide", callback_data="help_dl"),
         InlineKeyboardButton("🔙 Home", callback_data="back_home")],
    ]))


# ── /ping ─────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("ping") & ~filters.outgoing)
async def ping_cmd(client: Client, message: Message):
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    latency = (time.time() - start) * 1000
    up = int(time.time() - BOT_START_TIME)
    d,r = divmod(up,86400); h,r = divmod(r,3600); m,s = divmod(r,60)
    uptime = f"{d}d {h}h {m}m {s}s" if d else f"{h}h {m}m {s}s" if h else f"{m}m {s}s"
    total,used,free = shutil.disk_usage("/tmp")
    now = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    lock = "🔒 Locked" if getattr(_cfg,"BOT_LOCK",False) else "🔓 Open"
    await msg.edit_text(
        f"**{H} Bot Info {H}**\n`{LN}`\n\n"
        f"🟢 **Status:** Online\n"
        f"🏓 **Latency:** `{latency:.1f}ms`\n"
        f"⏱ **Uptime:** `{uptime}`\n"
        f"🕐 **Time:** `{now}`\n"
        f"📥 **Active DLs:** `{queue_manager.active_count()}`\n"
        f"📋 **Queue:** `{queue_manager.queue_size()}`\n"
        f"💾 **Temp Free:** `{fmt_size(free)}`\n"
        f"🔑 **Lock:** `{lock}`\n\n"
        f"`{LN}`"
    )


# ── /status ───────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("status") & ~filters.outgoing)
@ensure_registered
async def status_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    await message.reply_text(
        f"**{H} Bot Status {H}**\n`{LN}`\n\n"
        f"👥 **Users:** `{stats['total_users']}`\n"
        f"📥 **Total Downloads:** `{stats['total_downloads']}`\n"
        f"✅ **Successful:** `{stats['successful_downloads']}`\n"
        f"⚡ **Active:** `{queue_manager.active_count()}`\n"
        f"📋 **Queued:** `{queue_manager.queue_size()}`\n\n"
        f"`{LN}`"
    )


# ── /plans ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("plans") & ~filters.outgoing)
@ensure_registered
@not_banned
async def plans_cmd(client: Client, message: Message):
    await message.reply_text(
        f"**{H} Subscription Plans {H}**\n`{LN}`\n\n"
        f"🆓 **Free**\n{SP}{B} `{FREE_LIMIT}` downloads/day\n\n"
        f"🥉 **Basic**\n{SP}{B} `{BASIC_LIMIT}` downloads/day\n{SP}{B} 30 days\n\n"
        f"💎 **Premium**\n{SP}{B} `{PREMIUM_LIMIT}` downloads/day\n{SP}{B} 365 days\n\n"
        f"👑 **Owner**\n{SP}{B} Unlimited · Lifetime\n\n"
        f"`{LN}`\n{B} Contact @{SUPPORT_USERNAME} to upgrade!",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("💬 Upgrade Now", url=f"https://t.me/{SUPPORT_USERNAME}")
        ]])
    )


# ── /mystats ──────────────────────────────────────────────────────────────────

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
    pi   = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count",0)
    lim  = pi["limit"]
    rem  = "Unlimited" if lim>=999999 else str(max(0,lim-used))
    hist = await db.get_user_history(uid, limit=9999)
    ok   = sum(1 for h in hist if h.get("status")=="done")
    await message.reply_text(
        f"**{H} Your Stats {H}**\n`{LN}`\n\n"
        f"💎 **Plan:** `{pi['name']}`\n"
        f"📥 **Used Today:** `{used}`\n"
        f"✅ **Remaining:** `{rem}`\n"
        f"📊 **Total DLs:** `{len(hist)}`\n"
        f"🎯 **Success:** `{ok}`\n"
        f"📅 **Expiry:** `{user.get('plan_expiry') or 'N/A'}`\n"
        f"🗓 **Joined:** `{user.get('joined_at','N/A')[:10]}`\n\n"
        f"`{LN}`"
    )


# ── /history ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("history") & ~filters.outgoing)
@ensure_registered
@not_banned
async def history_cmd(client: Client, message: Message):
    hist = await db.get_user_history(message.from_user.id, limit=10)
    if not hist:
        await message.reply_text("📭 No download history yet.")
        return
    lines = [f"**{H} Recent Downloads {H}**\n`{LN}`\n"]
    for i, dl in enumerate(hist, 1):
        title = (dl.get("title") or "")[:35] or "Unknown"
        icon  = "✅" if dl.get("status")=="done" else "❌"
        date  = (dl.get("created_at") or "")[:10]
        lines.append(f"`{i:02d}.` {icon} `{title}`\n{SP}`{date}`")
    lines.append(f"\n`{LN}`")
    await message.reply_text("\n\n".join(lines))


# ── /settings ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("settings") & ~filters.outgoing)
@ensure_registered
async def settings_cmd(client: Client, message: Message):
    await message.reply_text(
        f"**{H} Settings {H}**\n`{LN}`\n\n"
        f"{B} Thumbnail: `Smart (no black frames)`\n"
        f"{B} Metadata Caption: `Enabled`\n"
        f"{B} MP4 Faststart: `Enabled`\n"
        f"{B} Playlist ZIP: `Enabled`\n"
        f"{B} Progress Bar: `Download + Upload`\n"
        f"{B} Reactions: `75% chance, 1-4s delay`\n"
        f"{B} Queue Delay: `2s between jobs`\n"
        f"{B} Force Sub: `{'@'+FORCE_SUB_CHANNEL if FORCE_SUB_CHANNEL else 'Off'}`\n\n"
        f"`{LN}`"
    )


# ── /queue ────────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("queue") & ~filters.outgoing)
async def queue_cmd(client: Client, message: Message):
    await message.reply_text(
        f"**📋 Queue Status**\n\n"
        f"{B} Active: `{queue_manager.active_count()}`\n"
        f"{B} Waiting: `{queue_manager.queue_size()}`"
    )


# ── /feedback ─────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("feedback") & ~filters.outgoing)
@ensure_registered
@not_banned
async def feedback_cmd(client: Client, message: Message):
    text = " ".join(message.command[1:]).strip()
    if not text:
        await message.reply_text(
            f"💬 **Usage:** `/feedback Your message here`\n\n"
            f"**Example:** `/feedback The bot downloaded perfectly, thanks!`"
        )
        return
    await db.save_feedback(message.from_user.id, text)
    await message.reply_text(f"✅ **Feedback received!**\n{B} Thank you for helping us improve!")


# ── /cookies ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("cookies") & ~filters.outgoing)
@ensure_registered
async def cookies_cmd(client: Client, message: Message):
    msg = await message.reply_text("🍪 Checking cookie status...")
    from downloader.core import check_yt_cookies_status
    result = await check_yt_cookies_status()
    icon = "✅" if result["valid"] else ("⚠️" if result["expired"] else "❌")
    await msg.edit_text(
        f"**{H} Cookie Status {H}**\n`{LN}`\n\n"
        f"{icon} {result['message']}\n\n"
        f"**How to set cookies on Render:**\n"
        f"`1.` Install **Get cookies.txt LOCALLY** (Chrome extension)\n"
        f"`2.` Visit YouTube while logged in\n"
        f"`3.` Click extension → Export Netscape format\n"
        f"`4.` Render → Service → Environment\n"
        f"`5.` Key: `YT_COOKIES` → Paste full file content\n"
        f"`6.` Save → Redeploy ✅\n\n"
        f"`{LN}`"
    )


# ── /speedtest ────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("speedtest") & ~filters.outgoing)
@ensure_registered
@not_banned
async def speedtest_cmd(client: Client, message: Message):
    import aiohttp
    msg = await message.reply_text("⚡ Testing speed...")
    try:
        start = time.time()
        done = 0
        async with aiohttp.ClientSession() as s:
            async with s.get("https://speed.cloudflare.com/__down?bytes=5000000",
                              timeout=aiohttp.ClientTimeout(total=30)) as r:
                async for chunk in r.content.iter_chunked(65536):
                    done += len(chunk)
        elapsed = time.time() - start
        mb = done / elapsed / 1_000_000
        await msg.edit_text(
            f"**{H} Speed Test {H}**\n`{LN}`\n\n"
            f"{B} File: `{fmt_size(done)}`\n"
            f"{B} Time: `{elapsed:.2f}s`\n"
            f"{B} Speed: `{mb:.2f} MB/s` · `{mb*8:.1f} Mbps`\n\n"
            f"`{LN}`"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Speed test failed: `{e}`")


# ── /formats ──────────────────────────────────────────────────────────────────

@Client.on_message(filters.command("formats") & ~filters.outgoing)
@ensure_registered
@not_banned
async def formats_cmd(client: Client, message: Message):
    import asyncio, yt_dlp
    url = " ".join(message.command[1:]).strip()
    if not url:
        await message.reply_text(
            f"📋 **Usage:** `/formats [URL]`\n\n"
            f"**Example:** `/formats https://youtu.be/dQw4w9WgXcQ`"
        )
        return
    msg = await message.reply_text("🔍 Fetching formats...")
    try:
        loop = asyncio.get_event_loop()
        def _get():
            with yt_dlp.YoutubeDL({"quiet":True,"no_warnings":True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info: return []
                seen, out = set(), []
                for f in reversed(info.get("formats",[])):
                    h = f.get("height")
                    if h and h not in seen:
                        seen.add(h)
                        tbr = f.get("tbr",0)
                        out.append(f"`{h}p` · `{f.get('ext','?')}` · {f.get('format_note','')}"
                                   + (f" · `{int(tbr)}kbps`" if tbr else ""))
                return out[:12]
        fmts = await loop.run_in_executor(None, _get)
        if not fmts:
            await msg.edit_text("❌ No formats found.")
            return
        lines = "\n".join(f"{B} {f}" for f in fmts)
        await msg.edit_text(
            f"**{H} Available Formats {H}**\n`{LN}`\n\n{lines}\n\n`{LN}`"
        )
    except Exception as e:
        await msg.edit_text(f"❌ Error: `{str(e)[:200]}`")


# ── Callbacks ─────────────────────────────────────────────────────────────────

@Client.on_callback_query(filters.regex("^back_home$"))
async def cb_back_home(client: Client, query: CallbackQuery):
    await query.answer()
    name = query.from_user.first_name or "User"
    await query.message.edit_text(
        f"**{H} Welcome to {BOT_NAME}! {H}**\n`{LN}`\n\n"
        f"👋 Hello **{name}**!\n\n"
        f"{B} Send any URL to download! ✨\n\n`{LN}`",
        reply_markup=_kb_main()
    )


@Client.on_callback_query(filters.regex("^plans$"))
async def cb_plans(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"**{H} Plans {H}**\n`{LN}`\n\n"
        f"🆓 **Free** — `{FREE_LIMIT}`/day\n"
        f"🥉 **Basic** — `{BASIC_LIMIT}`/day · 30 days\n"
        f"💎 **Premium** — `{PREMIUM_LIMIT}`/day · 365 days\n"
        f"👑 **Owner** — Unlimited\n\n"
        f"{B} Contact @{SUPPORT_USERNAME}\n`{LN}`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 Upgrade", url=f"https://t.me/{SUPPORT_USERNAME}")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_home")],
        ])
    )


@Client.on_callback_query(filters.regex("^mystats$"))
async def cb_mystats(client: Client, query: CallbackQuery):
    await query.answer()
    user = await db.get_user(query.from_user.id)
    plan = user.get("plan","free") if user else "free"
    pi   = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count",0) if user else 0
    rem  = "∞" if pi["limit"]>=999999 else str(max(0,pi["limit"]-used))
    await query.message.edit_text(
        f"**Stats**\n\n{B} Plan: `{pi['name']}`\n{B} Used: `{used}`\n{B} Left: `{rem}`",
        reply_markup=_kb_back()
    )


@Client.on_callback_query(filters.regex("^history_cb$"))
async def cb_history(client: Client, query: CallbackQuery):
    await query.answer()
    hist = await db.get_user_history(query.from_user.id, limit=5)
    if not hist:
        await query.message.edit_text("📭 No downloads yet!", reply_markup=_kb_back())
        return
    lines = ["**Recent Downloads**\n"]
    for i, dl in enumerate(hist, 1):
        title = (dl.get("title") or "")[:30] or "Unknown"
        icon  = "✅" if dl.get("status")=="done" else "❌"
        lines.append(f"`{i}.` {icon} `{title}`")
    await query.message.edit_text("\n".join(lines), reply_markup=_kb_back())


@Client.on_callback_query(filters.regex("^cookie_status$"))
async def cb_cookie_status(client: Client, query: CallbackQuery):
    await query.answer("Checking...")
    from downloader.core import check_yt_cookies_status
    result = await check_yt_cookies_status()
    icon = "✅" if result["valid"] else ("⚠️" if result["expired"] else "❌")
    await query.message.edit_text(
        f"**Cookie Status** 🍪\n\n{icon} {result['message']}\n\nUse `/cookies` for full guide.",
        reply_markup=_kb_back()
    )


@Client.on_callback_query(filters.regex("^settings_cb$"))
async def cb_settings(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"**Settings ⚙️**\n\n"
        f"{B} Thumbnail: Smart\n{B} Faststart MP4: On\n"
        f"{B} Progress: DL+UL\n{B} Reactions: 75%",
        reply_markup=_kb_back()
    )
