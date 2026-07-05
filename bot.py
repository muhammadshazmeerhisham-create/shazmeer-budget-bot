import os
import threading
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = "8750781186:AAHGi2hhfkHJUMa2AzawQMka47dfRT1s-9w"

# ==========================
# DATABASE SQLITE
# ==========================

conn = sqlite3.connect("safia.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    merchant TEXT,
    amount REAL,
    category TEXT
)
""")

conn.commit()

# Command /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["💰 Gaji 28hb", "💸 Gaji 7hb"],
        ["🛒 Tambah Belanja", "📊 Lihat Baki"],
        ["📈 Laporan", "⚙️ Tetapan"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 SAFIA\n"
        "Smart AI Financial Assistant\n\n"
        "Selamat datang!\n\n"
        "Sila pilih menu di bawah 👇",
        reply_markup=reply_markup
    )

# Terima gambar resit
async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.photo[-1].get_file()

    await file.download_to_drive("receipt.jpg")

    await update.message.reply_text(
        "📷 Resit diterima!\n\n"
        "Sedang membaca maklumat..."
    )

# Telegram Bot
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.PHOTO, photo))

# Web server untuk Render
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.serve_forever()

if __name__ == "__main__":
    threading.Thread(target=run_web).start()
    print("Bot sedang berjalan...")
    app.run_polling(drop_pending_updates=True)
