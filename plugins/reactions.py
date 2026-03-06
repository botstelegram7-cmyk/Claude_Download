"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Reactions    ║
╚══════════════════════════════════════════╝
"""

import os
import sys
import random
import asyncio

# ── sys.path fix — required for Pyrogram plugin loader ──
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from config import REACTION_EMOJIS

REACT_CHANCE = 0.30


@Client.on_message(
    (filters.private | filters.group | filters.channel) & ~filters.outgoing,
    group=99
)
async def auto_react(client: Client, message: Message):
    if random.random() > REACT_CHANCE:
        return
    if not (message.text or message.photo or message.video or message.document or message.audio):
        return

    emoji = random.choice(REACTION_EMOJIS)
    await asyncio.sleep(random.uniform(1.0, 3.0))

    for _ in range(2):
        try:
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=emoji
            )
            return
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except Exception:
            return
