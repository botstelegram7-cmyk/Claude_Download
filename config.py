import os
from dotenv import load_dotenv

load_dotenv()

# ─── Core Settings ──────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN", "")
OWNER_ID     = int(os.environ.get("OWNER_ID", "0"))
PORT         = int(os.environ.get("PORT", "8080"))
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "nexora_admin_2024")

# ─── Optional Payment Settings ──────────────────
UPI_ID      = os.environ.get("UPI_ID", "")
UPI_QR_URL  = os.environ.get("UPI_QR_URL", "")

# ─── Optional Start Media ────────────────────────
START_IMAGE = os.environ.get("START_IMAGE", "")

# ─── Optional MongoDB ────────────────────────────
MONGODB_URL = os.environ.get("MONGODB_URL", "")

# ─── Pricing ─────────────────────────────────────
BASIC_PRICE  = "₹99"
PRO_PRICE    = "₹249"
BASIC_LABEL  = "Basic – ₹99/month"
PRO_LABEL    = "Pro – ₹249/year"

# ─── FILE SIZE LIMITS (MB) ───────────────────────
MAX_FILE_SIZE_MB = {
    "free":  20,
    "basic": 50,
    "pro":   100,
}

# ─── Bulk Processing ─────────────────────────────
BULK_MAX_FILES = {
    "free":  0,
    "basic": 10,
    "pro":   25,
}
BULK_QUEUE_TIMEOUT = 120

# ─── Broadcast Rate Limiting ─────────────────────
BROADCAST_DELAY_SEC = 0.35
BROADCAST_BATCH     = 25

# ─── Scheduled Deletion Options ──────────────────
SCHEDULED_DELETION_OPTIONS = {
    "30m":  30 * 60,
    "1h":   60 * 60,
    "3h":   3 * 60 * 60,
    "24h":  24 * 60 * 60,
}

