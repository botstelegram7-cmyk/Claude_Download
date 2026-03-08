# 🤖 Nexora PDF Doctor Bot v3.0

A powerful all-in-one Telegram PDF toolkit with 30+ features.

## 🆕 What's New in v3.0

### New Features
| Command | Feature | Plan |
|---------|---------|------|
| `/pdf2word` | PDF → Editable DOCX | 🥈 Basic |
| `/pdf2ppt` | PDF → PowerPoint Slides | 🥇 Pro |
| `/crop` | Auto-crop white margins | ✅ Free |
| `/qr` | QR Code Generator | ✅ Free |
| `/delete_pages` | Delete specific pages | ✅ Free (5 pages max) / 🥇 Pro |
| `/reorder` | Reorder pages (e.g., 3,1,2) | ✅ Free |
| `/lang` | Change bot language | ✅ Free |

### Improvements
- ✅ **OCR now asks language** before extraction (English, Hindi, Spanish, French, Korean, etc.)
- ✅ **6 Bot Languages**: English, Hindi, Bhojpuri, Spanish, French, Korean
- ✅ **14 Handwriting Fonts** (6 new added)
- ✅ **8 Notebook Styles**: Blue Lines, Yellow Legal, Graph, Dotted, Parchment, Dark, Pink Diary, Chalkboard
- ✅ **Fixed Handwriting Alignment**: Text now sits perfectly ON the ruled lines

## 📋 All Features

### 📄 PDF Tools
- `/compress` - Compress PDF (multi-strategy)
- `/split` - Split into individual pages
- `/merge` - Merge multiple PDFs
- `/repair` - Fix corrupted PDFs

### 🔐 Security
- `/lock` - Password protect PDF
- `/unlock` - Remove PDF password

### 🎨 Visual
- `/watermark` - Text/Logo/Invisible watermark
- `/darkmode` - Dark mode conversion
- `/bgchange` - Background color changer (8 themes)

### 🔄 Convert
- `/pdf2img` - PDF to PNG images
- `/img2pdf` - Images to PDF
- `/excel` - PDF to Excel
- `/pdf2word` - PDF to Word DOCX ✨
- `/pdf2ppt` - PDF to PowerPoint ✨

### ✨ Creative
- `/handwrite` - Handwritten PDF (14 fonts, 8 notebook styles)
- `/addtext` - Add text to PDF
- `/footer` - Add footer to all pages
- `/pagenos` - Add page numbers
- `/crop` - Crop white margins ✨
- `/qr` - QR Code generator ✨

### 🔍 Extract & Pages
- `/ocr` - OCR with language selection (10 languages)
- `/extract` - Extract page range
- `/delete_pages` - Delete pages ✨
- `/reorder` - Reorder pages ✨
- `/metadata` - View PDF metadata

### ⚙️ Tools
- `/rotate` - Rotate (90°, 180°, Auto-fix)
- `/resize` - Resize to A4

### 🌍 Languages
- `/lang` - English, Hindi, Bhojpuri, Spanish, French, Korean ✨

## 🚀 Setup

```bash
# Clone and install
pip install -r requirements.txt

# Set environment variables
BOT_TOKEN=your_bot_token
OWNER_ID=your_telegram_id
UPI_ID=your_upi_id  # optional
MONGODB_URL=your_mongodb_url  # optional, uses SQLite if empty

# Run
python main.py
```

## 🐳 Docker

```bash
docker-compose up -d
```

## 💎 Plans

| Feature | Free | Basic (₹99/mo) | Pro (₹249/yr) |
|---------|------|----------------|----------------|
| Daily operations | 3 | 50 | Unlimited |
| PDF → Word | ✅ | ✅ | ✅ |
| PDF → PPT | ❌ | ❌ | ✅ |
| Delete pages | 5 max | 20 max | Unlimited |
| OCR languages | 3 | All | All |
