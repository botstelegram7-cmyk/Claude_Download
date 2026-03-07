"""
Serena Bot - Auto Reactions
Pyrogram 2.0.106 compatible — uses send_reaction with emoji= param
"""
import random, asyncio, os, sys

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

REACT_CHANCE = 0.65

# Use only basic emojis — custom ones fail on many chats
EMOJIS = [
    "👍","❤️","🔥","🎉","😍","👏","🤩","💯",
    "⚡","🌟","🎵","🎬","💎","🚀","🙌","😎",
]


@Client.on_message(~filters.outgoing, group=99)
async def auto_react(client: Client, message: Message):
    if not message.from_user:
        return
    if not (message.text or message.photo or message.video
            or message.document or message.audio):
        return
    if random.random() > REACT_CHANCE:
        return

    await asyncio.sleep(random.uniform(1.5, 4.0))

    emoji = random.choice(EMOJIS)
    try:
        # Pyrogram 2.0.106 — send_reaction takes emoji= as string
        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji,
        )
    except FloodWait as e:
        await asyncio.sleep(e.value + 2)
    except Exception:
        # Silently ignore — reactions are optional
        pass