# ─── Per-Feature Rate Limits ─────────────────────
FEATURE_LIMITS = {
    "compress":         {"free": 3,  "basic": 30,   "pro": None},
    "split":            {"free": 2,  "basic": 20,   "pro": None},
    "merge":            {"free": 2,  "basic": 20,   "pro": None},
    "lock":             {"free": 3,  "basic": 30,   "pro": None},
    "unlock":           {"free": 3,  "basic": 30,   "pro": None},
    "repair":           {"free": 2,  "basic": 15,   "pro": None},
    "pdf2txt":          {"free": 5,  "basic": 50,   "pro": None},
    "linearize":        {"free": 3,  "basic": 30,   "pro": None},
    "thumbnail":        {"free": 10, "basic": None,  "pro": None},
    "pdf_info":         {"free": 10, "basic": None,  "pro": None},
    "redact":           {"free": 2,  "basic": 20,   "pro": None},
    "impose":           {"free": 2,  "basic": 20,   "pro": None},
    "deskew":           {"free": 2,  "basic": 20,   "pro": None},
    "bulk":             {"free": 0,  "basic": 5,    "pro": None},
    "pdf_stamp":        {"free": 3,  "basic": 30,   "pro": None},
    "pdf_grayscale":    {"free": 5,  "basic": None,  "pro": None},
    "pdf_extract_imgs": {"free": 2,  "basic": 20,   "pro": None},
    "pdf_remove_meta":  {"free": 5,  "basic": None,  "pro": None},
    "pdf_permissions":  {"free": 0,  "basic": 10,   "pro": None},
    "pdf_bookmark":     {"free": 5,  "basic": None,  "pro": None},
    "pdf_header":       {"free": 3,  "basic": 30,   "pro": None},
    "pdf_word_count":   {"free": 20, "basic": None,  "pro": None},
    "watermark":        {"free": 2,  "basic": 20,   "pro": None},
    "darkmode":         {"free": 2,  "basic": 20,   "pro": None},
    "bgchange":         {"free": 2,  "basic": 20,   "pro": None},
    "rotate":           {"free": 5,  "basic": 50,   "pro": None},
    "resize":           {"free": 3,  "basic": 30,   "pro": None},
    "pdf2img":          {"free": 2,  "basic": 15,   "pro": None},
    "img2pdf":          {"free": 3,  "basic": 20,   "pro": None},
    "excel":            {"free": 2,  "basic": 15,   "pro": None},
    "pdf2word":         {"free": 2,  "basic": 15,   "pro": None},
    "pdf2ppt":          {"free": 0,  "basic": 0,    "pro": None},
    "pdf2epub":         {"free": 0,  "basic": 5,    "pro": None},
    "doc2pdf":          {"free": 2,  "basic": 20,   "pro": None},
    "epub2pdf":         {"free": 2,  "basic": 20,   "pro": None},
    "img_compress":     {"free": 5,  "basic": 50,   "pro": None},
    "img_resize":       {"free": 5,  "basic": 50,   "pro": None},
    "img_crop":         {"free": 5,  "basic": 50,   "pro": None},
    "img_filter":       {"free": 5,  "basic": 50,   "pro": None},
    "img_text":         {"free": 3,  "basic": 30,   "pro": None},
    "img2jpg":          {"free": 5,  "basic": None,  "pro": None},
    "img2png":          {"free": 5,  "basic": None,  "pro": None},
    "img_bgremove":     {"free": 0,  "basic": 5,    "pro": None},
    "img_collage":      {"free": 2,  "basic": 20,   "pro": None},
    "img_meme":         {"free": 5,  "basic": 50,   "pro": None},
    "img_sticker":      {"free": 5,  "basic": None,  "pro": None},
    "img_ascii":        {"free": 5,  "basic": None,  "pro": None},
    "img_flip":         {"free": 10, "basic": None,  "pro": None},
    "img_border":       {"free": 5,  "basic": 30,   "pro": None},
    "img_round":        {"free": 5,  "basic": None,  "pro": None},
    "img_exif":         {"free": 10, "basic": None,  "pro": None},
    "img_enhance":      {"free": 5,  "basic": 30,   "pro": None},
    "csv2pdf":          {"free": 3,  "basic": 30,   "pro": None},
    "txt2pdf":          {"free": 5,  "basic": 50,   "pro": None},
    "html2pdf":         {"free": 2,  "basic": 20,   "pro": None},
    "json2pdf":         {"free": 3,  "basic": 30,   "pro": None},
    "hash":             {"free": 20, "basic": None,  "pro": None},
    "steganography":    {"free": 2,  "basic": 15,   "pro": None},
    "pdf_sign":         {"free": 2,  "basic": 20,   "pro": None},
    "pwd_crack":        {"free": 0,  "basic": 0,    "pro": 1},
    "img_remove_exif":  {"free": 10, "basic": None,  "pro": None},
    "poster":           {"free": 3,  "basic": 30,   "pro": None},
    "calendar_pdf":     {"free": 2,  "basic": 20,   "pro": None},
    "invoice":          {"free": 2,  "basic": 20,   "pro": None},
    "resume":           {"free": 1,  "basic": 10,   "pro": None},
    "certificate":      {"free": 1,  "basic": 10,   "pro": None},
    "quote_card":       {"free": 5,  "basic": 50,   "pro": None},
    "birthday_card":    {"free": 3,  "basic": 30,   "pro": None},
    "business_card":    {"free": 2,  "basic": 20,   "pro": None},
    "timetable":        {"free": 2,  "basic": 20,   "pro": None},
    "flyer":            {"free": 2,  "basic": 20,   "pro": None},
    "zip":              {"free": 3,  "basic": 30,   "pro": None},
    "unzip":            {"free": 3,  "basic": 30,   "pro": None},
    "fileinfo":         {"free": 20, "basic": None,  "pro": None},
    "qrcode_scan":      {"free": 10, "basic": None,  "pro": None},
    "barcode":          {"free": 10, "basic": None,  "pro": None},
    "remind":           {"free": 3,  "basic": 20,   "pro": None},
    "notes":            {"free": 5,  "basic": 50,   "pro": None},
    "history":          {"free": 5,  "basic": None,  "pro": None},
    "feedback":         {"free": 5,  "basic": None,  "pro": None},
    "referral":         {"free": 20, "basic": None,  "pro": None},
    "handwrite":        {"free": 5,  "basic": 50,   "pro": None},
    "addtext":          {"free": 5,  "basic": 50,   "pro": None},
    "footer":           {"free": 5,  "basic": 50,   "pro": None},
    "pagenos":          {"free": 3,  "basic": 30,   "pro": None},
    "crop":             {"free": 5,  "basic": 50,   "pro": None},
    "qr":               {"free": 10, "basic": None,  "pro": None},
    "extract":          {"free": 3,  "basic": 30,   "pro": None},
    "delete_pages":     {"free": 2,  "basic": 20,   "pro": None},
    "reorder":          {"free": 3,  "basic": 30,   "pro": None},
    "reverse":          {"free": 5,  "basic": 50,   "pro": None},
    "pdf_compare":      {"free": 1,  "basic": 10,   "pro": None},
    "ocr":              {"free": 3,  "basic": 20,   "pro": None},
    "metadata":         {"free": 10, "basic": None,  "pro": None},
    "metadata_edit":    {"free": 0,  "basic": 10,   "pro": None},
    "pwd_strength":     {"free": 10, "basic": None,  "pro": None},
    "pdf2epub":         {"free": 0,  "basic": 5,    "pro": None},
    "epub2pdf":         {"free": 2,  "basic": 20,   "pro": None},
    "doc2pdf":          {"free": 2,  "basic": 20,   "pro": None},
}

