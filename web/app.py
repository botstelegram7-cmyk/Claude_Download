"""
Serena Bot - Web Server
Keep-alive: bot pings itself every 4 minutes to prevent Render sleep
"""
import os
import threading
import time
import logging

from flask import Flask, jsonify

logger  = logging.getLogger("SerenaBot.Web")
web_app = Flask(__name__)


@web_app.route("/health", methods=["GET", "HEAD"])
def health():
    return jsonify({"status": "ok", "bot": "Serena Downloader Bot"}), 200


@web_app.route("/", methods=["GET", "HEAD"])
def index():
    return jsonify({
        "name":     "Serena Downloader Bot",
        "username": "@Universal_DownloadBot",
        "status":   "running",
        "owner":    "@Xioqui_Xan",
        "support":  "@TechnicalSerena",
    }), 200


@web_app.route("/ping", methods=["GET", "HEAD"])
def ping():
    return jsonify({"pong": True, "ts": int(time.time())}), 200


def _self_ping_loop(port: int):
    """
    Pings our own /ping endpoint every 4 minutes.
    This prevents Render (free tier) from putting the service to sleep.
    """
    import urllib.request
    time.sleep(60)          # wait for server to start first
    url = f"http://127.0.0.1:{port}/ping"
    while True:
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                logger.debug(f"Self-ping OK ({r.status})")
        except Exception as e:
            logger.debug(f"Self-ping failed: {e}")
        time.sleep(240)     # every 4 minutes


def run_web():
    port = int(os.environ.get("PORT", "10000"))

    # Start self-ping keep-alive thread
    t = threading.Thread(
        target=_self_ping_loop,
        args=(port,),
        daemon=True,
        name="KeepAlive",
    )
    t.start()

    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
