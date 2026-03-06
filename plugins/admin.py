"""
Serena Downloader Bot - Admin Commands
"""
import os, sys, asyncio

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
import database as db
from utils.decorators import owner_only, ensure_registered
from utils.helpers import BULLET, DIVIDER, HEADER, FOOTER
from config import PLANS, OWNER_IDS
import config as _cfg


@Client.on_message(filters.command("givepremium") & ~filters.outgoing)
@owner_only
async def givepremium_cmd(client: Client, message: Message):
    args = message.command[1:]
    if len(args) < 2:
        await message.reply_text("Usage: `/givepremium <user_id> <basic|premium>`")
        return
    if not args[0].lstrip("@").isdigit():
        await message.reply_text("❌ Numeric user ID required.")
        return
    user_id = int(args[0].lstrip("@"))
    plan = args[1].lower()
    if plan not in ("basic","premium"):
        await message.reply_text("❌ Plan must be `basic` or `premium`.")
        return
    await db.ensure_user(user_id)
    days = PLANS[plan]["days"]
    await db.set_plan(user_id, plan, days)
    await message.reply_text(
        f"✅ **Plan Updated!**\n{BULLET} User: `{user_id}`\n{BULLET} Plan: `{PLANS[plan]['name']}`\n{BULLET} Duration: `{days}d`"
    )
    try:
        await client.send_message(user_id,
            f"🎉 **Plan upgraded to {PLANS[plan]['name']}!**\n{BULLET} Duration: `{days} days`\nEnjoy! 💎")
    except Exception:
        pass


@Client.on_message(filters.command("removepremium") & ~filters.outgoing)
@owner_only
async def removepremium_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args or not args[0].lstrip("@").isdigit():
        await message.reply_text("Usage: `/removepremium <user_id>`")
        return
    user_id = int(args[0].lstrip("@"))
    await db.set_plan(user_id, "free", 0)
    await message.reply_text(f"✅ User `{user_id}` reverted to **Free**.")
    try:
        await client.send_message(user_id, "ℹ️ Your plan has been reverted to **Free 🆓**.")
    except Exception:
        pass


@Client.on_message(filters.command("ban") & ~filters.outgoing)
@owner_only
async def ban_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args or not args[0].lstrip("@").isdigit():
        await message.reply_text("Usage: `/ban <user_id>`")
        return
    user_id = int(args[0].lstrip("@"))
    await db.ensure_user(user_id)
    await db.ban_user(user_id)
    await message.reply_text(f"🚫 User `{user_id}` **banned**.")
    try:
        await client.send_message(user_id, "🚫 You have been banned. Contact @TechnicalSerena.")
    except Exception:
        pass


@Client.on_message(filters.command("unban") & ~filters.outgoing)
@owner_only
async def unban_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args or not args[0].lstrip("@").isdigit():
        await message.reply_text("Usage: `/unban <user_id>`")
        return
    user_id = int(args[0].lstrip("@"))
    await db.unban_user(user_id)
    await message.reply_text(f"✅ User `{user_id}` **unbanned**.")
    try:
        await client.send_message(user_id, "✅ You have been unbanned! Welcome back.")
    except Exception:
        pass


@Client.on_message(filters.command("broadcast") & ~filters.outgoing)
@owner_only
async def broadcast_cmd(client: Client, message: Message):
    text = " ".join(message.command[1:]).strip()
    if not text:
        await message.reply_text("Usage: `/broadcast <message>`")
        return
    users = await db.get_all_users()
    msg = await message.reply_text(f"📢 Broadcasting to `{len(users)}` users...")
    sent = failed = 0
    for user in users:
        for attempt in range(2):
            try:
                await client.send_message(user["user_id"], f"📢 **Broadcast**\n\n{text}")
                sent += 1
                await asyncio.sleep(0.08)
                break
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
            except Exception:
                failed += 1
                break
    await msg.edit_text(f"✅ **Broadcast done!**\n{BULLET} Sent: `{sent}`\n{BULLET} Failed: `{failed}`")


@Client.on_message(filters.command("stats") & ~filters.outgoing)
@owner_only
async def stats_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    plans_text = "\n".join(f"{BULLET} `{k}`: `{v}`" for k,v in stats.get("plans",{}).items())
    await message.reply_text(
        f"{HEADER}\n**Bot Statistics** 📊\n{DIVIDER}\n\n"
        f"{BULLET} Total Users: `{stats['total_users']}`\n"
        f"{BULLET} Banned: `{stats['banned']}`\n"
        f"{BULLET} Total Downloads: `{stats['total_downloads']}`\n"
        f"{BULLET} Successful: `{stats['successful_downloads']}`\n\n"
        f"**Plans:**\n{plans_text}\n\n{FOOTER}"
    )


@Client.on_message(filters.command("users") & ~filters.outgoing)
@owner_only
async def users_cmd(client: Client, message: Message):
    users = await db.get_all_users()
    lines = [f"**Users** 👥 (`{len(users)}` total)\n{DIVIDER}\n"]
    for u in users[:30]:
        uname = f"@{u['username']}" if u.get("username") else "N/A"
        lines.append(f"`{u['user_id']}` · {uname} · `{u.get('plan','free')}`")
    if len(users) > 30:
        lines.append(f"\n...and `{len(users)-30}` more.")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("banned") & ~filters.outgoing)
@owner_only
async def banned_cmd(client: Client, message: Message):
    banned = await db.get_banned_users()
    if not banned:
        await message.reply_text("✅ No banned users.")
        return
    lines = [f"**Banned Users** 🚫\n"]
    for u in banned:
        uname = f"@{u['username']}" if u.get("username") else "N/A"
        lines.append(f"`{u['user_id']}` · {uname}")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("lock") & ~filters.outgoing)
@owner_only
async def lock_cmd(client: Client, message: Message):
    """Lock bot — non-owners cannot download."""
    _cfg.BOT_LOCK = True
    await message.reply_text("🔒 **Bot locked!** Only owner can use downloads.")


@Client.on_message(filters.command("unlock") & ~filters.outgoing)
@owner_only
async def unlock_cmd(client: Client, message: Message):
    """Unlock bot — all users can download again."""
    _cfg.BOT_LOCK = False
    await message.reply_text("🔓 **Bot unlocked!** All users can download.")


@Client.on_message(filters.command("restart") & ~filters.outgoing)
@owner_only
async def restart_cmd(client: Client, message: Message):
    await message.reply_text("🔄 **Restarting...** Be right back!")
    await asyncio.sleep(1)
    os.execv(sys.executable, [sys.executable, os.path.abspath("bot.py")])
