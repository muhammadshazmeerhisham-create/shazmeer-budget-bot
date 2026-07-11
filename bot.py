import os
import threading
import re

from bank_db import BANK_DB
from merchant_db import MERCHANT_DB
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ==========================
# CONFIG
# ==========================

from config import BOT_TOKEN
from logging_config import get_logger

# ==========================
# LOGGING SYSTEM
# ==========================

logger = get_logger("SAFIA")

# ==========================
# DATABASE
# ==========================

from database import (
    get_expenses,
    get_total_expenses,
    initialize_database,
    save_expense,
)

initialize_database()

# ==========================
# OCR
# ==========================

from ocr import scan_receipt
from parser import parse_receipt

# ==========================
# START
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        logger.info(
            f"/start | User ID : {update.effective_user.id}"
        )

        keyboard = [
            ["📷 Scan Resit"],
            ["📒 Senarai", "📊 Dashboard"],
            ["💰 Gaji 28hb", "💸 Gaji 7hb"],
            ["⚙️ Tetapan"]
        ]

        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True
        )

        await update.message.reply_text(
            "🤖 SAFIA\n\n"
            "Smart AI Financial Assistant\n\n"
            "Selamat datang!\n\n"
            "Sila pilih menu di bawah 👇",
            reply_markup=reply_markup
        )

    except Exception:

        logger.exception("Start Function Error")

        await update.message.reply_text(
            "⚠️ Ralat semasa membuka menu utama."
        )
# ==========================
# OCR SCAN RESIT
# ==========================

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    try:

        logger.info(
            f"Photo received | User ID : {update.effective_user.id}"
        )

        if not update.message.photo:
            return

        file = await update.message.photo[-1].get_file()

        filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

        await file.download_to_drive(filename)

        text = scan_receipt(filename)

        result = parse_receipt(text)

        merchant = result["merchant"]
        recipient = result["recipient"]
        amount = result["amount"]
        category = result["category"]
        receipt_date = result["receipt_date"]
        receipt_time = result["receipt_time"]
        reference = result["reference"]

        save_expense(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            merchant,
            amount,
            category,
            "",
        )

        await update.message.reply_text(
            f"""✅ Resit Berjaya Disimpan

🏪 Kedai      : {merchant}
👤 Penerima   : {recipient}
💰 Jumlah     : RM{amount:.2f}
📂 Kategori   : {category}
📅 Tarikh     : {receipt_date}
🕒 Masa       : {receipt_time}
🔖 Rujukan    : {reference}

💾 Data berjaya direkodkan.
"""
        )

    except Exception as e:

        logger.exception("Photo Function Error")

        await update.message.reply_text(
            "❌ Maaf, berlaku ralat semasa memproses resit.\n"
            "Sila cuba semula sebentar lagi."
        )

# ==========================
# SENARAI BELANJA
# ==========================

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    rows = get_expenses()

    if not rows:
        await update.message.reply_text("📭 Tiada rekod lagi.")
        return

    text = "📒 SENARAI PERBELANJAAN\n\n"

    total = 0

    for row in rows:

        total += row[2]

        text += (
            f"🏪 {row[1]}\n"
            f"💰 RM{row[2]:.2f}\n"
            f"📂 {row[3]}\n"
            f"📅 {row[0]}\n\n"
        )

    text += f"💵 Jumlah Belanja : RM{total:.2f}"

    await update.message.reply_text(text)

# ==========================
# DASHBOARD
# ==========================

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    total = get_total_expenses()

    await update.message.reply_text(
        f"""📊 SAFIA Dashboard 💰 Jumlah Belanja RM{total:.2f} """
    )

# ==========================
# BUTTON MENU
# ==========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

    logger.info(
        f"Button : {update.message.text}"
    )

    text = update.message.text

    if text == "📒 Senarai":
        await list_expenses(update, context)
        return

    if text == "📊 Dashboard":
        await dashboard(update, context)
        return

    if text == "📷 Scan Resit":
        await update.message.reply_text(
            "📷 Sila hantar gambar resit."
        )
        return

    await update.message.reply_text(
        "Sila gunakan menu yang disediakan."
    )

# ==========================
# GLOBAL ERROR HANDLER
# ==========================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):

    update_id = getattr(update, "update_id", "-")
    user = getattr(update, "effective_user", None)
    user_id = getattr(user, "id", "-")

    if getattr(update, "callback_query", None):
        update_type = "callback_query"
    elif getattr(update, "message", None):
        update_type = "photo" if update.message.photo else "message"
    else:
        update_type = "unknown"

    logger.exception(
        "🚨 Unhandled Exception | update_id=%s | user_id=%s | type=%s",
        update_id,
        user_id,
        update_type,
        exc_info=context.error
    )

    if update and hasattr(update, "effective_message"):

        try:
            await update.effective_message.reply_text(
                "⚠️ Maaf, berlaku ralat semasa memproses permintaan anda.\n\n"
                "Sila cuba semula sebentar lagi."
            )

        except Exception:
            pass


# ==========================
# TELEGRAM BOT
# ==========================

app = Application.builder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_expenses))
app.add_handler(CommandHandler("dashboard", dashboard))

app.add_handler(
    MessageHandler(filters.PHOTO, photo)
)

app.add_handler(
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        button
    )
)

app.add_error_handler(error_handler)

# ==========================
# WEB SERVER (RENDER)
# ==========================

class Handler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"SAFIA is running!")

def run_web():

    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        Handler
    )

    server.serve_forever()

# ==========================
# MAIN
# ==========================

if __name__ == "__main__":

    threading.Thread(
        target=run_web,
        daemon=True
    ).start()

    logger.info("🚀 SAFIA Bot Started")

    app.run_polling(
        drop_pending_updates=True
    )
