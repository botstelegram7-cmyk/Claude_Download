"""
Serena Bot - Auto Reactions
Fixed: Only works in private chats, uses simple emoji strings.
"""
import random
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

logger = logging.getLogger("SerenaBot.Reactions")

REACT_CHANCE = 0.60
EMOJIS = ["👍", "❤️", "🔥", "🎉", "😍", "👏", "🤩", "💯", "⚡", "🌟", "🎵", "🎬", "💎", "🚀", "🙌", "😎"]


@Client.on_message(~filters.outgoing & filters.private, group=99)
async def auto_react(client: Client, message):
    """Automatically react to user messages in private chat."""
    try:
        if not message.from_user:
            return
        if not (message.text or message.photo or message.video
                or message.document or message.audio):
            return
        if random.random() > REACT_CHANCE:
            return

        await asyncio.sleep(random.uniform(1.5, 4.0))
        emoji = random.choice(EMOJIS)

        # Ensure emoji is a simple string
        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji,
        )
        logger.debug(f"Reacted to message {message.id} with {emoji}")
    except FloodWait as e:
        logger.warning(f"Flood wait {e.value}s for reaction")
        await asyncio.sleep(e.value + 2)
    except Exception as e:
        # Ignore any reaction errors – they are non‑critical
        logger.debug(f"Reaction error (ignored): {e}")
