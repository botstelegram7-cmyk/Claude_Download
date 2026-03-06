"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Start        ║
╚══════════════════════════════════════════╝
"""

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import database as db
from utils.decorators import not_banned, ensure_registered
from utils.helpers import make_header, make_footer, BULLET, DIVIDER, HEADER, FOOTER
from config import (
    BOT_NAME, BOT_USERNAME, OWNER_USERNAME, SUPPORT_USERNAME,
    PLANS, FREE_LIMIT, BASIC_LIMIT, PREMIUM_LIMIT
)
from queue_manager import queue_manager


@Client.on_message(filters.command("start") & ~filters.outgoing)
@ensure_registered
@not_banned
async def start_cmd(client: Client, message: Message):
    user = message.from_user
    name = user.first_name or "User"

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Plans", callback_data="plans"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
        ],
    ])

    await message.reply_text(
        f"{HEADER}\n"
        f"**Welcome to {BOT_NAME}!** 🎉\n"
        f"{DIVIDER}\n\n"
        f"Hello **{name}**! I can download from:\n\n"
        f"{BULLET} YouTube, Instagram, TikTok\n"
        f"{BULLET} Twitter/X, Facebook\n"
        f"{BULLET} Google Drive, Terabox\n"
        f"{BULLET} M3U8 Streams & Direct Links\n\n"
        f"Just send me any URL and I'll handle the rest! ✨\n\n"
        f"{DIVIDER}\n"
        f"{FOOTER}",
        reply_markup=kb
    )


@Client.on_message(filters.command("help") & ~filters.outgoing)
@ensure_registered
@not_banned
async def help_cmd(client: Client, message: Message):
    text = (
        f"{HEADER}\n"
        f"**{BOT_NAME} — Help Guide** 📖\n"
        f"{DIVIDER}\n\n"
        f"**▸ How to Download:**\n"
        f"Simply send a URL from any supported platform.\n\n"
        f"**▸ User Commands:**\n"
        f"`/start` — Welcome message\n"
        f"`/help` — This help guide\n"
        f"`/ping` — Check bot latency\n"
        f"`/status` — Bot status\n"
        f"`/plans` — Subscription plans\n"
        f"`/mystats` — Your download stats\n"
        f"`/history` — Recent downloads\n"
        f"`/settings` — Bot settings\n"
        f"`/audio [url]` — Extract audio\n"
        f"`/info [url]` — Media information\n"
        f"`/queue` — View your queue\n"
        f"`/cancel` — Cancel current download\n"
        f"`/feedback [text]` — Send feedback\n\n"
        f"**▸ Quality Selection:**\n"
        f"After sending a URL, choose quality:\n"
        f"`144p | 360p | 720p | 1080p | Audio`\n\n"
        f"**▸ Bulk Downloads:**\n"
        f"Send a `.txt` file with one URL per line!\n\n"
        f"{DIVIDER}\n"
        f"{BULLET} Support: @{SUPPORT_USERNAME}\n"
        f"{FOOTER}"
    )
    await message.reply_text(text)


@Client.on_message(filters.command("ping") & ~filters.outgoing)
async def ping_cmd(client: Client, message: Message):
    import time
    start = time.time()
    msg = await message.reply_text("🏓 Pinging...")
    elapsed = (time.time() - start) * 1000
    await msg.edit_text(f"🏓 **Pong!** `{elapsed:.2f}ms`")


@Client.on_message(filters.command("status") & ~filters.outgoing)
@ensure_registered
async def status_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    active = queue_manager.active_count()
    queued = queue_manager.queue_size()

    await message.reply_text(
        f"{HEADER}\n"
        f"**Bot Status** ⚡\n"
        f"{DIVIDER}\n\n"
        f"{BULLET} Status: `🟢 Online`\n"
        f"{BULLET} Total Users: `{stats['total_users']}`\n"
        f"{BULLET} Total Downloads: `{stats['total_downloads']}`\n"
        f"{BULLET} Active Downloads: `{active}`\n"
        f"{BULLET} Queued: `{queued}`\n\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("plans") & ~filters.outgoing)
@ensure_registered
@not_banned
async def plans_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n"
        f"**Subscription Plans** 💎\n"
        f"{DIVIDER}\n\n"
        f"**Free 🆓**\n"
        f"{BULLET} `{FREE_LIMIT}` downloads/day\n"
        f"{BULLET} Basic quality\n\n"
        f"**Basic 🥉**\n"
        f"{BULLET} `{BASIC_LIMIT}` downloads/day\n"
        f"{BULLET} 30 days duration\n"
        f"{BULLET} Priority queue\n\n"
        f"**Premium 💎**\n"
        f"{BULLET} `{PREMIUM_LIMIT}` downloads/day\n"
        f"{BULLET} 365 days duration\n"
        f"{BULLET} Highest priority\n"
        f"{BULLET} All qualities\n\n"
        f"**Owner 👑**\n"
        f"{BULLET} Unlimited downloads\n"
        f"{BULLET} Lifetime access\n\n"
        f"{DIVIDER}\n"
        f"{BULLET} Contact @{SUPPORT_USERNAME} to upgrade!\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("mystats") & ~filters.outgoing)
@ensure_registered
@not_banned
async def mystats_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    await db.check_and_reset_daily(user_id)
    await db.check_plan_expiry(user_id)
    user = await db.get_user(user_id)
    if not user:
        await message.reply_text("❌ User not found.")
        return

    plan = user.get("plan", "free")
    plan_info = PLANS.get(plan, PLANS["free"])
    limit = plan_info["limit"]
    used = user.get("daily_count", 0)
    remaining = max(0, limit - used) if limit < 999999 else "Unlimited"
    expiry = user.get("plan_expiry") or "N/A"

    await message.reply_text(
        f"{HEADER}\n"
        f"**Your Stats** 📊\n"
        f"{DIVIDER}\n\n"
        f"{BULLET} Plan: `{plan_info['name']}`\n"
        f"{BULLET} Daily Used: `{used}`\n"
        f"{BULLET} Remaining: `{remaining}`\n"
        f"{BULLET} Plan Expiry: `{expiry}`\n"
        f"{BULLET} Joined: `{user.get('joined_at', 'N/A')[:10]}`\n\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("history") & ~filters.outgoing)
@ensure_registered
@not_banned
async def history_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    history = await db.get_user_history(user_id, limit=10)
    if not history:
        await message.reply_text("📭 No download history yet.")
        return

    lines = [f"{HEADER}\n**Recent Downloads** 📜\n{DIVIDER}\n"]
    for i, dl in enumerate(history, 1):
        title = (dl.get("title") or dl.get("url", ""))[:40]
        status = dl.get("status", "?")
        date = (dl.get("created_at") or "")[:10]
        lines.append(f"`{i}.` {title}\n   `{status}` · `{date}`")
    lines.append(f"\n{FOOTER}")
    await message.reply_text("\n\n".join(lines))


@Client.on_message(filters.command("settings") & ~filters.outgoing)
@ensure_registered
@not_banned
async def settings_cmd(client: Client, message: Message):
    await message.reply_text(
        f"{HEADER}\n"
        f"**Settings** ⚙️\n"
        f"{DIVIDER}\n\n"
        f"{BULLET} Default Quality: `Best Available`\n"
        f"{BULLET} Auto Thumbnail: `Enabled`\n"
        f"{BULLET} Metadata Injection: `Enabled`\n"
        f"{BULLET} Notifications: `Enabled`\n\n"
        f"More settings coming soon!\n\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("queue") & ~filters.outgoing)
async def queue_cmd(client: Client, message: Message):
    active = queue_manager.active_count()
    queued = queue_manager.queue_size()
    await message.reply_text(
        f"📋 **Queue Status**\n\n"
        f"{BULLET} Active: `{active}`\n"
        f"{BULLET} Waiting: `{queued}`"
    )


@Client.on_message(filters.command("feedback") & ~filters.outgoing)
@ensure_registered
@not_banned
async def feedback_cmd(client: Client, message: Message):
    text = " ".join(message.command[1:]).strip()
    if not text:
        await message.reply_text(
            "💬 Usage: `/feedback Your message here`\n\n"
            "We read every piece of feedback! 💎"
        )
        return
    await db.save_feedback(message.from_user.id, text)
    await message.reply_text(
        f"✅ **Feedback received!** Thank you! 💎\n\n"
        f"Our team will review your message.\n"
        f"{BULLET} Support: @{SUPPORT_USERNAME}"
    )


# ── Callback Queries ──
@Client.on_callback_query(filters.regex("^plans$"))
async def cb_plans(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"{HEADER}\n"
        f"**Subscription Plans** 💎\n"
        f"{DIVIDER}\n\n"
        f"**Free 🆓** — `{FREE_LIMIT}` downloads/day\n"
        f"**Basic 🥉** — `{BASIC_LIMIT}` downloads/day · 30 days\n"
        f"**Premium 💎** — `{PREMIUM_LIMIT}` downloads/day · 365 days\n"
        f"**Owner 👑** — Unlimited · Lifetime\n\n"
        f"{BULLET} Contact @{SUPPORT_USERNAME} to upgrade!\n"
        f"{FOOTER}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_start")
        ]])
    )


@Client.on_callback_query(filters.regex("^help$"))
async def cb_help(client: Client, query: CallbackQuery):
    await query.answer()
    await query.message.edit_text(
        f"**Just send any URL!** 🔗\n\n"
        f"Use `/help` for full command list.\n"
        f"Use `/plans` to see subscription info.",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_start")
        ]])
    )


@Client.on_callback_query(filters.regex("^mystats$"))
async def cb_mystats(client: Client, query: CallbackQuery):
    await query.answer()
    user_id = query.from_user.id
    user = await db.get_user(user_id)
    plan = user.get("plan", "free") if user else "free"
    plan_info = PLANS.get(plan, PLANS["free"])
    used = user.get("daily_count", 0) if user else 0
    limit = plan_info["limit"]
    remaining = max(0, limit - used) if limit < 999999 else "∞"
    await query.message.edit_text(
        f"**Your Stats** 📊\n\n"
        f"{BULLET} Plan: `{plan_info['name']}`\n"
        f"{BULLET} Used Today: `{used}`\n"
        f"{BULLET} Remaining: `{remaining}`",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Back", callback_data="back_start")
        ]])
    )


@Client.on_callback_query(filters.regex("^back_start$"))
async def cb_back_start(client: Client, query: CallbackQuery):
    await query.answer()
    user = query.from_user
    name = user.first_name or "User"
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Plans", callback_data="plans"),
            InlineKeyboardButton("❓ Help", callback_data="help"),
        ],
        [
            InlineKeyboardButton("📊 My Stats", callback_data="mystats"),
            InlineKeyboardButton("💬 Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
        ],
    ])
    await query.message.edit_text(
        f"{HEADER}\n"
        f"**Welcome to {BOT_NAME}!** 🎉\n"
        f"{DIVIDER}\n\n"
        f"Hello **{name}**! Just send me a URL to download! ✨\n\n"
        f"{FOOTER}",
        reply_markup=kb
    )
