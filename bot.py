import os
import sqlite3
import threading
import requests
import re

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

BOT_TOKEN = os.getenv("BOT_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")

# ==========================
# DATABASE
# ==========================

conn = sqlite3.connect("safia.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS expenses(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    merchant TEXT,
    amount REAL,
    category TEXT,
    note TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS salary(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    salary_type TEXT,
    amount REAL
)
""")

conn.commit()
# ==========================
# START
# ==========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

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
# ==========================
# OCR SCAN RESIT
# ==========================

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    print("PHOTO RECEIVED")
    print("Downloading image...")

    if not update.message.photo:
        return

    file = await update.message.photo[-1].get_file()

    filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    await file.download_to_drive(filename)
    print("Image downloaded")

    with open(filename, "rb") as f:

        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"filename": f},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng"
            }
        )
        
    print("OCR API status =", response.status_code)

    result = response.json()
    print(result)
    
    print("OCR Exit Code:", result.get("OCRExitCode"))
    print("IsErrored:", result.get("IsErroredOnProcessing"))
    print("Error:", result.get("ErrorMessage"))
    

    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    print("===== OCR RESULT =====")
    print(text)
    print("======================")

# ==========================
# SAFIA SMART PARSER V3
# ==========================

merchant = "Tidak Dikenal"
amount = 0.0
category = "Lain-lain"

lines = [line.strip() for line in text.split("\n") if line.strip()]

print("===== PARSED LINES =====")
for i, line in enumerate(lines):
    print(i, ":", line)
print("========================")


# -------------------------
# MERCHANT
# -------------------------

for i, line in enumerate(lines):

    lower = line.lower()

    if lower == "recipient" and i + 1 < len(lines):
        merchant = lines[i + 1]
        break

if merchant == "Tidak Dikenal":

    for line in lines:
        if "kedai" in line.lower():
            merchant = line
            break


# -------------------------
# AMOUNT (Priority 1)
# selepas Amount
# -------------------------

for i, line in enumerate(lines):

    if line.lower() == "amount" and i + 1 < len(lines):

        next_line = lines[i + 1]

        m = re.search(r"([\d,]+\.\d{2})", next_line)

        if m:
            amount = float(m.group(1).replace(",", ""))
            break


# -------------------------
# Priority 2
# Cari RMxx.xx seluruh OCR
# -------------------------

if amount == 0:

    m = re.search(r"RM\s*([\d,]+\.\d{2})", text, re.IGNORECASE)

    if m:
        amount = float(m.group(1).replace(",", ""))


# -------------------------
# Priority 3
# Cari nombor xx.xx
# -------------------------

if amount == 0:

    numbers = re.findall(r"\d[\d,]*\.\d{2}", text)

    if numbers:

        amount = float(numbers[0].replace(",", ""))


print("Merchant :", merchant)
print("Amount   :", amount)
            
# Simpan ke database
cursor.execute(
    """
    INSERT INTO expenses(
        date,
        merchant,
        amount,
        category,
        note
    )
    VALUES (?, ?, ?, ?, ?)
    """,
    (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        merchant,
        amount,
        category,
        ""
    )
)
    
conn.commit()
    
message = (
    "✅ Resit berjaya disimpan\n\n"
    f"🏪 Kedai:\n{merchant}\n\n"
    f"💰 Jumlah:\nRM{amount:.2f}\n\n"
    f"📂 Kategori:\n{category}"
)

    await update.message.reply_text(message)

# ==========================
# SENARAI BELANJA
# ==========================

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("""
        SELECT
            date,
            merchant,
            amount,
            category
        FROM expenses
        ORDER BY id DESC
    """)

    rows = cursor.fetchall()

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

    cursor.execute("""
        SELECT IFNULL(SUM(amount),0)
        FROM expenses
    """)

    total = cursor.fetchone()[0]

    await update.message.reply_text(
        f"""📊 SAFIA Dashboard

💰 Jumlah Belanja
RM{total:.2f}
"""
    )

# ==========================
# BUTTON MENU
# ==========================

async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):

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

    print("SAFIA Started...")
    print("Polling started...")

    app.run_polling(
        drop_pending_updates=True
    )
