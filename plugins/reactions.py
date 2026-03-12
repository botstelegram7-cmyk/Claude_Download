"""
Serena Bot - Auto Reactions
Reference: Multi-token reaction bot approach
- Uses setMessageReaction API directly with is_big=True (animated)
- Multiple BOT_TOKENS support (REACTION_TOKENS env var)
- Different emoji sets per message type
- DM popup tips for group messages
"""
import os
import random
import asyncio
import logging
import threading
import time
import requests as _requests

from pyrogram import Client, filters
from pyrogram.enums import ChatType, ChatMemberStatus
from pyrogram.errors import FloodWait, UserIsBlocked, PeerIdInvalid

logger = logging.getLogger("SerenaBot.Reactions")

REACT_CHANCE = 0.70   # 70% chance to react
DM_CHANCE    = 0.35   # 35% chance to DM popup (groups only)

# ── Load extra reaction bot tokens from env ──────────────────────────────
# Format: REACTION_TOKENS=token1,token2,token3
_extra_raw = os.environ.get("REACTION_TOKENS", "")
REACTION_TOKENS: list[str] = [t.strip() for t in _extra_raw.split(",") if t.strip()]

# ── Emoji sets per message type ──────────────────────────────────────────
EMOJI_SETS = {
    "photo":    ["❤️", "🔥", "👍", "👏", "🎉", "🤩", "😍", "✨", "💯", "🌟"],
    "video":    ["🔥", "🎬", "👍", "👏", "🤩", "😎", "💯", "⚡", "🎵", "🚀"],
    "document": ["👍", "✅", "💎", "📥", "🙌", "👌", "🔥", "⚡", "💯", "🤝"],
    "audio":    ["🎵", "🎶", "🔥", "❤️", "🤩", "👏", "✨", "😍", "💯", "🌟"],
    "sticker":  ["😄", "😂", "🤣", "😍", "😎", "🤩", "🎭", "✨", "❤️", "🔥"],
    "text":     ["❤️", "🔥", "👍", "👏", "🎉", "🤔", "😮", "🤝", "💯", "⚡"],
}

# DM popup messages
DM_MESSAGES = [
    "🔥 **Hey!** Try sending me a direct MP4/APK/ZIP link — I'll download it instantly!",
    "⚡ **Tip:** Use `/audio [url]` to get MP3 from any YouTube/TikTok video!",
    "💎 **Hey!** Upgrade to Premium for 50 downloads/day → @TechnicalSerena",
    "🎬 **Tip:** Send a `.txt` file with multiple URLs to bulk download everything at once!",
    "🌟 **Hello!** Use `/info [url]` to preview any video before downloading!",
    "🚀 **Quick tip:** I support YouTube, Instagram, TikTok, Twitter, Facebook & 50+ sites!",
    "🎵 **Did you know?** I can extract audio as MP3 from any supported platform!",
    "💫 **Pro tip:** For large files >2GB, I can upload to GoFile.io automatically!",
    "🤩 **Hey!** Send me a googlevideo.com link for direct YouTube CDN downloads!",
    "👋 **Thanks for using Serena Downloader!** Share with your friends 💙",
]


def _detect_msg_type(message) -> str:
    if getattr(message, "photo", None):     return "photo"
    if getattr(message, "video", None):     return "video"
    if getattr(message, "audio", None):     return "audio"
    if getattr(message, "document", None):  return "document"
    if getattr(message, "sticker", None):   return "sticker"
    return "text"


def _send_reaction_api(bot_token: str, chat_id: int, message_id: int,
                        emoji: str, is_big: bool = True) -> bool:
    """
    Send reaction via raw HTTP — identical to the reference bot approach.
    is_big=True → animated big reaction (Telegram premium feature, works without premium for bots).
    """
    try:
        url  = f"https://api.telegram.org/bot{bot_token}/setMessageReaction"
        data = {
            "chat_id":    chat_id,
            "message_id": message_id,
            "reaction":   [{"type": "emoji", "emoji": emoji}],
            "is_big":     is_big,
        }
        r = _requests.post(url, json=data, timeout=10)
        result = r.json()
        if result.get("ok"):
            return True
        # Retry without is_big if it failed
        if is_big:
            data.pop("is_big", None)
            r2 = _requests.post(url, json=data, timeout=10)
            return r2.json().get("ok", False)
        return False
    except Exception as e:
        logger.debug(f"Reaction API error: {e}")
        return False


