"""
Serena Bot - Reactions
Auto react to messages — group=99 lowest priority
"""
import random, asyncio
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait, ReactionInvalid, ChatAdminRequired, UserBannedInChannel

import sys, os
_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _root not in sys.path:
    sys.path.insert(0, _root)

from config import REACTION_EMOJIS

REACT_CHANCE = 0.65

# Basic emojis most chats allow
SAFE_EMOJIS = ["👍","❤️","🔥","🎉","😍","👏","🤩","💯","⚡","🌟"]


@Client.on_message(
    ~filters.outgoing,
    group=99
)
async def auto_react(client: Client, message: Message):
    if not message.from_user:
        return
    if random.random() > REACT_CHANCE:
        return
    if not (message.text or message.photo or message.video or message.document or message.audio):
        return

    await asyncio.sleep(random.uniform(1.0, 4.0))

    # Try full emoji list first, fallback to safe basic ones
    for emoji_list in [REACTION_EMOJIS, SAFE_EMOJIS]:
        emoji = random.choice(emoji_list)
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
            except (ReactionInvalid, ChatAdminRequired, UserBannedInChannel):
                break  # try safe list
            except Exception:
                return
