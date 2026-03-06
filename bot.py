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
from config import BOT_TOKEN, API_ID, API_HASH


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


async def start_bot_with_retry(app):
    """
    Attempt app.start() and handle Telegram's auth FloodWait gracefully.
    Telegram can impose a wait of up to ~40 min on auth.ImportBotAuthorization
    if the bot was restarted/redeployed too many times in quick succession.
    We wait the exact required time then retry automatically — no crash.
    """
    from pyrogram.errors import FloodWait

    attempt = 0
    while True:
        attempt += 1
        try:
            await app.start()
            return  # success
        except FloodWait as e:
            wait_sec = e.value + 5   # add 5s buffer on top of required wait
            wait_min = wait_sec / 60
            logger.warning(
                f"⏳ Telegram auth FloodWait on attempt #{attempt}. "
                f"Required wait: {e.value}s (~{wait_min:.1f} min). "
                f"Sleeping {wait_sec}s then retrying automatically..."
            )
            # Sleep in 30s chunks so logs stay active and web server stays alive
            slept = 0
            chunk = 30
            while slept < wait_sec:
                sleep_now = min(chunk, wait_sec - slept)
                await asyncio.sleep(sleep_now)
                slept += sleep_now
                remaining = wait_sec - slept
                if remaining > 0:
                    logger.info(
                        f"⏳ Auth flood wait: {remaining:.0f}s remaining "
                        f"(~{remaining/60:.1f} min)..."
                    )
            logger.info(f"🔄 Retrying bot.start() (attempt #{attempt + 1})...")
        except Exception as e:
            logger.error(f"❌ Unexpected error during app.start(): {e}")
            raise


async def main():
    validate_config()

    # ── Init DB ──
    import database as db
    await db.init_db()
    logger.info("✅ Database initialized")

    # ── Start Flask web server FIRST so Render health checks pass during
    #    any FloodWait delay (Render kills the service if /health doesn't respond)
    from web.app import run_web
    port = int(os.environ.get("PORT", "10000"))
    web_thread = threading.Thread(target=run_web, daemon=True, name="WebServer")
    web_thread.start()
    logger.info(f"✅ Web server started on port {port}")

    # Small delay to let Flask bind before bot auth starts
    await asyncio.sleep(2)

    # ── Import client + queue ──
    from client import app
    from queue_manager import queue_manager

    # ── Start queue worker ──
    queue_manager.start()
    logger.info("✅ Queue manager started")

    # ── Start bot — with FloodWait retry loop ──
    logger.info("🚀 Starting Serena Downloader Bot...")
    await start_bot_with_retry(app)

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
