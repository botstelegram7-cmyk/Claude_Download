<div align="center">

```
╔══════════════════════════════════════════════════════╗
║                                                      ║
║        ⋆｡° ✮  Serena Downloader Bot  ✮ °｡⋆          ║
║                                                      ║
║        @Universal_DownloadBot                        ║
║        Owner  : @Xioqui_Xan                         ║
║        Support: @TechnicalSerena                     ║
║                                                      ║
╚══════════════════════════════════════════════════════╝
```

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Pyrogram](https://img.shields.io/badge/Pyrogram-2.0-green?style=for-the-badge)
![yt-dlp](https://img.shields.io/badge/yt--dlp-Latest-red?style=for-the-badge)
![Render](https://img.shields.io/badge/Deploy-Render-purple?style=for-the-badge&logo=render)
![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)

**A powerful, all-in-one Telegram media downloader bot supporting 50+ platforms.**

[Features](#-features) • [Deploy](#-deploy-on-render) • [Commands](#-commands) • [Config](#-environment-variables) • [Support](#-support)

</div>

---

## ✨ Features

| Feature | Details |
|---|---|
| 🎬 **YouTube** | Dynamic quality selector (fetches actual available qualities) |
| 📸 **Instagram** | Reels, Posts, Stories |
| 🎵 **TikTok** | Videos, Slideshows |
| 🐦 **Twitter/X** | Videos, GIFs |
| 👥 **Facebook** | Videos, Reels |
| 📁 **Google Drive** | Files + Folders (ZIP or Individual) |
| ☁️ **Terabox** | Videos, Files |
| 📡 **M3U8 Streams** | Encrypted + plain HLS streams |
| 🔗 **Direct Links** | Any direct MP4, APK, ZIP, audio, image URL |
| 🎞️ **googlevideo.com** | YouTube CDN direct links |
| 🌐 **50+ Sites** | Reddit, Vimeo, Twitch, Dailymotion, SoundCloud, Pinterest & more |

### 🚀 Smart Features

- **📊 Live Progress Bar** — Real-time download & upload progress with speed, ETA, network quality
- **🖼️ Auto Thumbnail** — Fetches original thumbnail from source, generates from video if unavailable
- **📦 Large File Handler** — Files >2GB: choose Split Parts / GoFile.io / Force Telegram
- **☁️ GoFile.io Upload** — Automatically uploads huge files and returns a share link
- **✂️ File Splitting** — Splits large files into 1.9GB Telegram-safe parts
- **📋 Queue System** — True sequential queue (1st finishes → 2nd starts)
- **🌍 Geo-Bypass** — Auto bypasses country restrictions for YouTube
- **😴 Anti-Sleep** — Self-ping keep-alive to prevent Render free tier from sleeping
- **💬 Auto Reactions** — Reacts to messages + random DM popup tips
- **📄 Bulk Download** — Upload a `.txt` file with multiple URLs to queue them all
- **👑 Plans System** — Free / Basic / Premium / Owner with daily limits

---

## 📦 Requirements

- Python `3.10+`
- `ffmpeg` (for video remux, thumbnail generation, M3U8)
- Telegram API ID & Hash → [my.telegram.org](https://my.telegram.org)
- Bot Token → [@BotFather](https://t.me/BotFather)

**Python packages** (see `requirements.txt`):
```
Pyrogram==2.0.106
TgCrypto==1.2.5
yt-dlp>=2025.1.1
aiohttp>=3.9.0
aiosqlite>=0.19.0
Pillow>=10.0.0
Flask>=3.0.0
requests>=2.31.0
```

---

## 🚀 Deploy on Render

### One-Click Deploy

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

### Manual Steps

1. **Fork / Clone** this repo
2. Go to [render.com](https://render.com) → **New Web Service**
3. Connect your GitHub repo
4. Set runtime to **Docker**
5. Add all **Environment Variables** (see below)
6. Set **Health Check Path** → `/health`
7. Click **Deploy!**

> ✅ The bot self-pings every 4 minutes to stay awake on Render free tier.  
> ✅ UptimeRobot on both `HEAD /` and `GET /health` is also recommended.

---

## ⚙️ Environment Variables

### Required

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash from my.telegram.org |
| `OWNER_IDS` | Your Telegram user ID (comma-separated for multiple) |

### Optional

| Variable | Default | Description |
|---|---|---|
| `OWNER_USERNAME` | `Xioqui_xin` | Owner's Telegram username |
| `SUPPORT_USERNAME` | `TechnicalSerena` | Support username |
| `FREE_LIMIT` | `3` | Daily downloads for free users |
| `BASIC_LIMIT` | `15` | Daily downloads for basic users |
| `PREMIUM_LIMIT` | `50` | Daily downloads for premium users |
| `QUEUE_DELAY` | `2.0` | Seconds between queued jobs |
| `PORT` | `10000` | Web server port |
| `DB_PATH` | `/tmp/serena_db/bot.db` | SQLite DB path |
| `DL_DIR` | `/tmp/serena_dl` | Temp download directory |

### Cookies (Highly Recommended)

> Cookies allow downloading age-restricted, private or geo-blocked content.  
> Export from your browser using the **"Get cookies.txt LOCALLY"** extension.

| Variable | Description |
|---|---|
| `YT_COOKIES` | YouTube cookies (Netscape format) — for age-restricted/geo videos |
| `INSTAGRAM_COOKIES` | Instagram cookies — for private profiles |
| `TERABOX_COOKIES` | Terabox cookies — for private files |

### Proxy (Optional)

| Variable | Description |
|---|---|
| `YT_PROXY` | HTTP proxy for YouTube — e.g. `http://user:pass@proxy.webshare.io:80` |

### GoFile.io (Optional — for files >2GB)

| Variable | Description |
|---|---|
| `GOFILE_TOKEN` | Your GoFile account token |
| `GOFILE_ACCOUNT_ID` | Your GoFile account ID |

> Get your token at [gofile.io](https://gofile.io) → Account Settings

---

## 📋 Commands

| Command | Description |
|---|---|
| `/start` | Start the bot & register |
| `/help` | Show help message |
| `/ping` | Check bot status & latency |
| `/info [url]` | Get media info before downloading |
| `/audio [url]` | Extract audio as MP3 |
| `/mystats` | View your download stats |
| `/history` | Your recent downloads |
| `/plans` | View available plans |
| `/status` | Bot status & queue info |
| `/cancel` | Cancel pending URL |
| `/feedback [msg]` | Send feedback to owner |
| `/cookies` | Check cookie status (owner) |
| `/formats` | Supported platforms list |

### Admin Commands

| Command | Description |
|---|---|
| `/givepremium [id] [days]` | Grant premium to user |
| `/removepremium [id]` | Remove premium |
| `/ban [id]` | Ban a user |
| `/unban [id]` | Unban a user |
| `/broadcast [msg]` | Send message to all users |
| `/stats` | Full bot statistics |
| `/users` | List recent users |
| `/lock` | Lock bot (maintenance mode) |
| `/unlock` | Unlock bot |
| `/restart` | Restart the bot |

---

## 📥 How to Use

### Download a Video
Just send any supported URL — the bot auto-detects the platform:
```
https://youtu.be/dQw4w9WgXcQ
```
For YouTube, a quality selector pops up showing **only actually available qualities**.

### Audio Only
```
/audio https://youtu.be/dQw4w9WgXcQ
```

### Bulk Download
Upload a `.txt` file containing one URL per line:
```
https://youtu.be/abc123
https://www.instagram.com/p/xyz/
https://vm.tiktok.com/abc/
```

### Direct Links
Any direct download link (MP4, APK, ZIP, MP3, images) works automatically:
```
https://example.com/video.mp4
https://example.com/app.apk
https://rr2---sn-xxx.googlevideo.com/videoplayback?...
```

---

## 📊 Progress Bar

Downloads and uploads show a live progress bar:

```
➵⋆🪐ᴛᴇᴄʜɴɪᴄᴀʟ_sᴇʀᴇɴᴀ𓂃
📄 Kung Fu Hustle Best Scenes
↔️ to Telegram
[●●●●●●●●○○○○○○○○○○○○]
◌ Progress 😉 : 〘 40.0% 〙
✅ Done       : 〘 220.88 MB of 552.19 MB 〙
🚀 Speed      : 〘 3.98 MB/s 〙
⏳ ETA        : 〘 2m 7s 〙
📶 Network    : 📶 Fast
```

---

## 📁 Project Structure

```
SerenaBot/
├── bot.py                  # Main entry point
├── client.py               # Pyrogram client setup
├── config.py               # All configuration & env vars
├── database.py             # SQLite async DB (aiosqlite)
├── queue_manager.py        # Sequential download queue
├── main.py                 # Alternative entry (gunicorn)
├── render.yaml             # Render.com deployment config
├── Dockerfile              # Docker image
├── requirements.txt        # Python dependencies
│
├── plugins/
│   ├── download.py         # URL handler, quality selector, callbacks
│   ├── start.py            # /start, /help, /ping, /plans
│   ├── admin.py            # Admin commands
│   └── reactions.py        # Auto reactions + DM popup
│
├── downloader/
│   ├── core.py             # yt-dlp, direct download, M3U8, Terabox
│   └── media.py            # Upload pipeline, large file handler
│
├── utils/
│   ├── progress.py         # Fancy live progress bar
│   ├── helpers.py          # URL detection, formatters
│   ├── decorators.py       # @not_banned, @ensure_registered
│   └── gofile.py           # GoFile.io uploader
│
└── web/
    └── app.py              # Flask health server + keep-alive self-ping
```

---

## 🛠️ Local Development

```bash
# Clone
git clone https://github.com/youruser/serena-bot
cd serena-bot

# Install dependencies
pip install -r requirements.txt

# Install ffmpeg (Ubuntu/Debian)
sudo apt install ffmpeg -y

# Set environment variables
export BOT_TOKEN="your_token"
export API_ID="your_api_id"
export API_HASH="your_api_hash"
export OWNER_IDS="your_user_id"

# Run
python bot.py
```

### Docker

```bash
docker build -t serena-bot .
docker run -e BOT_TOKEN=xxx -e API_ID=xxx -e API_HASH=xxx serena-bot
```

---

## 📐 Plans

| Plan | Daily Limit | Duration |
|---|---|---|
| 🆓 Free | 3 downloads/day | Forever |
| 🥉 Basic | 15 downloads/day | 30 days |
| 💎 Premium | 50 downloads/day | 365 days |
| 👑 Owner | Unlimited | Forever |

> Contact [@TechnicalSerena](https://t.me/TechnicalSerena) to purchase plans.

---

## ❓ FAQ

**Q: Bot is sleeping on Render?**  
A: Add UptimeRobot monitoring on both `GET /` and `HEAD /health`. Bot also self-pings every 4 minutes internally.

**Q: YouTube videos not downloading?**  
A: Set `YT_COOKIES` with fresh cookies exported from a logged-in browser. Also try setting `YT_PROXY`.

**Q: File too large (>2GB)?**  
A: Bot will automatically ask you whether to Split Parts, Upload to GoFile.io, or force to Telegram.

**Q: How to export cookies?**  
A: Install "Get cookies.txt LOCALLY" browser extension → Go to YouTube while logged in → Export → Paste the contents as `YT_COOKIES` env variable.

**Q: How to add more owners?**  
A: Set `OWNER_IDS=123456789,987654321` (comma-separated user IDs).

---

## 📞 Support

- **Bot:** [@Universal_DownloadBot](https://t.me/Universal_DownloadBot)
- **Owner:** [@Xioqui_Xan](https://t.me/Xioqui_Xan)
- **Support:** [@TechnicalSerena](https://t.me/TechnicalSerena)
- **Channel:** [@TechnicalSerena](https://t.me/TechnicalSerena)

---

## 📄 License

```
MIT License — Free to use, modify and distribute.
Give credit to @TechnicalSerena if you use this code. 💙
```

---

<div align="center">

**Made with 💙 by [@TechnicalSerena](https://t.me/TechnicalSerena)**

⋆｡° ✮ Serena Downloader Bot ✮ °｡⋆

</div>
