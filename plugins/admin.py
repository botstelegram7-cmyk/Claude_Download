"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Admin        ║
╚══════════════════════════════════════════╝
"""

import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import Message
import database as db
from utils.decorators import owner_only, ensure_registered
from utils.helpers import BULLET, DIVIDER, HEADER, FOOTER
from config import PLANS, OWNER_IDS


def parse_target(message: Message):
    """Extract user_id or username from command args."""
    args = message.command[1:]
    if not args:
        return None
    target = args[0].lstrip("@")
    if target.isdigit():
        return int(target)
    return target  # username string


@Client.on_message(filters.command("givepremium") & ~filters.outgoing)
@owner_only
async def givepremium_cmd(client: Client, message: Message):
    """Usage: /givepremium <user_id|@username> <basic|premium>"""
    args = message.command[1:]
    if len(args) < 2:
        await message.reply_text(
            "Usage: `/givepremium <user_id> <basic|premium>`\n"
            "Example: `/givepremium 123456789 premium`"
        )
        return

    target = args[0].lstrip("@")
    plan = args[1].lower()

    if plan not in ("basic", "premium"):
        await message.reply_text("❌ Plan must be `basic` or `premium`.")
        return

    try:
        user_id = int(target) if target.isdigit() else None
        if not user_id:
            await message.reply_text("❌ Please provide a numeric user ID.")
            return

        await db.ensure_user(user_id)
        days = PLANS[plan]["days"]
        await db.set_plan(user_id, plan, days)

        await message.reply_text(
            f"✅ **Plan Updated!**\n\n"
            f"{BULLET} User: `{user_id}`\n"
            f"{BULLET} Plan: `{PLANS[plan]['name']}`\n"
            f"{BULLET} Duration: `{days} days`"
        )
        # Notify user
        try:
            await client.send_message(
                user_id,
                f"🎉 **Your plan has been upgraded!**\n\n"
                f"{BULLET} New Plan: `{PLANS[plan]['name']}`\n"
                f"{BULLET} Duration: `{days} days`\n\n"
                f"Enjoy your premium access! 💎"
            )
        except Exception:
            pass
    except Exception as e:
        await message.reply_text(f"❌ Error: `{e}`")


@Client.on_message(filters.command("removepremium") & ~filters.outgoing)
@owner_only
async def removepremium_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text("Usage: `/removepremium <user_id>`")
        return

    target = args[0].lstrip("@")
    if not target.isdigit():
        await message.reply_text("❌ Provide a numeric user ID.")
        return

    user_id = int(target)
    await db.set_plan(user_id, "free", 0)
    await message.reply_text(f"✅ User `{user_id}` reverted to Free plan.")

    try:
        await client.send_message(
            user_id,
            "ℹ️ Your plan has been reverted to **Free 🆓**.\n"
            "Contact @TechnicalSerena for more info."
        )
    except Exception:
        pass


@Client.on_message(filters.command("ban") & ~filters.outgoing)
@owner_only
async def ban_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text("Usage: `/ban <user_id>`")
        return
    target = args[0].lstrip("@")
    if not target.isdigit():
        await message.reply_text("❌ Provide a numeric user ID.")
        return
    user_id = int(target)
    await db.ensure_user(user_id)
    await db.ban_user(user_id)
    await message.reply_text(f"🚫 User `{user_id}` has been **banned**.")
    try:
        await client.send_message(user_id, "🚫 You have been banned from using this bot.")
    except Exception:
        pass


@Client.on_message(filters.command("unban") & ~filters.outgoing)
@owner_only
async def unban_cmd(client: Client, message: Message):
    args = message.command[1:]
    if not args:
        await message.reply_text("Usage: `/unban <user_id>`")
        return
    target = args[0].lstrip("@")
    if not target.isdigit():
        await message.reply_text("❌ Provide a numeric user ID.")
        return
    user_id = int(target)
    await db.unban_user(user_id)
    await message.reply_text(f"✅ User `{user_id}` has been **unbanned**.")
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
    status_msg = await message.reply_text(f"📢 Broadcasting to `{len(users)}` users...")

    sent = 0
    failed = 0
    for user in users:
        try:
            await client.send_message(
                user["user_id"],
                f"📢 **Broadcast Message**\n\n{text}"
            )
            sent += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ **Broadcast Complete!**\n\n"
        f"{BULLET} Sent: `{sent}`\n"
        f"{BULLET} Failed: `{failed}`"
    )


@Client.on_message(filters.command("stats") & ~filters.outgoing)
@owner_only
async def stats_cmd(client: Client, message: Message):
    stats = await db.get_stats()
    plans = stats.get("plans", {})
    plan_lines = "\n".join(
        f"{BULLET} `{k}`: `{v}`" for k, v in plans.items()
    )
    await message.reply_text(
        f"{HEADER}\n**Bot Statistics** 📊\n{DIVIDER}\n\n"
        f"{BULLET} Total Users: `{stats['total_users']}`\n"
        f"{BULLET} Banned: `{stats['banned']}`\n"
        f"{BULLET} Total Downloads: `{stats['total_downloads']}`\n"
        f"{BULLET} Successful: `{stats['successful_downloads']}`\n\n"
        f"**Plans:**\n{plan_lines}\n\n"
        f"{FOOTER}"
    )


@Client.on_message(filters.command("users") & ~filters.outgoing)
@owner_only
async def users_cmd(client: Client, message: Message):
    users = await db.get_all_users()
    lines = [f"{HEADER}\n**All Users** 👥\n{DIVIDER}\n"]
    for u in users[:30]:
        uid = u["user_id"]
        uname = f"@{u['username']}" if u.get("username") else "N/A"
        plan = u.get("plan", "free")
        lines.append(f"`{uid}` · {uname} · `{plan}`")
    if len(users) > 30:
        lines.append(f"\n... and `{len(users) - 30}` more.")
    lines.append(f"\n{FOOTER}")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("banned") & ~filters.outgoing)
@owner_only
async def banned_cmd(client: Client, message: Message):
    banned = await db.get_banned_users()
    if not banned:
        await message.reply_text("✅ No banned users.")
        return
    lines = [f"**Banned Users** 🚫\n{DIVIDER}\n"]
    for u in banned:
        uid = u["user_id"]
        uname = f"@{u['username']}" if u.get("username") else "N/A"
        lines.append(f"`{uid}` · {uname}")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.command("restart") & ~filters.outgoing)
@owner_only
async def restart_cmd(client: Client, message: Message):
    await message.reply_text("🔄 **Restarting bot...** Be right back!")
    await asyncio.sleep(1)
    os.execv("/usr/bin/python3", ["python3", "bot.py"])