def _send_multi_reactions_threaded(chat_id: int, message_id: int,
                                    msg_type: str, main_bot_token: str):
    """
    Run in background thread.
    Main bot always reacts (via Pyrogram we already called send_reaction).
    Extra REACTION_TOKENS send additional reactions using raw HTTP.
    """
    emojis   = EMOJI_SETS.get(msg_type, EMOJI_SETS["text"])
    # Build token list — deduplicate
    tokens   = list(dict.fromkeys(REACTION_TOKENS))   # extras only
    max_bots = min(len(tokens), 7)                    # max 7 extra reactions

    if not tokens:
        return

    selected = random.sample(emojis, min(max_bots, len(emojis)))

    success = 0
    for i in range(max_bots):
        token  = tokens[i]
        emoji  = selected[i] if i < len(selected) else "❤️"
        is_big = (i < 3)   # first 3 → big animated reactions

        if _send_reaction_api(token, chat_id, message_id, emoji, is_big):
            success += 1
            logger.debug(f"Extra reaction {'BIG' if is_big else 'normal'} {emoji} ✅")

        time.sleep(random.uniform(0.4, 1.2))   # natural delay

    logger.debug(f"Extra reactions done: {success}/{max_bots}")


async def _can_react(client: Client, chat_id: int) -> bool:
    try:
        from pyrogram.enums import ChatType
        chat = await client.get_chat(chat_id)
        if chat.type == ChatType.PRIVATE:
            return True
        me     = await client.get_me()
        member = await client.get_chat_member(chat_id, me.id)
        return member.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except Exception:
        return False


async def _send_dm_popup(client: Client, user_id: int):
    try:
        msg = random.choice(DM_MESSAGES)
        await client.send_message(user_id, msg)
        logger.debug(f"DM popup → {user_id}")
    except (UserIsBlocked, PeerIdInvalid):
        pass
    except FloodWait as e:
        await asyncio.sleep(e.value + 1)
    except Exception as e:
        logger.debug(f"DM popup error (ignored): {e}")


@Client.on_message(~filters.outgoing, group=99)
async def auto_react(client: Client, message):
    """
    1. Main bot reacts via Pyrogram send_reaction (emoji based on msg type)
    2. Extra REACTION_TOKENS react via raw HTTP in a background thread (is_big=True)
    3. 35% chance to DM popup in groups
    """
    try:
        if not message.from_user:
            return
        if not (message.text or message.photo or message.video or
                message.document or message.audio or message.sticker):
            return
        if random.random() > REACT_CHANCE:
            return
        if not await _can_react(client, message.chat.id):
            return

        msg_type = _detect_msg_type(message)
        emojis   = EMOJI_SETS.get(msg_type, EMOJI_SETS["text"])

        await asyncio.sleep(random.uniform(1.0, 3.5))

        # ── Main bot reaction via Pyrogram ──
        main_emoji = random.choice(emojis)
        try:
            await client.send_reaction(
                chat_id=message.chat.id,
                message_id=message.id,
                emoji=main_emoji,
                big=True,        # animated big reaction
            )
            logger.debug(f"Main reaction BIG {main_emoji} on {message.id}")
        except Exception as e:
            logger.debug(f"Main reaction failed: {e}")

        # ── Extra tokens react in background thread ──
        if REACTION_TOKENS:
            main_token = client.bot_token if hasattr(client, "bot_token") else ""
            t = threading.Thread(
                target=_send_multi_reactions_threaded,
                args=(message.chat.id, message.id, msg_type, main_token),
                daemon=True,
            )
            t.start()

        # ── DM popup (groups only) ──
        if (message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)
                and random.random() < DM_CHANCE):
            await asyncio.sleep(random.uniform(2.0, 5.0))
            await _send_dm_popup(client, message.from_user.id)

    except FloodWait as e:
        await asyncio.sleep(e.value + 2)
    except Exception as e:
        logger.debug(f"auto_react error (ignored): {e}")
