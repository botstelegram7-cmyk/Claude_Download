"""
Nexora PDF Doctor Bot v7.0 — Main Entry Point
=====================================================
v7 New: Auto-detect files, Animated progress bars, Quick action buttons,
        Coin system, Trial, Promo codes, Achievements, Stats card, Leaderboard,
        Flashcards, Mind maps, Study schedule, Assignment tracker, Pomodoro,
        PDF Flatten, PDF Annotate, PDF Split by Size, PDF Table Extract
"""
import asyncio, logging, traceback
from aiohttp import web
from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes,
)
from config import BOT_TOKEN, PORT, OWNER_ID, MAX_FILE_SIZE_MB, BROADCAST_DELAY_SEC, BROADCAST_BATCH

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Handler imports ───────────────────────────────────────────────────────────
from handlers.start_handler   import start_cmd, help_cmd, account_cmd
from handlers.premium_handler import (
    premium_cmd, grant_premium_cmd, buy_plan_callback, pay_screenshot_callback,
)
from handlers.pdf_handler import (
    menu_callback, handle_message, handle_group_reaction, cmd_dashboard,
    cmd_compress, cmd_split, cmd_merge, cmd_lock, cmd_unlock, cmd_repair,
    cmd_watermark, cmd_darkmode, cmd_pagenos, cmd_pdf2img, cmd_img2pdf,
    cmd_excel, cmd_bgchange, cmd_handwrite, cmd_ocr, cmd_rotate, cmd_resize,
    cmd_addtext, cmd_footer, cmd_extract, cmd_metadata,
    cmd_pdf2word, cmd_pdf2ppt, cmd_crop, cmd_qr,
    cmd_delete_pages, cmd_reorder, cmd_lang, cmd_reverse, cmd_compare,
)
from handlers.new_features_handler import (
    cmd_pdf2txt, cmd_linearize, cmd_thumbnail, cmd_pdf_info,
    cmd_redact, cmd_impose, cmd_deskew, cmd_pwd_strength, cmd_pwd_crack,
    cmd_metadata_edit,
    cmd_img_compress, cmd_img_resize, cmd_img_crop, cmd_img_filter,
    cmd_img_text, cmd_img2jpg, cmd_img2png, cmd_img_bgremove,
    cmd_csv2pdf, cmd_txt2pdf, cmd_html2pdf, cmd_json2pdf,
    cmd_doc2pdf, cmd_pdf2epub, cmd_epub2pdf,
    cmd_hash, cmd_steganography, cmd_pdf_sign,
    cmd_poster, cmd_calendar_pdf, cmd_invoice, cmd_resume, cmd_certificate,
    cmd_zip, cmd_unzip, cmd_fileinfo, cmd_qrcode_scan, cmd_barcode,
    cmd_remind, cmd_notes, cmd_history,
    handle_new_features, handle_new_callbacks,
    cmd_pdf_stamp, cmd_pdf_grayscale, cmd_pdf_extract_imgs,
    cmd_pdf_remove_meta, cmd_pdf_word_count, cmd_pdf_header, cmd_pdf_bookmark,
    cmd_img_collage, cmd_img_meme, cmd_img_sticker, cmd_img_ascii,
    cmd_img_flip, cmd_img_border, cmd_img_round, cmd_img_exif,
    cmd_img_remove_exif, cmd_img_enhance,
    cmd_quote_card, cmd_birthday_card, cmd_business_card, cmd_flyer, cmd_timetable,
    cmd_feedback, cmd_referral, cmd_streak,
    handle_new_features_v6, handle_new_callbacks_v6,
)
from handlers.v7_handler import (
    # UX
    auto_detect_and_suggest, notify_achievements, award_coins_for_op,
    # Monetize
    cmd_coins, cmd_earn, cmd_trial, cmd_redeem,
    # Engagement
    cmd_badges, cmd_stats_card, cmd_top,
    # Student
    cmd_flashcard, cmd_mindmap, cmd_study_schedule, cmd_assign, cmd_pomodoro,
    # PDF Advanced
    cmd_pdf_flatten, cmd_pdf_split_size, cmd_pdf_annotate, cmd_pdf_table,
    # Handlers
    handle_v7_features, handle_v7_callbacks,
)
from handlers.admin_handler import admin_panel

