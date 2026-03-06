"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Client       ║
╚══════════════════════════════════════════╝
"""

import os
import sys

# ── Ensure project root is on sys.path BEFORE Pyrogram loads plugins ──
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

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
