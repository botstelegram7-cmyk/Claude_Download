"""
Serena Bot - Auto Reactions + DM Popup
- Reacts to messages with random emoji
- Also sends a random DM popup message to the user
"""
import random
import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, ReactionInvalid, ChatAdminRequired, UserIsBlocked, PeerIdInvalid

logger = logging.getLogger("SerenaBot.Reactions")

REACT_CHANCE = 0.65   # 65% chance to react
DM_CHANCE    = 0.40   # 40% chance to also send a DM popup

EMOJIS = [
    "👍","❤️","🔥","🎉","😍","👏","🤩","💯","⚡","🌟",
    "🎵","🎬","💎","🚀","🙌","😎","🫡","🥰","💪","✨",
]

# Random DM popup messages
DM_MESSAGES = [
    "🔥 **Hey!** Your download request is looking great! Keep using Serena Downloader ✨",
    "⚡ **Psst!** Did you know you can use `/audio` to extract audio from any video? Try it!",
    "💎 **Hey there!** Upgrade to Premium for 50 downloads/day! Contact @TechnicalSerena",
    "🎬 **Tip:** Send me a `.txt` file with multiple URLs to bulk download everything at once!",
    "🌟 **Hello!** You can use `/info [url]` to preview any video before downloading it!",
    "🚀 **Quick tip:** I support YouTube, Instagram, TikTok, Twitter, and 50+ more sites!",
    "🎵 **Hey!** Want just the audio? Use `/audio [url]` for MP3 downloads!",
    "💫 **Did you know?** I can download directly from googlevideo, M3U8 streams and more!",
    "🤩 **Pro tip:** For large files (>2GB) I can upload to GoFile.io automatically!",
    "👋 **Hey!** Thanks for using Serena Downloader! Share it with your friends 💙",
]


async def can_react(client: Client, chat_id: int) -> bool:
    try:
        chat = await client.get_chat(chat_id)
        if chat.type == ChatType.PRIVATE:
            return True
        member = await client.get_chat_member(chat_id, (await client.get_me()).id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def send_dm_popup(client: Client, user_id: int):
    """Send a random popup DM to the user."""
    try:
        msg = random.choice(DM_MESSAGES)
        await client.send_message(user_id, msg)
        logger.debug(f"DM popup sent to {user_id}")
    except (UserIsBlocked, PeerIdInvalid):
        pass  # User has blocked the bot or is unreachable
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logger.debug(f"DM popup error (ignored): {e}")


@Client.on_message(~filters.outgoing, group=99)
async def auto_react(client: Client, message):
    """React to user messages + optionally send DM popup."""
    try:
        if not message.from_user:
            return
        if not (message.text or message.photo or message.video
                or message.document or message.audio):
            return
        if random.random() > REACT_CHANCE:
            return
        if not await can_react(client, message.chat.id):
            return

        await asyncio.sleep(random.uniform(1.5, 4.0))
        emoji = random.choice(EMOJIS)

        await client.send_reaction(
            chat_id=message.chat.id,
            message_id=message.id,
            emoji=emoji,
        )
        logger.debug(f"Reacted to {message.id} with {emoji}")

        # DM popup — only in groups (don't DM in private chats)
        if (message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
                and random.random() < DM_CHANCE):
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await send_dm_popup(client, message.from_user.id)

    except FloodWait as e:
        logger.warning(f"Flood wait {e.value}s for reaction")
        await asyncio.sleep(e.value + 2)
    except (ReactionInvalid, ChatAdminRequired) as e:
        logger.debug(f"Reaction not allowed: {e}")
    except Exception as e:
        logger.debug(f"Reaction error (ignored): {e}")
