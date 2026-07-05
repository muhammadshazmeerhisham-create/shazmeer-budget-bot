import os
import threading
import sqlite3
import requests

from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TOKEN = "8750781186:AAFS2bhkzgPcdCxjcxe8fSrtG9vDRzPtQSQ"

OCR_API_KEY = os.getenv("OCR_API_KEY")

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

    filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    await file.download_to_drive(filename)

    # Hantar gambar ke OCR.Space
    with open(filename, "rb") as f:
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"filename": f},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng"
            }
        )

    result = response.json()

    print("===== API RESPONSE =====")
    print(result)
    print("========================")

    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    print("===== OCR RESULT =====")
    print(text)
    print("======================")

    cursor.execute(
        "INSERT INTO expenses(date, merchant, amount, category) VALUES (?, ?, ?, ?)",
        (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Belum Dikenal",
            0,
            "Belum Dikenal"
        )
    )

    conn.commit()

    await update.message.reply_text(
        "✅ Gambar berjaya diterima!\n\n"
        "🔍 OCR sedang membaca resit...\n"
        "💾 Rekod dimasukkan ke database."
    )

# Senarai rekod
async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute(
        "SELECT id, date, merchant, amount, category FROM expenses ORDER BY id DESC"
    )

    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("📭 Tiada rekod lagi.")
        return

    text = "📒 Senarai Perbelanjaan\n\n"

    for row in rows:
        text += (
            f"🆔 {row[0]}\n"
            f"📅 {row[1]}\n"
            f"🏪 {row[2]}\n"
            f"💰 RM{row[3]:.2f}\n"
            f"📂 {row[4]}\n\n"
        )

    await update.message.reply_text(text)

# Telegram Bot
app = Application.builder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("list", list_expenses))
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
