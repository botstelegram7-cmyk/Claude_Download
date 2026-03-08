"""
Serena Bot - Auto Reactions
Pyrogram 2.0.106 — tested working method
"""
import random, asyncio, os, sys, logging

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait

logger = logging.getLogger("SerenaBot.Reactions")

REACT_CHANCE = 0.60
EMOJIS = ["👍","❤️","🔥","🎉","😍","👏","🤩","💯","⚡","🌟","🎵","🎬","💎","🚀","🙌","😎"]


@Client.on_message(~filters.outgoing, group=99)
async def auto_react(client: Client, message: Message):
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

        # Pyrogram 2.0.106 exact API
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
        logger.error(f"Reaction error: {e}")
        pass  # reactions are optional, never crash bot
