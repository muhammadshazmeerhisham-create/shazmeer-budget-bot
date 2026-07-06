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
# CATEGORY MAPPING
# ==========================

CATEGORY_KEYWORDS = {
    "🥛 Dairy": ["susu", "keju", "yogurt", "butter", "krim", "cheese", "milk", "cream"],
    "🍞 Bakery": ["roti", "kek", "donut", "pastry", "bread", "cake", "bun", "loaf"],
    "🥬 Vegetables": ["sayur", "lobak", "bayam", "timun", "wortel", "kentang", "kubis", "vegetable"],
    "🍎 Fruits": ["buah", "epal", "oren", "nanas", "pisang", "ceri", "strawberry", "watermelon", "fruit"],
    "🥚 Protein": ["telur", "ayam", "daging", "ikan", "udang", "tahu", "egg", "chicken", "beef", "fish"],
    "🥫 Canned": ["tin", "sardin", "sausage", "canned", "kaleng", "corned"],
    "🧴 Personal Care": ["sabun", "syampu", "ubat gigi", "toothpaste", "shampoo", "soap", "deodorant"],
    "🛁 Household": ["detergent", "tissue", "sampah", "sapu", "cloth", "bag", "plastic"],
    "🍬 Snacks": ["keropok", "coklat", "gula-gula", "chips", "biscuit", "kuki", "cookie"],
    "🥤 Beverages": ["air", "jus", "kopi", "teh", "coffee", "tea", "juice", "drink"],
}

# ==========================
# DATABASE
# ==========================