# ── Bot Commands ──────────────────────────────────────────────────────────────
BOT_COMMANDS = [
    BotCommand("start",             "🏠 Main Menu"),
    BotCommand("help",              "❓ Help & Commands"),
    BotCommand("account",           "👤 My Account"),
    BotCommand("dashboard",         "📊 Usage Dashboard"),
    BotCommand("premium",           "💎 Premium Plans"),
    BotCommand("trial",             "🎁 Free 3-Day Trial"),
    BotCommand("redeem",            "🎟️ Redeem Promo Code"),
    BotCommand("coins",             "🪙 My Coins"),
    BotCommand("earn",              "💰 Earn Coins"),
    BotCommand("streak",            "🔥 Daily Streak"),
    BotCommand("badges",            "🏅 Achievements"),
    BotCommand("stats_card",        "📊 Stats Card (Shareable)"),
    BotCommand("top",               "🏆 Leaderboard"),
    BotCommand("referral",          "👥 Refer & Earn"),
    BotCommand("feedback",          "⭐ Rate the Bot"),
    BotCommand("lang",              "🌍 Language"),
    # Student Tools
    BotCommand("flashcard",         "📚 Flashcard Maker"),
    BotCommand("mindmap",           "🧠 Mind Map Generator"),
    BotCommand("study_schedule",    "📅 Study Schedule"),
    BotCommand("assign",            "📋 Assignment Tracker"),
    BotCommand("pomodoro",          "🍅 Pomodoro Timer"),
    # PDF Tools
    BotCommand("compress",          "📐 Compress PDF"),
    BotCommand("split",             "✂️ Split PDF"),
    BotCommand("merge",             "🔗 Merge PDFs"),
    BotCommand("lock",              "🔒 Lock PDF"),
    BotCommand("unlock",            "🔓 Unlock PDF"),
    BotCommand("repair",            "🧩 Repair PDF"),
    BotCommand("pdf2txt",           "📄 PDF to Text"),
    BotCommand("linearize",         "🌐 Web Optimize PDF"),
    BotCommand("thumbnail",         "🖼️ PDF Preview"),
    BotCommand("pdf_info",          "🔍 PDF Deep Analysis"),
    BotCommand("redact",            "⬛ Redact Text"),
    BotCommand("impose",            "📋 2-up / 4-up"),
    BotCommand("deskew",            "📐 Fix Crooked Scan"),
    BotCommand("pdf_stamp",         "🖊️ Stamp PDF"),
    BotCommand("pdf_grayscale",     "⬛ PDF Grayscale"),
    BotCommand("pdf_extract_imgs",  "🖼️ Extract Images"),
    BotCommand("pdf_remove_meta",   "🗑️ Strip Metadata"),
    BotCommand("pdf_word_count",    "📊 Word Count"),
    BotCommand("pdf_header",        "🔢 Add Header"),
    BotCommand("pdf_bookmark",      "🔖 View Bookmarks"),
    BotCommand("pdf_flatten",       "📋 Flatten Forms"),
    BotCommand("pdf_split_size",    "✂️ Split by Size"),
    BotCommand("pdf_annotate",      "🖊️ Highlight Text"),
    BotCommand("pdf_table",         "📊 Extract Tables"),
    BotCommand("pwd_strength",      "🔐 Password Strength"),
    BotCommand("pwd_crack",         "🔓 PDF Password Crack 👑"),
    BotCommand("metadata_edit",     "✏️ Edit Metadata"),
    # Visual
    BotCommand("watermark",         "🌊 Watermark"),
    BotCommand("darkmode",          "🌙 Dark Mode"),
    BotCommand("pagenos",           "🔢 Page Numbers"),
    BotCommand("bgchange",          "🎨 BG Color"),
    BotCommand("rotate",            "🔄 Rotate"),
    BotCommand("resize",            "📏 Resize A4"),
    # Convert
    BotCommand("pdf2img",           "🖼️ PDF to Images"),
    BotCommand("img2pdf",           "🖼️ Images to PDF"),
    BotCommand("excel",             "📊 PDF to Excel"),
    BotCommand("pdf2word",          "📄 PDF to Word"),
    BotCommand("pdf2epub",          "📚 PDF to EPUB"),
    BotCommand("epub2pdf",          "📖 EPUB to PDF"),
    BotCommand("doc2pdf",           "📝 Word to PDF"),
    # Image
    BotCommand("img_compress",      "📦 Compress Image"),
    BotCommand("img_resize",        "📏 Resize Image"),
    BotCommand("img_crop",          "✂️ Crop Image"),
    BotCommand("img_filter",        "🎨 Image Filters"),
    BotCommand("img_text",          "📝 Text on Image"),
    BotCommand("img2jpg",           "🖼️ To JPG"),
    BotCommand("img2png",           "🖼️ To PNG"),
    BotCommand("img_bgremove",      "✂️ Remove BG"),
    BotCommand("img_collage",       "🖼️ Collage"),
    BotCommand("img_meme",          "😂 Meme Generator"),
    BotCommand("img_sticker",       "🎭 Make Sticker"),
    BotCommand("img_ascii",         "🔤 ASCII Art"),
    BotCommand("img_flip",          "🔄 Flip Image"),
    BotCommand("img_border",        "🖼️ Add Border"),
    BotCommand("img_round",         "⭕ Rounded Corners"),
    BotCommand("img_exif",          "📷 View EXIF"),
    BotCommand("img_remove_exif",   "🧹 Strip EXIF"),
    BotCommand("img_enhance",       "✨ Auto Enhance"),
    # Doc Convert
    BotCommand("csv2pdf",           "📊 CSV to PDF"),
    BotCommand("txt2pdf",           "📄 TXT to PDF"),
    BotCommand("html2pdf",          "🌐 HTML to PDF"),
    BotCommand("json2pdf",          "📋 JSON to PDF"),
    # Security
    BotCommand("hash",              "🔒 File Hash"),
    BotCommand("steganography",     "🕵️ Steganography"),
    BotCommand("pdf_sign",          "✍️ Sign PDF"),
    # Creative
    BotCommand("quote_card",        "💬 Quote Card"),
    BotCommand("birthday_card",     "🎂 Birthday Card"),
    BotCommand("business_card",     "💼 Business Card"),
    BotCommand("flyer",             "📢 Flyer Generator"),
    BotCommand("timetable",         "🗓️ Timetable"),
    BotCommand("poster",            "🎨 Poster"),
    BotCommand("calendar_pdf",      "📅 Calendar PDF"),
    BotCommand("invoice",           "🧾 Invoice"),
    BotCommand("resume",            "📋 Resume Builder"),
    BotCommand("certificate",       "🏆 Certificate"),
    BotCommand("handwrite",         "✍️ Handwritten PDF"),
    # Pages
    BotCommand("extract",           "🔖 Extract Pages"),
    BotCommand("delete_pages",      "🗑️ Delete Pages"),
    BotCommand("reorder",           "🔀 Reorder Pages"),
    BotCommand("reverse",           "🔃 Reverse Pages"),
    BotCommand("compare",           "🔍 Compare PDFs"),
    # Smart Tools
    BotCommand("ocr",               "👁️ OCR Text"),
    BotCommand("metadata",          "📋 View Metadata"),
    BotCommand("addtext",           "📝 Add Text"),
    BotCommand("footer",            "🗂️ Footer"),
    BotCommand("crop",              "✂️ Crop Margins"),
    BotCommand("qr",                "🔲 QR Code"),
    # Utilities
    BotCommand("zip",               "📦 Create ZIP"),
    BotCommand("unzip",             "📂 Extract ZIP"),
    BotCommand("fileinfo",          "ℹ️ File Info"),
    BotCommand("qrcode_scan",       "📷 Scan QR"),
    BotCommand("barcode",           "📊 Barcode"),
    # UX
    BotCommand("remind",            "⏰ Set Reminder"),
    BotCommand("notes",             "📒 Notes"),
    BotCommand("history",           "📂 History"),
]


