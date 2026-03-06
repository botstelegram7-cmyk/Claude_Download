"""
Serena Downloader Bot - Reactions
Random reactions on messages in groups AND DMs
"""
import os, sys, asyncio, random

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from config import REACTION_EMOJIS

REACTION_CHANCE = 0.75


@Client.on_message(
    (filters.text | filters.photo | filters.video | filters.document)
    & ~filters.outgoing,
    group=99
)
async def auto_react(client: Client, message: Message):
    if random.random() > REACTION_CHANCE:
        return
    if not message.from_user:
        return

    await asyncio.sleep(random.uniform(1.0, 4.0))

    emoji = random.choice(REACTION_EMOJIS)
    for attempt in range(3):
        try:
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=emoji,   # Pyrogram 2.x uses emoji= directly
            )
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            return
