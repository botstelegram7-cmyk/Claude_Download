"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Client       ║
╚══════════════════════════════════════════╝
"""

from pyrogram import Client
from config import BOT_TOKEN, API_ID, API_HASH

app = Client(
    name="SerenaBot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH,
    in_memory=True,
    plugins=dict(root="plugins"),
)