FREE_DAILY_LIMIT = 5

# ─── Referral System ─────────────────────────────
REFERRAL_BONUS_DAYS = 7
REFERRAL_NEEDED     = 3

# ─── Streak System ───────────────────────────────
STREAK_BONUS_OPS = {3: 2, 7: 5, 14: 10, 30: 20}

# ─── Daily Bonus ─────────────────────────────────
DAILY_BONUS_OPS = 2

# ─── PDF Stamp Presets ───────────────────────────
STAMP_PRESETS = [
    ("⛔ CONFIDENTIAL",  (180, 0,   0)),
    ("📝 DRAFT",         (100, 100, 100)),
    ("✅ APPROVED",      (0,   140, 0)),
    ("❌ REJECTED",      (200, 0,   0)),
    ("🔒 PRIVATE",       (0,   0,   150)),
    ("📋 COPY",          (80,  80,  80)),
    ("💰 PAID",          (0,   120, 0)),
    ("⏳ PENDING",       (180, 120, 0)),
]

# ─── Quote Card Themes ───────────────────────────
QUOTE_THEMES = {
    "dark":    {"bg": (18, 18, 30),    "text": (240, 240, 255), "accent": (130, 80,  255)},
    "light":   {"bg": (255, 255, 255), "text": (30,  30,  50),  "accent": (80,  80,  200)},
    "sunset":  {"bg": (255, 100, 50),  "text": (255, 255, 255), "accent": (255, 220, 80)},
    "ocean":   {"bg": (10,  80,  120), "text": (220, 245, 255), "accent": (80,  200, 220)},
    "forest":  {"bg": (20,  60,  30),  "text": (220, 255, 220), "accent": (100, 200, 80)},
    "rose":    {"bg": (255, 230, 235), "text": (80,  20,  40),  "accent": (220, 60,  100)},
}

# ─── Business Card Themes ────────────────────────
BCARD_THEMES = {
    "minimal": {"bg": (255,255,255), "accent": (30,  30,  30),  "text": (50,  50,  50)},
    "dark":    {"bg": (20,  20,  30), "accent": (100, 100, 255), "text": (220, 220, 240)},
    "gold":    {"bg": (30,  20,  10), "accent": (200, 160, 40),  "text": (230, 210, 160)},
    "blue":    {"bg": (10,  40,  90), "accent": (80,  160, 255), "text": (200, 220, 255)},
}

# ─── Flyer Themes ────────────────────────────────
FLYER_THEMES = {
    "event":   {"bg": (20,  20,  40),  "accent": (255, 80,  120), "text": (255, 255, 255)},
    "sale":    {"bg": (255, 40,  40),  "accent": (255, 220, 0),   "text": (255, 255, 255)},
    "concert": {"bg": (10,  10,  20),  "accent": (120, 80,  255), "text": (255, 255, 255)},
    "clean":   {"bg": (245, 245, 255), "accent": (60,  60,  220), "text": (20,  20,  60)},
}

# ─── Handwritten Fonts ───────────────────────────
FONTS = {
    "caveat":       {"name": "✍️ Caveat",               "file": "fonts/Caveat.ttf"},
    "dancing":      {"name": "💃 Dancing Script",        "file": "fonts/DancingScript.ttf"},
    "kalam":        {"name": "📝 Kalam",                 "file": "fonts/Kalam.ttf"},
    "pacifico":     {"name": "🎨 Pacifico",              "file": "fonts/Pacifico.ttf"},
    "satisfy":      {"name": "✨ Satisfy",               "file": "fonts/Satisfy.ttf"},
    "shadows":      {"name": "🌙 Shadows Into Light",    "file": "fonts/ShadowsIntoLight.ttf"},
    "yellowtail":   {"name": "🌟 Yellowtail",            "file": "fonts/Yellowtail.ttf"},
    "sacramento":   {"name": "🌹 Sacramento",            "file": "fonts/Sacramento.ttf"},
    "amatic":       {"name": "🔠 Amatic SC",             "file": "fonts/AmaticSC.ttf"},
    "indie":        {"name": "📖 Indie Flower",          "file": "fonts/IndieFlower.ttf"},
    "patrick":      {"name": "🍀 Patrick Hand",          "file": "fonts/PatrickHand.ttf"},
    "mali":         {"name": "🌸 Mali",                  "file": "fonts/Mali.ttf"},
    "courgette":    {"name": "☕ Courgette",             "file": "fonts/Courgette.ttf"},
    "paytone":      {"name": "💪 Paytone One",           "file": "fonts/PaytoneOne.ttf"},
}

