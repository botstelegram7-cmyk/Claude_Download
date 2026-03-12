import os
from typing import List

BOT_TOKEN: str = os.environ.get("BOT_TOKEN", "")
API_ID: int = int(os.environ.get("API_ID", "0"))
API_HASH: str = os.environ.get("API_HASH", "")

OWNER_IDS: List[int] = [
    int(x.strip()) for x in os.environ.get("OWNER_IDS", "1598576202").split(",")
    if x.strip().isdigit()
]
OWNER_USERNAME: str  = os.environ.get("OWNER_USERNAME",  "Xioqui_xin")
SUPPORT_USERNAME: str = os.environ.get("SUPPORT_USERNAME", "TechnicalSerena")
SUPPORT_CHANNEL: str  = os.environ.get("SUPPORT_CHANNEL",  "TechnicalSerena")   # channel username
FORCE_SUB_CHANNEL: str = os.environ.get("FORCE_SUB_CHANNEL", "serenaunzipbot")

FREE_LIMIT: int    = int(os.environ.get("FREE_LIMIT",    "3"))
BASIC_LIMIT: int   = int(os.environ.get("BASIC_LIMIT",   "15"))
PREMIUM_LIMIT: int = int(os.environ.get("PREMIUM_LIMIT", "50"))

DB_PATH: str = os.environ.get("DB_PATH", "/tmp/serena_db/bot.db")
DL_DIR: str  = os.environ.get("DL_DIR",  "/tmp/serena_dl")

YT_COOKIES: str        = os.environ.get("YT_COOKIES", "")
INSTAGRAM_COOKIES: str = os.environ.get("INSTAGRAM_COOKIES", "")
TERABOX_COOKIES: str   = os.environ.get("TERABOX_COOKIES", "")

# Webshare rotating proxy — http://user-rotate:pass@p.webshare.io:80
YT_PROXY: str = os.environ.get("YT_PROXY", "")

PORT: int = int(os.environ.get("PORT", "10000"))

PLANS = {
    "free":    {"name": "Free 🆓",    "limit": FREE_LIMIT,    "days": 0},
    "basic":   {"name": "Basic 🥉",   "limit": BASIC_LIMIT,   "days": 30},
    "premium": {"name": "Premium 💎", "limit": PREMIUM_LIMIT, "days": 365},
    "owner":   {"name": "Owner 👑",   "limit": 999999,        "days": 0},
}

BOT_NAME     = "Serena Downloader"
BOT_USERNAME = "SerenaXDownloader_bot"

# Queue delay between jobs (seconds)
QUEUE_DELAY: float = float(os.environ.get("QUEUE_DELAY", "2.0"))

REACTION_EMOJIS = [
    "🔥","❤️","👍","🎉","😍","🤩","💯","⚡",
    "🌟","✨","🎵","🎬","📥","💎","🚀","👏",
    "😎","🤙","💪","🙌","🫡","🥰","😘","🎶",
]

BOT_LOCK: bool = False

# GoFile settings (optional — for large file uploads > 2 GB)
GOFILE_TOKEN: str      = os.environ.get("GOFILE_TOKEN", "")
GOFILE_ACCOUNT_ID: str = os.environ.get("GOFILE_ACCOUNT_ID", "")

# Max Telegram upload size (bytes). Telegram MTProto limit = 2 GB.
# Files above this threshold ask user: Split / GoFile / Direct Telegram.
TG_MAX_SIZE: int = int(os.environ.get("TG_MAX_SIZE", str(2 * 1024 * 1024 * 1024)))  # 2 GB default

# Extra bot tokens for multi-reaction (comma-separated)
# e.g. REACTION_TOKENS=token1,token2,token3
REACTION_TOKENS: str = os.environ.get("REACTION_TOKENS", "")
