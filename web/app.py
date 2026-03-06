"""
╔══════════════════════════════════════════╗
║     Serena Downloader Bot - Web Server   ║
╚══════════════════════════════════════════╝
"""

from flask import Flask, jsonify
from config import PORT

web_app = Flask(__name__)


@web_app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "bot": "Serena Downloader Bot"}), 200


@web_app.route("/", methods=["GET"])
def index():
    return jsonify({
        "name": "Serena Downloader Bot",
        "username": "@Universal_DownloadBot",
        "status": "running",
        "owner": "@Xioqui_Xan",
        "support": "@TechnicalSerena"
    }), 200


def run_web():
    web_app.run(host="0.0.0.0", port=PORT, debug=False)
