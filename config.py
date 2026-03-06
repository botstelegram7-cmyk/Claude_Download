"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Config       ║
║     @Universal_DownloadBot               ║
╚══════════════════════════════════════════╝
"""

import os
from typing import List

# ──────────────── Bot Credentials ────────────────
BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
API_ID: int = int(os.environ.get("API_ID", "0"))
API_HASH: str = os.environ.get("API_HASH", "")

# ──────────────── Owner / Support ────────────────
OWNER_IDS: List[int] = [
    int(x.strip())
    for x in os.environ.get("OWNER_IDS", "1598576202").split(",")
    if x.strip().isdigit()
]
OWNER_USERNAME: str = os.environ.get("OWNER_USERNAME", "Xioqui_Xan")
SUPPORT_USERNAME: str = os.environ.get("SUPPORT_USERNAME", "TechnicalSerena")

# ──────────────── Download Limits ────────────────
FREE_LIMIT: int = int(os.environ.get("FREE_LIMIT", "3"))
BASIC_LIMIT: int = int(os.environ.get("BASIC_LIMIT", "15"))
PREMIUM_LIMIT: int = int(os.environ.get("PREMIUM_LIMIT", "50"))

# ──────────────── Paths ────────────────
DB_PATH: str = os.environ.get("DB_PATH", "/tmp/serena_db/bot.db")
DL_DIR: str = os.environ.get("DL_DIR", "/tmp/serena_dl")

# ──────────────── Cookies ────────────────
YT_COOKIES: str = os.environ.get("YT_COOKIES", "")
INSTAGRAM_COOKIES: str = os.environ.get("INSTAGRAM_COOKIES", "")
TERABOX_COOKIES: str = os.environ.get("TERABOX_COOKIES", "")

# ──────────────── Web Server ────────────────
PORT: int = int(os.environ.get("PORT", "8080"))

# ──────────────── Plan Names ────────────────
PLANS = {
    "free":    {"name": "Free 🆓",    "limit": FREE_LIMIT,    "days": 0},
    "basic":   {"name": "Basic 🥉",   "limit": BASIC_LIMIT,   "days": 30},
    "premium": {"name": "Premium 💎", "limit": PREMIUM_LIMIT, "days": 365},
    "owner":   {"name": "Owner 👑",   "limit": 999999,        "days": 0},
}

# ──────────────── Branding ────────────────
BOT_NAME = "Serena Downloader Bot"
BOT_USERNAME = "Universal_DownloadBot"

HEADER = "⋆｡° ✮ °｡⋆"
DIVIDER = "»»──── ✦ ────««"
FOOTER = "⋆ ｡˚ ˚｡ ⋆"
BULLET = "▸"

# ──────────────── Supported Platforms ────────────────
SUPPORTED_PLATFORMS = [
    "YouTube", "Instagram", "TikTok", "Twitter/X",
    "Facebook", "Google Drive", "Terabox",
    "M3U8 Streams", "Direct Links"
]

# ──────────────── Reactions ────────────────
REACTION_EMOJIS = [
    "🔥", "❤️", "👍", "🎉", "😍", "🤩", "💯", "⚡",
    "🌟", "✨", "🎵", "🎬", "📥", "💎", "🚀", "👏",
    "😎", "🤙", "💪", "🙌"
]
