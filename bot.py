"""
╔══════════════════════════════════════════════════════╗
║                                                      ║
║         ⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆          ║
║                                                      ║
║         @Universal_DownloadBot                       ║
║         Owner: @Xioqui_Xan                           ║
║         Support: @TechnicalSerena                    ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
"""

import asyncio
import logging
import os
import sys
import threading

# ── Setup logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("SerenaBot")

# ── Ensure required dirs ──
for d in ["/tmp/serena_db", "/tmp/serena_dl"]:
    os.makedirs(d, exist_ok=True)

# ── Import config first ──
from config import BOT_TOKEN, API_ID, API_HASH, DL_DIR, DB_PATH, PORT


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

    # ── Import client (plugins loaded via Client plugins= param) ──
    from client import app
    from queue_manager import queue_manager

    # ── Start queue worker ──
    queue_manager.start()
    logger.info("✅ Queue manager started")

    # ── Start Flask web server in background thread ──
    from web.app import run_web
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    logger.info(f"✅ Web server started on port {PORT}")

    # ── Start bot ──
    logger.info("🚀 Starting Serena Downloader Bot...")
    await app.start()

    me = await app.get_me()
    logger.info(
        f"\n"
        f"╔══════════════════════════════════════╗\n"
        f"║  ⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆ ║\n"
        f"╠══════════════════════════════════════╣\n"
        f"║  Bot: @{me.username:<29} ║\n"
        f"║  ID: {me.id:<31} ║\n"
        f"║  Owner: @Xioqui_Xan                  ║\n"
        f"║  Support: @TechnicalSerena            ║\n"
        f"╚══════════════════════════════════════╝\n"
    )

    logger.info("✅ Bot is running! Press Ctrl+C to stop.")

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
