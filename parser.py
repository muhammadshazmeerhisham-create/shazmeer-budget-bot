import re
import json
import os

from merchant_db import MERCHANT_DB
from bank_db import BANK_DB


def load_custom_merchants():
    if os.path.exists("merchant_db.json"):
        with open("merchant_db.json", "r") as f:
            return json.load(f)
    return {}


def parse_receipt(text):

    merchant = "Tidak Dikenal"
    amount = 0.0
    category = "Lain-lain"

    receipt_date = "-"
    receipt_time = "-"
    reference = "-"
    recipient = "-"

    # ==========================
    # OCR CLEANING V2
    # ==========================
    
    text = text.replace("|", "I")
    text = text.replace("RM ", "RM")
    text = text.replace("RM.", "RM")
    text = text.replace("R M", "RM")
    
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    
    text = text.strip()

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    custom_db = load_custom_merchants()

    # Merchant
    for line in lines[:15]:
        upper = line.upper()

        for key, value in MERCHANT_DB.items():
            if key in upper:
                merchant = value["name"]
                category = value["category"]
                break

        if merchant != "Tidak Dikenal":
            break
            
    # Custom Merchant Database
    if merchant == "Tidak Dikenal":
    
        for line in lines[:15]:
            upper = line.upper()
    
            for key, value in custom_db.items():
                if key in upper:
                    merchant = value["name"]
                    category = value["category"]
                    break

            if merchant != "Tidak Dikenal":
                break

    # Bank / E-Wallet Detection
    if merchant == "Tidak Dikenal":

        for line in lines[:15]:
            upper = line.upper()

            for key, value in BANK_DB.items():
                if key in upper:
                    merchant = value["name"]
                    category = value["category"]
                    break

            if merchant != "Tidak Dikenal":
                break

    # Smart Detection
    if merchant == "Tidak Dikenal":

        upper_text = text.upper()

        if "GX" in upper_text and "BANK" in upper_text:
            merchant = "GXBank"
            category = "Transfer"

        elif "DUITNOW" in upper_text:
            merchant = "DuitNow"
            category = "Transfer"

        elif "TNG" in upper_text:
            merchant = "Touch 'n Go"
            category = "E-Wallet"

        elif "MAYBANK" in upper_text:
            merchant = "Maybank"
            category = "Transfer"

        elif "CIMB" in upper_text:
            merchant = "CIMB"
            category = "Transfer"

        elif "RHB" in upper_text:
            merchant = "RHB"
            category = "Transfer"

    # ==========================
    # SMART MERCHANT GUESS V2
    # ==========================
    
    if merchant == "Tidak Dikenal":
    
        blacklist = [
            "RECEIPT",
            "TAX INVOICE",
            "INVOICE",
            "PAYMENT",
            "SUCCESSFUL",
            "THANK YOU",
            "DATE",
            "TIME",
            "TOTAL",
            "AMOUNT",
            "CASHIER",
            "CHANGE",
            "DUITNOW",
            "QR",
            "RM"
        ]
    
        for line in lines[:8]:
    
            text_line = line.strip()
    
            if len(text_line) < 4:
                continue
    
            if any(word in text_line.upper() for word in blacklist):
                continue
    
            if re.search(r"\d{2,}", text_line):
                continue
    
            merchant = text_line.title()
            break

    # Auto Save Unknown Merchant
    if merchant == "Tidak Dikenal":
    
        if len(lines) > 0:
    
            new_merchant = lines[0].strip()
    
            if len(new_merchant) > 2:
    
                custom_db[new_merchant.upper()] = {
                    "name": new_merchant.title(),
                    "category": "Lain-lain"
                }
    
                with open("merchant_db.json", "w") as f:
                    json.dump(custom_db, f, indent=4)
    
                merchant = new_merchant.title()

    # ==========================
    # SMART DATE DETECTION V2
    # ==========================
    
    date_patterns = [
    
        r"(\d{4}-\d{2}-\d{2})",
    
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    
        r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{2,4})",
    
        r"(\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{2,4})",
    
        r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),\s*\d{2,4})",
    
    ]
    
    for pattern in date_patterns:
    
        match = re.search(pattern, text, re.IGNORECASE)
    
        if match:
            receipt_date = match.group(1)
            break

    # ==========================
    # SMART TIME DETECTION V2
    # ==========================
    
    time_patterns = [
    
        r"(\d{1,2}:\d{2}:\d{2})",
    
        r"(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))",
    
        r"(\d{1,2}:\d{2})",
    
    ]
    
    for pattern in time_patterns:
    
        match = re.search(pattern, text, re.IGNORECASE)
    
        if match:
    
            receipt_time = match.group(1).upper()
    
            receipt_time = receipt_time.replace("AM", " AM")
            receipt_time = receipt_time.replace("PM", " PM")
    
            receipt_time = re.sub(r"\s{2,}", " ", receipt_time)
    
            break

    # ==========================
    # SMART RECIPIENT DETECTION V2
    # ==========================
    
    recipient_patterns = [
    
        r"Recipient\s*[:\-]?\s*(.+)",
    
        r"Penerima\s*[:\-]?\s*(.+)",
    
        r"To\s*[:\-]?\s*(.+)",
    
        r"Payee\s*[:\-]?\s*(.+)",
    
        r"Receiver\s*[:\-]?\s*(.+)",
    
        r"Beneficiary\s*[:\-]?\s*(.+)",
    
    ]

    recipient_blacklist = [

        "ADDRESS",
        "ADDR",
        "LOCATION",
        "TEL",
        "PHONE",
        "TELP",
        "DESCRIPTION",
        "PRICE",
        "ITEM",
        "TOTAL",
        "SUBTOTAL",
        "CASH",
        "CHANGE",
        "THANK YOU",
        "SHOP NAME",
    
    ]
    
    for pattern in recipient_patterns:

        match = re.search(pattern, text, re.IGNORECASE)
    
        if match:
    
            candidate = match.group(1).strip()
    
            if any(word in candidate.upper() for word in recipient_blacklist):
                continue
    
            recipient = candidate
            break

    # ==========================
    # SMART RECIPIENT DETECTION V2
    # ==========================
    
    if recipient == "-":
    
        for line in lines:
    
            candidate = line.strip()
    
            upper = candidate.upper()
    
            if len(candidate) < 4:
                continue
    
            if any(word in upper for word in recipient_blacklist):
                continue
    
            if merchant.upper() in upper:
                continue
    
            if re.search(r"\d{2,}", candidate):
                continue
    
            if re.search(r"RM|TOTAL|CASH|CHANGE", upper):
                continue
    
            recipient = candidate.title()
            break

    # ==========================
    # SMART REFERENCE DETECTION V2
    # ==========================
    
    reference_patterns = [
    
        r"Reference\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Receipt\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Invoice\s*No\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Order\s*ID\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Payment\s*ID\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Transaction\s*ID\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"DuitNow\s*Ref\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"FPX\s*Ref\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Receipt\s*Reference\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Reference\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Ref\s*#?\s*([A-Za-z0-9\-]+)",
    
    ]
    
    for pattern in reference_patterns:
    
        match = re.search(pattern, text, re.IGNORECASE)
    
        if match:
    
            reference = match.group(1).strip()
    
            break

    # ==========================
    # SMART AMOUNT DETECTION V2
    # ==========================
    
   patterns = [

        # Highest Priority
        r"GRAND\s*TOTAL.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"TOTAL\s*PAYABLE.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"NET\s*TOTAL.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"TOTAL\s*DUE.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"TOTAL\s*RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"AMOUNT\s*PAID.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"AMOUNT\s*RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"PAID\s*RM?\s*(\d+(?:\.\d{1,2})?)",
    
        r"TRANSFER\s*AMOUNT.*?RM?\s*(\d+(?:\.\d{1,2})?)",
    
    ]
    
    for pattern in patterns:
    
        match = re.search(pattern, text, re.IGNORECASE)
    
        if match:
            amount = float(match.group(1))
            break

        if amount == 0:

    values = []

    for line in lines:

        upper = line.upper()

        # Abaikan line yang bukan jumlah belanja
        if any(word in upper for word in [

            "CASH",
            "CHANGE",
            "BALANCE",
            "TENDER",
            "ROUNDING",
            "DISCOUNT",
            "TEL",
            "PHONE",

        ]):
            continue

        nums = re.findall(r"\d+(?:\.\d{1,2})?", line)

        for n in nums:

            try:

                x = float(n)

                if 1 <= x <= 10000:
                    values.append(x)

            except:
                pass

    if values:

        amount = max(values)

    # ==========================
    # SMART CATEGORY DETECTION V2
    # ==========================
    
    if category == "Lain-lain":
    
        upper_text = text.upper()
    
        category_rules = {
    
            "Petrol": [
                "PETRONAS",
                "SHELL",
                "BHP",
                "CALTEX",
                "PETRON"
            ],
    
            "Makanan": [
                "KFC",
                "MCD",
                "MCDONALD",
                "BURGER KING",
                "PIZZA",
                "TEALIVE",
                "STARBUCKS"
            ],
    
            "Shopping": [
                "SHOPEE",
                "LAZADA",
                "TIKTOK SHOP"
            ],
    
            "Grocery": [
                "LOTUS",
                "LOTUSS",
                "ECONSAVE",
                "MYDIN",
                "TF VALUE",
                "99 SPEEDMART",
                "NSK"
            ],
    
            "Home": [
                "MR DIY",
                "ACE HARDWARE"
            ],
    
            "Transport": [
                "GRAB",
                "MAXIM",
                "AIRASIA RIDE"
            ],
    
            "Transfer": [
                "DUITNOW",
                "GXBANK",
                "MAYBANK",
                "CIMB",
                "RHB"
            ],
    
            "E-Wallet": [
                "TNG",
                "TOUCH N GO",
                "BOOST"
            ],
    
        }
    
        for cat, keywords in category_rules.items():
    
            if any(word in upper_text for word in keywords):
    
                category = cat
    
                break
    
    # ==========================
    # AI CONFIDENCE SCORE V1
    # ==========================
    
    confidence = 100
    
    if merchant == "Tidak Dikenal":
        confidence -= 35
    
    if amount == 0:
        confidence -= 30
    
    if receipt_date == "-":
        confidence -= 10
    
    if receipt_time == "-":
        confidence -= 10
    
    if recipient == "-":
        confidence -= 10
    
    if reference == "-":
        confidence -= 5
    
    if confidence < 0:
        confidence = 0

    # ==========================
    # AI CONFIDENCE SCORE V1
    # ==========================
    
    confidence = 100
    
    if merchant == "Tidak Dikenal":
        confidence -= 35
    
    if amount == 0:
        confidence -= 30
    
    if receipt_date == "-":
        confidence -= 10
    
    if receipt_time == "-":
        confidence -= 10
    
    if recipient == "-":
        confidence -= 10
    
    if reference == "-":
        confidence -= 5
    
    if confidence < 0:
        confidence = 0

    return {
        "merchant": merchant,
        "recipient": recipient,
        "amount": amount,
        "category": category,
        "receipt_date": receipt_date,
        "receipt_time": receipt_time,
        "reference": reference,
        "confidence": confidence,
}
