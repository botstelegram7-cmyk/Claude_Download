"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Decorators   ║
╚══════════════════════════════════════════╝
"""

import functools
from pyrogram.types import Message
import database as db
from config import OWNER_IDS


def owner_only(func):
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.from_user and message.from_user.id not in OWNER_IDS:
            await message.reply_text(
                "❌ **Access Denied**\n\n"
                "▸ This command is restricted to the bot owner only."
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def not_banned(func):
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if not message.from_user:
            return
        user = await db.get_user(message.from_user.id)
        if user and user.get("is_banned"):
            await message.reply_text(
                "🚫 **You have been banned**\n\n"
                "▸ Contact support if this is a mistake.\n"
                f"▸ Support: @TechnicalSerena"
            )
            return
        return await func(client, message, *args, **kwargs)
    return wrapper


def ensure_registered(func):
    @functools.wraps(func)
    async def wrapper(client, message: Message, *args, **kwargs):
        if message.from_user:
            await db.ensure_user(
                message.from_user.id,
                message.from_user.username
            )
        return await func(client, message, *args, **kwargs)
    return wrapper
