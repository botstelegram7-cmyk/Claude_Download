"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║        ⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆           ║
║                                                      ║
║        @Universal_DownloadBot                        ║
║        Owner: @Xioqui_Xan                            ║
║        Support: @TechnicalSerena                     ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import sys
import threading

# ── CRITICAL: Add project root to sys.path so plugins can resolve
#    utils.*, database, config, etc. when loaded by Pyrogram.
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)

# ── Setup logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SerenaBot")

# ── Ensure runtime dirs exist ──
for _d in ["/tmp/serena_db", "/tmp/serena_dl"]:
    os.makedirs(_d, exist_ok=True)

# ── Config ──
from config import BOT_TOKEN, API_ID, API_HASH, PORT


def validate_config():
    errors = []
    if not BOT_TOKEN:
        errors.append("BOT_TOKEN is not set")
    if not API_ID:
        errors.append("API_ID is not set")
    if not API_HASH:
        errors.append("API_HASH is not set")
    if errors:
        for e in errors:
            logger.error(f"❌ Config error: {e}")
        sys.exit(1)


async def main():
    validate_config()

    # ── Init DB ──
    import database as db
    await db.init_db()
    logger.info("✅ Database initialized")

    # ── Start Flask web server in background thread ──
    from web.app import run_web
    web_thread = threading.Thread(target=run_web, daemon=True, name="WebServer")
    web_thread.start()
    logger.info(f"✅ Web server starting on port {PORT}")

    # ── Import client (Pyrogram will load plugins/ via plugins= param) ──
    from client import app
    from queue_manager import queue_manager

    # ── Start queue worker ──
    queue_manager.start()
    logger.info("✅ Queue manager started")

    # ── Start bot ──
    logger.info("🚀 Starting Serena Downloader Bot...")
    await app.start()

    me = await app.get_me()
    logger.info(
        f"\n"
        f"  ⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆\n"
        f"  Bot     : @{me.username}\n"
        f"  ID      : {me.id}\n"
        f"  Owner   : @Xioqui_Xan\n"
        f"  Support : @TechnicalSerena\n"
        f"  Status  : 🟢 Online\n"
    )

    # ── Keep alive ──
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Shutting down...")
    finally:
        await app.stop()
        logger.info("👋 Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
