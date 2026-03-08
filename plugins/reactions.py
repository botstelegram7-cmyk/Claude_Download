"""
Serena Bot - Auto Reactions
Fixed: Works in groups if bot is admin, otherwise skips.
Uses Pyrogram's send_reaction with safe emoji list.
"""
import random
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, ReactionInvalid, ChatAdminRequired

logger = logging.getLogger("SerenaBot.Reactions")

REACT_CHANCE = 0.60  # 60% chance to react
EMOJIS = ["👍", "❤️", "🔥", "🎉", "😍", "👏", "🤩", "💯", "⚡", "🌟", "🎵", "🎬", "💎", "🚀", "🙌", "😎"]


async def can_react(client: Client, chat_id: int, user_id: int) -> bool:
    """Check if bot can react in this chat (is admin in groups, always in private)."""
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == ChatType.PRIVATE:
            return True
        # For groups/supergroups, check if bot is admin
        member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


@Client.on_message(~filters.outgoing, group=99)
async def auto_react(client: Client, message):
    """Automatically react to user messages in any chat (if allowed)."""
    try:
        if not message.from_user:
            return
        if not (message.text or message.photo or message.video
                or message.document or message.audio):
            return
        if random.random() > REACT_CHANCE:
            return

        # Check if bot can react
        if not await can_react(client, message.chat.id, message.from_user.id):
            logger.debug(f"Skipping reaction in chat {message.chat.id} (not allowed)")
            return

        await asyncio.sleep(random.uniform(1.5, 4.0))
        emoji = random.choice(EMOJIS)

        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji,
        )
        logger.debug(f"Reacted to message {message.id} with {emoji}")
    except FloodWait as e:
        logger.warning(f"Flood wait {e.value}s for reaction")
        await asyncio.sleep(e.value + 2)
    except (ReactionInvalid, ChatAdminRequired) as e:
        logger.debug(f"Reaction not allowed: {e}")
    except Exception as e:
        logger.debug(f"Reaction error (ignored): {e}")
