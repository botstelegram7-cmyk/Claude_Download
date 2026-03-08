# ⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆

> **@Universal_DownloadBot** — A production-ready Telegram media downloader bot

»»──── ✦ ────««

## Overview

Serena Downloader Bot is a fully-featured Telegram bot that downloads media from virtually any platform, built with Python 3.11, Pyrogram, and yt-dlp.

## ✨ Features

- **Multi-Platform Downloads** — YouTube, Instagram, TikTok, Twitter/X, Facebook, Google Drive, Terabox, M3U8, Direct links
- **Quality Selector** — 144p / 360p / 720p / 1080p / Audio Only / Best
- **Async Queue System** — Per-user download queue with real-time progress
- **Subscription Plans** — Free / Basic / Premium / Owner tiers
- **Bulk Downloads** — Send a `.txt` file with multiple URLs
- **Auto Reactions** — Bot randomly reacts to messages with emojis
- **Cookies Support** — YouTube, Instagram, Terabox cookies via env vars
- **Admin Panel** — Full admin command suite
- **Render.com Ready** — Deploy with one click

## 🚀 Deployment

### Prerequisites
- Python 3.11+
- FFmpeg installed
- Telegram Bot Token from [@BotFather](https://t.me/BotFather)
- Telegram API credentials from [my.telegram.org](https://my.telegram.org)

### Local Setup

```bash
# 1. Clone / unzip the project
cd serena_bot

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 4. Run the bot
python bot.py
```

### Docker

```bash
docker build -t serena-bot .
docker run --env-file .env serena-bot
```

### Render.com

1. Push this project to a GitHub repository
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your repo
4. Set environment variables (BOT_TOKEN, API_ID, API_HASH)
5. Deploy!

The `render.yaml` file handles all configuration automatically.

## ⚙️ Environment Variables

| Variable | Required | Description |
|---|---|---|
| `BOT_TOKEN` | ✅ | Your Telegram bot token |
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API hash |
| `OWNER_IDS` | ✅ | Comma-separated owner Telegram IDs |
| `FREE_LIMIT` | — | Daily downloads for free users (default: 3) |
| `BASIC_LIMIT` | — | Daily downloads for basic users (default: 15) |
| `PREMIUM_LIMIT` | — | Daily downloads for premium users (default: 50) |
| `YT_COOKIES` | — | YouTube cookies in Netscape format |
| `INSTAGRAM_COOKIES` | — | Instagram cookies in Netscape format |
| `TERABOX_COOKIES` | — | Terabox cookies in Netscape format |
| `PORT` | — | Web server port (default: 8080) |

## 📋 Commands

### User Commands
| Command | Description |
|---|---|
| `/start` | Welcome message |
| `/help` | Help guide |
| `/ping` | Check bot latency |
| `/status` | Bot status |
| `/plans` | Subscription plans |
| `/mystats` | Your download stats |
| `/history` | Recent downloads |
| `/settings` | Bot settings |
| `/audio [url]` | Extract audio |
| `/info [url]` | Media information |
| `/queue` | View queue status |
| `/cancel` | Cancel pending selection |
| `/feedback [text]` | Send feedback |

### Admin Commands (Owner only)
| Command | Description |
|---|---|
| `/givepremium <id> <plan>` | Grant premium plan |
| `/removepremium <id>` | Remove premium plan |
| `/ban <id>` | Ban a user |
| `/unban <id>` | Unban a user |
| `/broadcast <message>` | Broadcast to all users |
| `/stats` | Bot statistics |
| `/users` | List all users |
| `/banned` | List banned users |
| `/restart` | Restart the bot |

## 🍪 Cookie Setup

To use age-restricted or region-locked content:

1. Install a browser extension like "Get cookies.txt LOCALLY"
2. Visit YouTube/Instagram while logged in
3. Export cookies in **Netscape format**
4. Paste the entire content as the `YT_COOKIES` environment variable on Render

## 📁 Project Structure

```
serena_bot/
├── bot.py              # Main entry point
├── client.py           # Pyrogram client
├── config.py           # Configuration
├── database.py         # SQLite database layer
├── queue_manager.py    # Async download queue
├── plugins/
│   ├── start.py        # User commands
│   ├── download.py     # Download handler
│   ├── admin.py        # Admin commands
│   └── reactions.py    # Auto emoji reactions
├── downloader/
│   ├── core.py         # yt-dlp / ffmpeg core
│   └── media.py        # Upload pipeline
├── utils/
│   ├── helpers.py      # Utility functions
│   ├── progress.py     # Progress tracking
│   └── decorators.py   # Auth decorators
├── web/
│   └── app.py          # Flask health server
├── Dockerfile
├── render.yaml
├── requirements.txt
├── .env.example
└── sample_urls.txt
```

## 👤 Credits

- **Owner:** @Xioqui_Xan
- **Support:** @TechnicalSerena
- **Bot:** @Universal_DownloadBot

»»──── ✦ ────««

⋆ ｡˚ Made with ❤️ ˚｡ ⋆