conn = sqlite3.connect("safia.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute(""" CREATE TABLE IF NOT EXISTS expenses( id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, merchant TEXT, amount REAL, category TEXT, note TEXT ) """)

cursor.execute(""" CREATE TABLE IF NOT EXISTS expense_items( id INTEGER PRIMARY KEY AUTOINCREMENT, expense_id INTEGER, item_name TEXT, item_category TEXT, quantity REAL, unit_price REAL, total_price REAL, FOREIGN KEY(expense_id) REFERENCES expenses(id) ) """)

cursor.execute(""" CREATE TABLE IF NOT EXISTS salary( id INTEGER PRIMARY KEY AUTOINCREMENT, salary_type TEXT, amount REAL ) """)

conn.commit()

# ==========================
# HELPER FUNCTIONS
# ==========================

def detect_category(item_name):
    """
    Auto-detect item category based on keywords
    Returns: category emoji + name, or ❓ Others if no match
    """
    item_lower = item_name.lower()
    
    for category, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in item_lower:
                return category
    
    return "❓ Others"

def is_valid_item_line(line):
    """
    Check if line is likely a valid item line
    Skip: metadata, headers, footers, special patterns
    """
    lower = line.lower()
    
    # Skip common non-item lines
    skip_patterns = [
        "total", "subtotal", "tax", "diskaun", "discount", "payment", "thank",
        "date", "time", "qty", "price", "item", "---", "===", "receipt",
        "invoice", "no:", "merchant", "kedai", "supermarket", "store",
        "jalan", "taman", "address", "tel:", "phone", "customer",
        "operator", "cashier", "no. rujukan", "reference", "pup", "thank you",
        "please visit", "website", "terima kasih"
    ]
    
    for pattern in skip_patterns:
        if pattern in lower:
            return False
    
    # Skip lines that are mostly numbers/special characters
    alpha_count = sum(1 for c in line if c.isalpha())
    if alpha_count < 2:
        return False
    
    return True

def parse_receipt_items(text):
    """
    Parse receipt text to extract items with quantity and price
    Expected format: ITEM_NAME | QUANTITY | PRICE
    Returns: list of (item_name, quantity, unit_price, total_price)
    """
    items = []
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    print("===== PARSING ITEMS =====")
    
    for line in lines:
        # Skip invalid lines first
        if not is_valid_item_line(line):
            print(f"⊘ Skipped: {line[:50]}")
            continue
        
        # Try to parse line with multiple number patterns
        # Pattern: ITEM_NAME | QTY | PRICE or ITEM_NAME QTY PRICE
        
        # Split by pipe first (if exists)
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                item_name = parts[0]
                try:
                    qty_match = re.search(r"[\d.]+", parts[1])
                    price_match = re.search(r"[\d.]+", parts[2])
                    
                    if qty_match and price_match:
                        qty = float(qty_match.group())
                        price = float(price_match.group())
                        
                        # Validate: qty 0.1-100, price RM0.50-RM500
                        if 0.1 <= qty <= 100 and 0.5 <= price <= 500:
                            total = qty * price
                            category = detect_category(item_name)
                            items.append((item_name, category, qty, price, total))
                            print(f"✓ {item_name} [{category}] | {qty} x RM{price:.2f} = RM{total:.2f}")
                        else:
                            print(f"⊘ Out of range: {item_name} qty={qty} price={price}")
                except Exception as e:
                    print(f"⊘ Parse error: {line[:50]} - {e}")
                    continue
        else:
            # Try pattern: NAME QTY PRICE (space separated)
            numbers = re.findall(r"[\d.]+", line)
            if len(numbers) >= 2:
                try:
                    price = float(numbers[-1])
                    qty = float(numbers[-2])
                    
                    # Validate prices and quantities
                    if not (0.1 <= qty <= 100 and 0.5 <= price <= 500):
                        print(f"⊘ Out of range: qty={qty} price={price}")
                        continue
                    
                    # Extract item name (remove numbers from end)
                    item_name = re.sub(r"[\d.\s]+$", "", line).strip()
                    
                    # Only add if item_name is reasonable length (3-50 chars, mostly letters)
                    if 3 <= len(item_name) <= 50:
                        alpha_pct = sum(1 for c in item_name if c.isalpha()) / len(item_name)
                        if alpha_pct >= 0.5:  # At least 50% letters
                            total = qty * price
                            category = detect_category(item_name)
                            items.append((item_name, category, qty, price, total))
                            print(f"✓ {item_name} [{category}] | {qty} x RM{price:.2f} = RM{total:.2f}")
                        else:
                            print(f"⊘ Too many special chars: {item_name}")
                except Exception as e:
                    print(f"⊘ Parse error: {line[:50]} - {e}")
                    continue
    
    print("==========================")
    return items

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
    
    print("OCR Exit Code:", result.get("OCRExitCode"))
    print("IsErrored:", result.get("IsErroredOnProcessing"))
    
    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    print("===== OCR RESULT =====")
    print(text)
    print("======================")

    # ==========================
    # SAFIA SMART PARSER V4
    # ==========================

    merchant = "Tidak Dikenal"
    amount = 0.0
    category = "Lain-lain"
    items = []

    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # -------------------------
    # MERCHANT
    # -------------------------

    for i, line in enumerate(lines):
        lower = line.lower()
        if lower == "recipient" and i + 1 < len(lines):
            merchant = lines[i + 1]
            break

    if merchant == "Tidak Dikenal":
        for line in lines[:5]:  # Check first 5 lines only
            if any(x in line.lower() for x in ["kedai", "supermarket", "store", "tesco", "aeon", "giant"]):
                merchant = line
                break

    # -------------------------
    # PARSE ITEMS
    # -------------------------

    items = parse_receipt_items(text)

    # -------------------------
    # CALCULATE TOTAL FROM ITEMS
    # -------------------------

    if items:
        amount = sum(total for _, _, _, _, total in items)
        print(f"Calculated total from items: RM{amount:.2f}")
    else:
        # Fallback: Find largest reasonable price
        numbers = re.findall(r"\d+\.?\d*", text)
        valid_prices = []
        for num_str in numbers:
            try:
                num = float(num_str)
                if 1 <= num <= 1000:  # Reasonable total range
                    valid_prices.append(num)
            except:
                pass
        
        if valid_prices:
            amount = max(valid_prices)
            print(f"Fallback total: RM{amount:.2f}")

    print("Merchant :", merchant)
    print("Amount   :", amount)
    print("Items    :", len(items))

    # -------------------------
    # SAVE TO DATABASE
    # -------------------------

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

    # Get the expense ID
    expense_id = cursor.lastrowid

    # Save individual items with categories
    for item_name, item_category, qty, unit_price, total_price in items:
        cursor.execute(
            """
            INSERT INTO expense_items(
                expense_id,
                item_name,
                item_category,
                quantity,
                unit_price,
                total_price
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (expense_id, item_name, item_category, qty, unit_price, total_price)
        )

    conn.commit()

    # -------------------------
    # BUILD RESPONSE MESSAGE
    # -------------------------

    message = (
        "✅ Resit berjaya disimpan\n\n"
        f"🏪 Kedai:\n{merchant}\n\n"
    )

    if items:
        message += "📦 Items:\n"
        for item_name, item_category, qty, unit_price, total_price in items:
            message += f"  {item_category} {item_name}\n"
            message += f"    {qty} x RM{unit_price:.2f} = RM{total_price:.2f}\n"
        message += "\n"
    else:
        message += "⚠️ No items detected\n\n"

    message += (
        f"💰 Jumlah:\nRM{amount:.2f}\n\n"
        f"📂 Kategori:\n{category}"
    )

    await update.message.reply_text(message)

# ==========================
# SENARAI BELANJA
# ==========================

async def list_expenses(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute(""" SELECT id, date, merchant, amount, category FROM expenses ORDER BY id DESC LIMIT 20 """)

    rows = cursor.fetchall()

    if not rows:
        await update.message.reply_text("📭 Tiada rekod lagi.")
        return

    text = "📒 SENARAI PERBELANJAAN\n\n"

    total = 0

    for row in rows:

        exp_id, date, merchant, amount, category = row
        total += amount

        text += (
            f"🏪 {merchant}\n"
            f"💰 RM{amount:.2f}\n"
            f"📂 {category}\n"
            f"📅 {date}\n"
        )

        # Get items for this expense
        cursor.execute(""" SELECT item_name, item_category, quantity, unit_price, total_price FROM expense_items WHERE expense_id = ? ORDER BY item_category """, (exp_id,))
        items = cursor.fetchall()

        if items:
            text += "  Items:\n"
            current_category = None
            for item_name, item_category, qty, unit_price, total_price in items:
                if item_category != current_category:
                    current_category = item_category
                    text += f"    {item_category}\n"
                text += f"      • {item_name}: {qty} x RM{unit_price:.2f}\n"

        text += "\n"

    text += f"💵 Jumlah Belanja : RM{total:.2f}"

    await update.message.reply_text(text)

# ==========================
# DASHBOARD
# ==========================

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):

    cursor.execute(""" SELECT IFNULL(SUM(amount),0) FROM expenses """)

    total = cursor.fetchone()[0]

    cursor.execute(""" SELECT COUNT(*) FROM expenses """)
    transaction_count = cursor.fetchone()[0]

    cursor.execute(""" SELECT COUNT(*) FROM expense_items """)
    item_count = cursor.fetchone()[0]

    # Get spending by category
    cursor.execute(""" SELECT item_category, SUM(total_price) as category_total FROM expense_items GROUP BY item_category ORDER BY category_total DESC """)
    
    category_breakdown = cursor.fetchall()

    message = (
        f"""📊 SAFIA Dashboard

💰 Jumlah Belanja
RM{total:.2f}

📊 Stats:
Transactions: {transaction_count}
Items: {item_count}

📈 Spending by Category:
"""
    )

    for cat, cat_total in category_breakdown:
        message += f"{cat} RM{cat_total:.2f}\n"

    await update.message.reply_text(message)

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
