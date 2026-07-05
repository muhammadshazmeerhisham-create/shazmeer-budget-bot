import os
import threading
import sqlite3
import requests
import re

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

TOKEN = os.getenv("BOT_TOKEN")
OCR_API_KEY = os.getenv("OCR_API_KEY")

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

conn.commit()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        ["📷 Scan Resit"],
        ["📒 Senarai", "📊 Laporan"],
        ["💰 Baki", "⚙️ Tetapan"]
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 SAFIA\n"
        "Smart AI Financial Assistant\n\n"
        "Selamat datang.\n"
        "Sila pilih menu di bawah.",
        reply_markup=reply_markup
    )

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

async def photo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    # Download gambar
    file = await update.message.photo[-1].get_file()

    filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"

    await file.download_to_drive(filename)

    # OCR.Space
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

    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    print(text)

text = ""

if result.get("ParsedResults"):
    text = result["ParsedResults"][0]["ParsedText"]

print(text)

# ==========================
# AI Receipt Parser
# ==========================

merchant = "Tidak Dikenal"
amount = 0.0
category = "Lain-lain"

merchant_upper = merchant.upper()

if "PETRONAS" in merchant_upper or "SHELL" in merchant_upper or "BHP" in merchant_upper:
    category = "⛽ Minyak"

elif "KFC" in merchant_upper or "MCD" in merchant_upper or "MCDONALD" in merchant_upper:
    category = "🍔 Makanan"

elif "LOTUS" in merchant_upper or "MYDIN" in merchant_upper or "ECONSAVE" in merchant_upper:
    category = "🛒 Barang Dapur"

elif "SHOPEE" in merchant_upper or "LAZADA" in merchant_upper:
    category = "📦 Shopping"

elif "TNB" in merchant_upper:
    category = "💡 Bil Elektrik"

elif "TM" in merchant_upper or "UNIFI" in merchant_upper:
    category = "🌐 Internet"

elif "GXBANK" in merchant_upper:
    category = "🏦 Transfer"
lines = text.split("\n")

for line in lines:

    line = line.strip()

    # Cari jumlah RM
    match = re.search(r'RM\s*([\d,]+\.\d{2})', line)

    if match:
        amount = float(
            match.group(1).replace(",", "")
        )

    # Cari nama kedai
    if "Kedai" in line:
        merchant = line

print("Merchant :", merchant)
print("Amount   :", amount)

# ==========================
# SIMPAN DATABASE
# ==========================

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

await update.message.reply_text(
    f"""✅ Resit berjaya disimpan

🏪 Kedai
{merchant}

💰 Jumlah
RM{amount:.2f}

📂 Kategori
{category}
"""
)

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute("""
        SELECT
            id,
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

    text = "📒 SENARAI PERBELANJAAN\n"
    text += "━━━━━━━━━━━━━━━━━━\n\n"

    total = 0

    for row in rows:

        total += row[3]

        text += (
            f"🆔 ID : {row[0]}\n"
            f"🏪 {row[2]}\n"
            f"💰 RM{row[3]:.2f}\n"
            f"📂 {row[4]}\n"
            f"📅 {row[1]}\n"
            "──────────────────\n"
        )

    text += f"\n💵 Jumlah Belanja : RM{total:.2f}"
    text += f"\n📦 Bilangan Rekod : {len(rows)}"

    await update.message.reply_text(text)