NOTEBOOK_STYLES = {
    "classic_blue":  {"name": "📘 Classic Blue Lines",  "bg": (255,255,255), "line_color": (0.65,0.82,1.0), "margin_color": (1.0,0.7,0.7),  "text_color": (0.05,0.05,0.3),  "line_spacing": 28, "margin_x": 70},
    "yellow_legal":  {"name": "📒 Yellow Legal Pad",    "bg": (255,252,200), "line_color": (0.7,0.85,0.5),  "margin_color": (1.0,0.4,0.4),  "text_color": (0.05,0.05,0.05), "line_spacing": 26, "margin_x": 65},
    "graph_paper":   {"name": "📐 Graph Paper",         "bg": (248,252,255), "line_color": (0.75,0.87,1.0), "margin_color": None,            "text_color": (0.05,0.05,0.5),  "line_spacing": 20, "margin_x": 50, "is_graph": True},
    "dotted":        {"name": "🔵 Dotted Notebook",     "bg": (255,255,255), "line_color": (0.7,0.7,0.85),  "margin_color": None,            "text_color": (0.0,0.0,0.0),    "line_spacing": 28, "margin_x": 50, "is_dotted": True},
    "parchment":     {"name": "📜 Vintage Parchment",   "bg": (244,228,188), "line_color": (0.6,0.45,0.3),  "margin_color": (0.55,0.3,0.15), "text_color": (0.15,0.05,0.0),  "line_spacing": 30, "margin_x": 72},
    "dark_notebook": {"name": "🌙 Dark Night Mode",     "bg": (18,18,30),    "line_color": (0.2,0.2,0.4),   "margin_color": (0.4,0.2,0.5),  "text_color": (0.9,0.95,1.0),   "line_spacing": 28, "margin_x": 70},
    "pink_diary":    {"name": "🌸 Pink Diary",          "bg": (255,240,248), "line_color": (1.0,0.72,0.85), "margin_color": (1.0,0.5,0.7),  "text_color": (0.3,0.0,0.2),    "line_spacing": 26, "margin_x": 68},
    "green_board":   {"name": "🟢 Chalkboard Green",    "bg": (28,55,35),    "line_color": (0.3,0.6,0.35),  "margin_color": (0.5,0.75,0.5), "text_color": (0.95,0.95,0.88), "line_spacing": 32, "margin_x": 70},
}

OCR_LANGUAGES = {
    "eng":      {"name": "🇬🇧 English",       "tesseract": "eng"},
    "hin":      {"name": "🇮🇳 Hindi",          "tesseract": "hin"},
    "eng+hin":  {"name": "🇮🇳 Hindi+English",  "tesseract": "eng+hin"},
    "spa":      {"name": "🇪🇸 Spanish",        "tesseract": "spa"},
    "fra":      {"name": "🇫🇷 French",         "tesseract": "fra"},
    "kor":      {"name": "🇰🇷 Korean",         "tesseract": "kor"},
    "chi_sim":  {"name": "🇨🇳 Chinese",        "tesseract": "chi_sim"},
    "ara":      {"name": "🇸🇦 Arabic",         "tesseract": "ara"},
    "deu":      {"name": "🇩🇪 German",         "tesseract": "deu"},
    "jpn":      {"name": "🇯🇵 Japanese",       "tesseract": "jpn"},
}

REACTIONS = [
    "🔥","❤️","🎉","👏","💯","⚡","🌟","😎","🚀","💎",
    "🎯","🥰","😱","🤩","👍","🙏","❤️‍🔥","💪","🏆","✨"
]
REACTION_COUNT         = 3
GROUP_REACTIONS_ENABLED = True
GROUP_REACTION_CHANCE   = 0.3
DELETE_BUTTONS_AFTER_SEC = 180

BOT_VERSION        = "6.0.0"
GITHUB             = "@SerenaXdev"
HANDWRITING_CREDIT = "Written By - Technical Serena"

IMAGE_FILTERS = {
    "blur":       "🌫️ Blur",
    "sharpen":    "🔪 Sharpen",
    "emboss":     "🌀 Emboss",
    "edge":       "⚡ Edge Enhance",
    "grayscale":  "⬜ Grayscale",
    "sepia":      "🟤 Sepia Tone",
    "brightness": "☀️ Brighten",
    "contrast":   "🔆 High Contrast",
    "vivid":      "🎨 Vivid Colors",
    "vintage":    "📷 Vintage",
    "cool":       "❄️ Cool Tone",
    "warm":       "🔥 Warm Tone",
}

