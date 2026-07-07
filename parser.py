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

# ==========================
# UNIVERSAL LABEL DETECTION ENGINE V1
# ==========================

# ==========================
# UNIVERSAL LABEL DATABASE V1
# ==========================

UNIVERSAL_LABELS = {

    "merchant": [

        "Merchant Name",
        "Merchant",
        "Store Name",
        "Business Name",
        "Shop Name",
        "Seller",
        "Outlet",
    ],

    "recipient": [

        "Beneficiary",
        "Beneficiary Name",
        "Recipient",
        "Receiver",
        "Payee",
        "To",
        "Penerima",
    ],

    "reference": [

        "Reference",
        "Reference ID",
        "Reference No",
        "Receipt Reference",
        "Transaction ID",
        "Payment ID",
        "Order ID",
        "FPX Ref",
        "DuitNow Ref",
    ],

    "date": [

        "Date",
        "Transaction Date",
        "Payment Date",
        "Transfer Date",
        "Tarikh",
        "Tarikh Transaksi",
    ],

    "time": [

        "Time",
        "Transaction Time",
        "Payment Time",
        "Transfer Time",
        "Masa",
    ]
}

# ==========================
# UNIVERSAL DATE PATTERNS V1
# ==========================

UNIVERSAL_DATE_PATTERNS = [

    r"(\d{4}-\d{2}-\d{2})",

    r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",

    r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{2,4})",

    r"(\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{2,4})",

    r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{2,4},\s*\d{1,2}:\d{2}\s?(?:AM|PM))",

    r"(\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{2,4},\s*\d{1,2}:\d{2}\s?(?:AM|PM))",
]

def get_value_after_label(lines, labels):

# ==========================
# UNIVERSAL DETECTION ENGINE V1
# ==========================

def get_value_after_label(lines, labels):
    """
    Cari nilai selepas sesuatu label.

    Contoh:

    Beneficiary Name
    MUHAMAD RIDHA BIN MD

    Return:
    MUHAMAD RIDHA BIN MD
    """

    if isinstance(labels, str):
        labels = [labels]

    labels = [label.upper().strip() for label in labels]

    for index, line in enumerate(lines):

        current = line.strip().upper()

        if current in labels:

            next_index = index + 1

            while next_index < len(lines):

                value = lines[next_index].strip()

                if value:
                    return value

                next_index += 1

    return None


def detect_by_label(lines, labels):

    value = get_value_after_label(lines, labels)

    if value:
        return value.strip()

    return "-"

# ==========================
# UNIVERSAL TRANSACTION TYPE V1
# ==========================

def detect_transaction_type(text):

    upper = text.upper()

    # QR Payment
    if (
        "SCAN & PAY" in upper
        or "DUITNOW QR" in upper
        or "QR PAYMENT" in upper
        or "MERCHANT NAME" in upper
    ):
        return "QR_PAYMENT"

    # Bank Transfer
    if (
        "BENEFICIARY" in upper
        or "TRANSFER SUCCESSFUL" in upper
        or "TRANSFER DETAILS" in upper
    ):
        return "BANK_TRANSFER"

    # Retail Receipt
    if (
        "TAX INVOICE" in upper
        or "RECEIPT" in upper
        or "CHANGE" in upper
        or "CASH" in upper
    ):
        return "RETAIL_RECEIPT"

    # E-Wallet
    if (
        "TOUCH 'N GO" in upper
        or "TNG EWALLET" in upper
        or "BOOST" in upper
        or "GRABPAY" in upper
        or "SHOPEEPAY" in upper
    ):
        return "E_WALLET"

    # Marketplace
    if (
        "SHOPEE" in upper
        or "LAZADA" in upper
    ):
        return "MARKETPLACE"

    return "UNKNOWN"

# ==========================
# UNIVERSAL VALIDATION ENGINE V1
# ==========================

def is_invalid_value(value, invalid_words):

    if not value:
        return True

    upper = value.upper().strip()

    return upper in [word.upper() for word in invalid_words]

def parse_receipt(text):

    transaction_type = detect_transaction_type(text)

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

    transaction_type = detect_transaction_type(text)

    custom_db = load_custom_merchants()

# ==========================
# UNIVERSAL MERCHANT LABEL V4
# ==========================

merchant_from_label = get_value_after_label(
    lines,
    UNIVERSAL_LABELS["merchant"]
)

if merchant_from_label:

    merchant = merchant_from_label.strip()

    category = "Lain-lain"
    
    # Merchant
    if merchant == "Tidak Dikenal":
    
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

    # ==========================
    # UNIVERSAL LABEL DETECTION V4
    # ==========================
    
    # ==========================
    # UNIVERSAL LABEL DETECTION V4
    # ==========================
    
    receipt_date = get_value_after_label(
        lines,
        [
            "Transaction Date",
            "Date",
            "Payment Date",
            "Transfer Date",
            "Tarikh",
            "Tarikh Transaksi"
        ]
    )
    
    # Validation
    if receipt_date:
    
        if not re.search(
            r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{2,4}"
            r"|"
            r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
            r"|"
            r"\d{4}-\d{2}-\d{2}",
            receipt_date,
            re.IGNORECASE
        ):
            receipt_date = "-"
    
    date_patterns = [
    
        r"(\d{4}-\d{2}-\d{2})",
    
        r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    
        r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s\d{2,4})",
    
        r"(\d{1,2}\s(?:January|February|March|April|May|June|July|August|September|October|November|December)\s\d{2,4})",
    
        r"(\d{1,2}\s(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),\s*\d{2,4})",
    
    ]
    
    if receipt_date == "-":
    
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

    # ==========================
    # UNIVERSAL LABEL DETECTION V4
    # ==========================
    
    recipient = get_value_after_label(
        lines,
        [
            "Beneficiary Name",
            "Beneficiary",
            "Recipient",
            "Receiver",
            "Payee",
            "Penerima",
            "To"
        ]
    )
    
    # Validation
    if recipient:
    
        upper = recipient.upper()
    
        if (
            "REFERENCE" in upper
            or "REFERENCE ID" in upper
            or "TRANSACTION" in upper
            or "DATE" in upper
            or "TIME" in upper
        ):
            recipient = "-"
    # ==========================
    # QR PAYMENT RECIPIENT V4
    # ==========================
    
    if recipient == "-":
    
        qr_recipient = get_value_after_label(
            lines,
            UNIVERSAL_LABELS["merchant"]
        )
    
        if qr_recipient:
    
            recipient = qr_recipient.strip()
    
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
    
    if recipient == "-":

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

    # ==========================
    # UNIVERSAL LABEL DETECTION V4
    # ==========================
    
    reference = get_value_after_label(
        lines,
        [
            "Reference ID",
            "Reference No",
            "Reference",
            "Receipt Reference",
            "Transaction ID",
            "Payment ID",
            "Order ID",
            "FPX Ref",
            "DuitNow Ref"
        ]
    )
    
    # Validation
    if reference:
    
        upper = reference.upper()
    
        invalid_values = [
            "ID",
            "REFERENCE",
            "REFERENCE ID",
            "REFERENCE NO",
            "TRANSACTION",
            "PAYMENT",
            "ORDER"
        ]
    
        if upper in invalid_values:
            reference = "-"

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
    
    if reference == "-":

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
