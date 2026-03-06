"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Reactions    ║
╚══════════════════════════════════════════╝
Auto-react to messages with random emojis.
"""

import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, ReactionType
from config import REACTION_EMOJIS


REACT_CHANCE = 0.35  # 35% chance to react


async def _react(client: Client, message: Message):
    """Send a random emoji reaction to a message."""
    try:
        emoji = random.choice(REACTION_EMOJIS)
        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji
        )
    except Exception:
        pass  # Silently ignore reaction errors


@Client.on_message(
    (filters.private | filters.group | filters.channel) & ~filters.outgoing
)
async def auto_react(client: Client, message: Message):
    """Randomly react to messages, photos, videos, documents."""
    if random.random() > REACT_CHANCE:
        return

    # React to: text, photo, video, document (PDF etc.)
    if message.text or message.photo or message.video or message.document or message.audio:
        await asyncio.sleep(random.uniform(0.5, 2.5))
        await _react(client, message)