PWD_CRACK_TIMEOUT_SEC = 60
PWD_CRACK_COMMON_LIST = [
    "123456","password","123456789","12345678","12345","1234567",
    "1234567890","qwerty","abc123","111111","iloveyou","admin",
    "1234","letmein","monkey","dragon","master","sunshine","princess",
    "welcome","shadow","superman","michael","football","jesus","ninja",
    "mustang","password1","123123","654321","666666","pass","test",
    "000000","zxcvbn","hello","1q2w3e","qwerty123","1q2w3e4r",
    "asdf","asdfgh","zxcvbnm","1111","2222","3333","4444","5555",
    "6666","7777","8888","9999","0000","9876","1357","2468",
]

# ─── v7: Coin System ─────────────────────────────────────────────────────────
COIN_REWARDS = {
    "daily_login":   5,
    "refer_friend":  20,
    "feedback":      10,
    "streak_7":      15,
    "streak_30":     50,
    "first_premium": 100,
}
COIN_COSTS = {
    "extra_op":      10,   # 10 coins = 1 bonus op
    "trial_day":     30,   # 30 coins = 1 day trial
    "unlock_pro_op": 50,   # 50 coins = 1 pro feature use
}

# ─── v7: Trial System ────────────────────────────────────────────────────────
TRIAL_DURATION_DAYS = 3
TRIAL_PLAN          = "basic"

# ─── v7: Promo Codes ─────────────────────────────────────────────────────────
PROMO_CODES = {
    "NEXORA50":   {"type": "coins",    "value": 50,  "max_uses": 1000},
    "STUDENT2024":{"type": "trial",    "value": 7,   "max_uses": 500},
    "WELCOME100": {"type": "coins",    "value": 100, "max_uses": 100},
    "FREEPRO":    {"type": "plan",     "value": "pro","max_uses": 10,  "days": 3},
}

# ─── v7: Student Tools ───────────────────────────────────────────────────────
FLASHCARD_THEMES = {
    "classic": {"bg": (255,255,255), "front": (30,30,80),   "back": (240,248,255)},
    "dark":    {"bg": (18,18,30),    "front": (200,200,255), "back": (30,30,60)},
    "nature":  {"bg": (230,255,230), "front": (20,60,20),    "back": (200,240,200)},
    "pink":    {"bg": (255,235,245), "front": (100,20,60),   "back": (255,220,240)},
}

MINDMAP_COLORS = [
    (255,80,80), (80,180,255), (80,220,80),
    (255,180,0), (180,80,255),(255,120,0),
]

# ─── v7: Auto-Detect MIME types ──────────────────────────────────────────────
AUTO_DETECT_ACTIONS = {
    "application/pdf":       ["compress","split","pdf_info","pdf2txt","ocr"],
    "image/jpeg":            ["img_compress","img_filter","img_resize","img_meme"],
    "image/png":             ["img_compress","img_filter","img_sticker","img_bgremove"],
    "text/plain":            ["txt2pdf","notes"],
    "text/csv":              ["csv2pdf"],
    "application/json":      ["json2pdf"],
    "text/html":             ["html2pdf"],
    "application/zip":       ["unzip","fileinfo"],
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ["doc2pdf"],
    "application/epub+zip":  ["epub2pdf"],
}

# ─── v7: Achievement Badges ──────────────────────────────────────────────────
ACHIEVEMENTS = {
    "first_step":    {"emoji": "👶", "name": "First Step",       "desc": "First file processed!", "ops": 1},
    "getting_going": {"emoji": "🏃", "name": "Getting Going",    "desc": "10 files processed",    "ops": 10},
    "power_user":    {"emoji": "💪", "name": "Power User",       "desc": "50 files processed",    "ops": 50},
    "pdf_master":    {"emoji": "🎓", "name": "PDF Master",       "desc": "100 files processed",   "ops": 100},
    "legend":        {"emoji": "🏆", "name": "Legend",           "desc": "500 files processed",   "ops": 500},
    "week_streak":   {"emoji": "🔥", "name": "Week Warrior",     "desc": "7-day streak!",         "streak": 7},
    "month_streak":  {"emoji": "💎", "name": "Month Master",     "desc": "30-day streak!",        "streak": 30},
    "social_star":   {"emoji": "⭐", "name": "Social Star",      "desc": "Referred 5 friends",    "refs": 5},
}
