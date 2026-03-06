"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Web Server   ║
╚══════════════════════════════════════════╝
"""

import os
from flask import Flask, jsonify

web_app = Flask(__name__)


@web_app.route("/health", methods=["GET", "HEAD"])
def health():
    return jsonify({"status": "ok", "bot": "Serena Downloader Bot"}), 200


@web_app.route("/", methods=["GET", "HEAD"])
def index():
    return jsonify({
        "name": "Serena Downloader Bot",
        "username": "@Universal_DownloadBot",
        "status": "running",
        "owner": "@Xioqui_Xan",
        "support": "@TechnicalSerena"
    }), 200


def run_web():
    port = int(os.environ.get("PORT", "10000"))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