# ── File size guard ───────────────────────────────────────────────────────────

async def check_file_size(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> bool:
    msg = update.message
    if not msg:
        return True
    file_size = 0
    if msg.document:
        file_size = msg.document.file_size or 0
    elif msg.photo:
        file_size = msg.photo[-1].file_size or 0
    if file_size == 0:
        return True
    from database import get_plan
    plan      = await get_plan(update.effective_user.id)
    max_mb    = MAX_FILE_SIZE_MB.get(plan, 20)
    max_bytes = max_mb * 1024 * 1024
    if file_size > max_bytes:
        actual_mb = round(file_size / 1024 / 1024, 1)
        await msg.reply_text(
            f"⚠️ <b>File Too Large!</b>\n\n"
            f"📦 Your file: <b>{actual_mb}MB</b>\n"
            f"🚫 Your limit: <b>{max_mb}MB</b> ({plan.title()} plan)\n\n"
            f"💡 /trial for free upgrade  |  /premium for full access",
            parse_mode="HTML",
        )
        return False
    return True


# ── Daily bonus + streak + trial expiry check ─────────────────────────────────

async def handle_daily_events(user_id: int, bot, chat_id: int):
    try:
        from database import claim_daily_bonus, update_streak, check_trial_expiry
        from config import DAILY_BONUS_OPS
        await check_trial_expiry(user_id)
        bonus_given           = await claim_daily_bonus(user_id)
        streak, milestone, _  = await update_streak(user_id)
        msgs = []
        if bonus_given:
            msgs.append(f"🎁 <b>Daily Bonus!</b> +{DAILY_BONUS_OPS} free ops + <b>5 🪙 coins</b>!")
            from database import add_coins
            await add_coins(user_id, 5, "daily_login")
        if milestone:
            from config import STREAK_BONUS_OPS
            bonus = STREAK_BONUS_OPS.get(streak, 0)
            msgs.append(
                f"🔥 <b>{streak}-Day Streak!</b> Amazing!\n"
                f"{'🎁 Bonus: +' + str(bonus) + ' ops today!' if bonus else ''}"
            )
        if msgs:
            await bot.send_message(chat_id=chat_id, text="\n\n".join(msgs), parse_mode="HTML")
    except Exception:
        pass


# ── Unified message handler ───────────────────────────────────────────────────

async def unified_message_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from database import ensure_user
    user = update.effective_user
    await ensure_user(user.id, user.full_name, user.username or "")
    if not await check_file_size(update, ctx):
        return
    asyncio.create_task(handle_daily_events(user.id, ctx.bot, update.effective_chat.id))

    # Handler priority: v7 → auto-detect → v6 → v5 → original
    if await handle_v7_features(update, ctx):
        return
    if await handle_new_features_v6(update, ctx):
        return
    if await handle_new_features(update, ctx):
        return
    # Auto-detect file when no state active
    if update.message and (update.message.document or update.message.photo):
        state = ctx.user_data.get("state", "")
        if not state:
            if await auto_detect_and_suggest(update, ctx):
                return
    await handle_message(update, ctx)


# ── Unified callback handler ──────────────────────────────────────────────────

async def unified_callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if await handle_v7_callbacks(update, ctx):
        return
    if await handle_new_callbacks_v6(update, ctx):
        return
    if await handle_new_callbacks(update, ctx):
        return
    await menu_callback(update, ctx)


# ── Error handler ─────────────────────────────────────────────────────────────

async def error_handler(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    err = ctx.error
    logger.error("Exception:", exc_info=err)
    import telegram.error as tg_err
    if isinstance(err, (tg_err.TimedOut, tg_err.NetworkError)):
        return
    if update and isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                f"⚠️ <b>Oops!</b> Something went wrong.\n"
                f"<code>{str(err)[:200]}</code>\n\nTry again or /start",
                parse_mode="HTML",
            )
        except Exception:
            pass
    if OWNER_ID:
        try:
            tb = "".join(traceback.format_exception(type(err), err, err.__traceback__))
            await ctx.bot.send_message(
                chat_id=OWNER_ID,
                text=f"🚨 <b>Error!</b>\n\n<pre>{tb[:3000]}</pre>",
                parse_mode="HTML",
            )
        except Exception:
            pass


# ── Broadcast ─────────────────────────────────────────────────────────────────

async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    text  = " ".join(ctx.args)
    from database import get_all_users
    users = await get_all_users()
    total = len(users)
    sent = failed = 0
    prog  = await update.message.reply_text(f"📢 Broadcasting to {total} users...")
    for i, u in enumerate(users):
        try:
            await ctx.bot.send_message(
                chat_id=u["user_id"],
                text=f"📢 <b>Announcement:</b>\n\n{text}",
                parse_mode="HTML",
            )
            sent += 1
        except Exception:
            failed += 1
        await asyncio.sleep(BROADCAST_DELAY_SEC)
        if (i + 1) % BROADCAST_BATCH == 0:
            try:
                await prog.edit_text(f"📢 {i+1}/{total} — ✅{sent} ❌{failed}")
            except Exception:
                pass
    await prog.edit_text(f"📢 <b>Done!</b>\n✅ {sent}\n❌ {failed}", parse_mode="HTML")


# ── Stats (admin) ─────────────────────────────────────────────────────────────

async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    from database import get_admin_stats, get_feedback_stats
    s  = await get_admin_stats()
    fb = await get_feedback_stats()
    await update.message.reply_text(
        f"📊 <b>Nexora Bot v7.0 Stats</b>\n\n"
        f"👥 Total: <b>{s['total_users']}</b>\n"
        f"🆓 Free: <b>{s['free_users']}</b>\n"
        f"⭐ Basic: <b>{s['basic_users']}</b>\n"
        f"👑 Pro: <b>{s['pro_users']}</b>\n"
        f"📆 Active today: <b>{s['today_active']}</b>\n"
        f"⚡ Ops today: <b>{s['today_ops']}</b>\n"
        f"💳 Pending: <b>{s['pending_payments']}</b>\n\n"
        f"⭐ Avg rating: <b>{fb['avg_rating']}/5</b> ({fb['total']} reviews)",
        parse_mode="HTML",
    )


# ── Reminder scheduler ────────────────────────────────────────────────────────

async def reminder_scheduler(bot):
    from database import get_due_reminders, mark_reminder_done
    while True:
        try:
            for r in await get_due_reminders():
                try:
                    await bot.send_message(
                        chat_id=r["chat_id"],
                        text=f"⏰ <b>Reminder!</b>\n\n📝 {r['message']}",
                        parse_mode="HTML",
                    )
                    await mark_reminder_done(r["id"])
                except Exception as e:
                    logger.warning(f"Reminder: {e}")
        except Exception as e:
            logger.error(f"Scheduler: {e}")
        await asyncio.sleep(30)


# ── App builder ───────────────────────────────────────────────────────────────

def build_app() -> Application:
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .connect_timeout(30).read_timeout(30)
        .write_timeout(60).pool_timeout(30)
        .build()
    )

    def cmd(name, func):
        app.add_handler(CommandHandler(name, func))

    # Core
    cmd("start",             start_cmd)
    cmd("help",              help_cmd)
    cmd("account",           account_cmd)
    cmd("dashboard",         cmd_dashboard)
    cmd("premium",           premium_cmd)
    cmd("lang",              cmd_lang)

    # v7 UX & Monetization
    cmd("trial",             cmd_trial)
    cmd("redeem",            cmd_redeem)
    cmd("coins",             cmd_coins)
    cmd("earn",              cmd_earn)
    cmd("streak",            cmd_streak)
    cmd("badges",            cmd_badges)
    cmd("stats_card",        cmd_stats_card)
    cmd("top",               cmd_top)
    cmd("referral",          cmd_referral)
    cmd("feedback",          cmd_feedback)

    # v7 Student Tools
    cmd("flashcard",         cmd_flashcard)
    cmd("mindmap",           cmd_mindmap)
    cmd("study_schedule",    cmd_study_schedule)
    cmd("assign",            cmd_assign)
    cmd("pomodoro",          cmd_pomodoro)

    # v7 PDF Advanced
    cmd("pdf_flatten",       cmd_pdf_flatten)
    cmd("pdf_split_size",    cmd_pdf_split_size)
    cmd("pdf_annotate",      cmd_pdf_annotate)
    cmd("pdf_table",         cmd_pdf_table)

    # Original PDF
    for name, func in [
        ("compress", cmd_compress), ("split", cmd_split), ("merge", cmd_merge),
        ("lock", cmd_lock), ("unlock", cmd_unlock), ("repair", cmd_repair),
        ("watermark", cmd_watermark), ("darkmode", cmd_darkmode), ("pagenos", cmd_pagenos),
        ("pdf2img", cmd_pdf2img), ("img2pdf", cmd_img2pdf), ("excel", cmd_excel),
        ("bgchange", cmd_bgchange), ("handwrite", cmd_handwrite), ("ocr", cmd_ocr),
        ("rotate", cmd_rotate), ("resize", cmd_resize), ("addtext", cmd_addtext),
        ("footer", cmd_footer), ("extract", cmd_extract), ("metadata", cmd_metadata),
        ("pdf2word", cmd_pdf2word), ("pdf2ppt", cmd_pdf2ppt), ("crop", cmd_crop),
        ("qr", cmd_qr), ("delete_pages", cmd_delete_pages), ("reorder", cmd_reorder),
        ("reverse", cmd_reverse), ("compare", cmd_compare),
    ]:
        cmd(name, func)

    # v5 PDF
    for name, func in [
        ("pdf2txt", cmd_pdf2txt), ("linearize", cmd_linearize), ("thumbnail", cmd_thumbnail),
        ("pdf_info", cmd_pdf_info), ("redact", cmd_redact), ("impose", cmd_impose),
        ("deskew", cmd_deskew), ("pwd_strength", cmd_pwd_strength), ("pwd_crack", cmd_pwd_crack),
        ("metadata_edit", cmd_metadata_edit),
    ]:
        cmd(name, func)

    # v6 PDF
    for name, func in [
        ("pdf_stamp", cmd_pdf_stamp), ("pdf_grayscale", cmd_pdf_grayscale),
        ("pdf_extract_imgs", cmd_pdf_extract_imgs), ("pdf_remove_meta", cmd_pdf_remove_meta),
        ("pdf_word_count", cmd_pdf_word_count), ("pdf_header", cmd_pdf_header),
        ("pdf_bookmark", cmd_pdf_bookmark),
    ]:
        cmd(name, func)

    # Image (v5 + v6)
    for name, func in [
        ("img_compress", cmd_img_compress), ("img_resize", cmd_img_resize),
        ("img_crop", cmd_img_crop), ("img_filter", cmd_img_filter),
        ("img_text", cmd_img_text), ("img2jpg", cmd_img2jpg), ("img2png", cmd_img2png),
        ("img_bgremove", cmd_img_bgremove), ("img_collage", cmd_img_collage),
        ("img_meme", cmd_img_meme), ("img_sticker", cmd_img_sticker),
        ("img_ascii", cmd_img_ascii), ("img_flip", cmd_img_flip),
        ("img_border", cmd_img_border), ("img_round", cmd_img_round),
        ("img_exif", cmd_img_exif), ("img_remove_exif", cmd_img_remove_exif),
        ("img_enhance", cmd_img_enhance),
    ]:
        cmd(name, func)

    # Doc Convert
    for name, func in [
        ("csv2pdf", cmd_csv2pdf), ("txt2pdf", cmd_txt2pdf), ("html2pdf", cmd_html2pdf),
        ("json2pdf", cmd_json2pdf), ("doc2pdf", cmd_doc2pdf),
        ("pdf2epub", cmd_pdf2epub), ("epub2pdf", cmd_epub2pdf),
    ]:
        cmd(name, func)

    # Security & Creative
    for name, func in [
        ("hash", cmd_hash), ("steganography", cmd_steganography), ("pdf_sign", cmd_pdf_sign),
        ("poster", cmd_poster), ("calendar_pdf", cmd_calendar_pdf), ("invoice", cmd_invoice),
        ("resume", cmd_resume), ("certificate", cmd_certificate),
        ("quote_card", cmd_quote_card), ("birthday_card", cmd_birthday_card),
        ("business_card", cmd_business_card), ("flyer", cmd_flyer), ("timetable", cmd_timetable),
    ]:
        cmd(name, func)

    # Utilities & UX
    for name, func in [
        ("zip", cmd_zip), ("unzip", cmd_unzip), ("fileinfo", cmd_fileinfo),
        ("qrcode_scan", cmd_qrcode_scan), ("barcode", cmd_barcode),
        ("remind", cmd_remind), ("notes", cmd_notes), ("history", cmd_history),
    ]:
        cmd(name, func)

    # Admin
    cmd("givepremium", grant_premium_cmd)
    cmd("broadcast",   broadcast_cmd)
    cmd("stats",       stats_cmd)

    # Callbacks
    app.add_handler(CallbackQueryHandler(buy_plan_callback,       pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(pay_screenshot_callback, pattern="^pay_ss_"))
    app.add_handler(CallbackQueryHandler(unified_callback_handler))

    # Messages — private
    app.add_handler(MessageHandler(
        (filters.Document.ALL | filters.PHOTO | filters.TEXT) &
        ~filters.COMMAND & filters.ChatType.PRIVATE,
        unified_message_handler,
    ))
    # Messages — groups
    app.add_handler(MessageHandler(
        filters.ChatType.GROUPS & ~filters.COMMAND,
        handle_group_reaction,
    ))

    app.add_error_handler(error_handler)
    return app


# ── Web server ────────────────────────────────────────────────────────────────

async def health(request):
    return web.Response(text="Nexora PDF Doctor v7.0 — Online!", status=200)


async def run_web_server(bot_app):
    wa = web.Application()
    wa.router.add_get("/",       health)
    wa.router.add_get("/health", health)
    wa.router.add_get("/admin",  admin_panel)
    runner = web.AppRunner(wa)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Web server on port {PORT}")


# ── Main ──────────────────────────────────────────────────────────────────────

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    try:
        from utils.font_loader import download_fonts
        download_fonts()
    except Exception as e:
        logger.warning(f"Fonts: {e}")

    tg_app = build_app()
    async with tg_app:
        try:
            await tg_app.bot.set_my_commands(BOT_COMMANDS)
        except Exception as e:
            logger.warning(f"Commands: {e}")

    await run_web_server(tg_app)
    logger.info("🚀 Starting Nexora PDF Doctor Bot v7.0...")

    async with tg_app:
        await tg_app.start()
        asyncio.create_task(reminder_scheduler(tg_app.bot))
        logger.info("✅ Nexora PDF Doctor v7.0 is LIVE!")
        await tg_app.updater.start_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES,
            timeout=10, read_timeout=15,
            write_timeout=15, connect_timeout=15,
            pool_timeout=15,
        )
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
