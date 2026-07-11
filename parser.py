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
        "Transaction No",
        "Transaction No.",
        "Transaction Number",
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
        "Date & Time",
        "Transaction Date & Time",
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


MAYBANK_SCAN_PAY_INVALID_NAMES = {
    "NAME",
    "MERCHANT",
    "MERCHANT NAME",
    "MERCHANT ACCOUNT NUMBER",
    "RECIPIENT",
    "RECIPIENT NAME",
    "RECIPIENT ACCOUNT NUMBER",
    "ACCOUNT NUMBER",
    "AMOUNT",
    "REFERENCE",
    "REFERENCE ID",
    "SUCCESSFUL",
}


MAYBANK_SCAN_PAY_REFERENCE_SCAN_LIMIT = 4


MAYBANK_SCAN_PAY_REFERENCE_LABELS = (
    "MERCHANT ACCOUNT NUMBER",
    "RECIPIENT ACCOUNT NUMBER",
    "REFERENCE ID",
    "MERCHANT NAME",
    "RECIPIENT NAME",
    "ACCOUNT NUMBER",
    "DATE & TIME",
    "REFERENCE",
    "MERCHANT",
    "RECIPIENT",
    "SUCCESSFUL",
    "AMOUNT",
    "DATE",
    "TIME",
    "NAME",
)


MAYBANK_SCAN_PAY_COMPACT_TIME_PATTERN = (
    r"(?<![A-Za-z0-9])(\d{3,4})\s+(AM|PM)\b"
)


def _is_valid_maybank_scan_pay_name(value):
    if not value:
        return False

    candidate = value.strip()

    if not candidate:
        return False

    normalized_label = re.sub(
        r"(?:\s*[:\-]\s*)+$",
        "",
        candidate,
    ).strip().upper()

    if normalized_label in MAYBANK_SCAN_PAY_INVALID_NAMES:
        return False

    if any(
        re.match(
            rf"^{re.escape(label)}\s*[:\-]",
            candidate,
            re.IGNORECASE,
        )
        for label in MAYBANK_SCAN_PAY_INVALID_NAMES
    ):
        return False

    known_label_patterns = (
        r"^(?:(?:MERCHANT|RECIPIENT)\s+)?"
        r"ACCOUNT NUMBER\s+\d[\d\s\-]*$",
        r"^AMOUNT\s+(?:RM\s*)?"
        r"\d+(?:[.,]\d{1,2})?$",
        r"^REFERENCE(?:\s+ID)?\s+"
        r"(?=[A-Za-z0-9\-]*\d)[A-Za-z0-9\-]+$",
    )

    if any(
        re.match(pattern, candidate, re.IGNORECASE)
        for pattern in known_label_patterns
    ):
        return False

    if re.fullmatch(
        r"(?:RM\s*)?[\d\s.,/\-]+",
        candidate,
        re.IGNORECASE,
    ):
        return False

    return True


def extract_maybank_scan_pay_name(lines, name_type):
    full_label = f"{name_type} Name"

    for index, line in enumerate(lines):
        current = line.strip()

        name_match = re.match(
            rf"^{re.escape(full_label)}"
            r"(?:$|(?:\s*[:\-]\s*|\s+)(.*)$)",
            current,
            re.IGNORECASE,
        )

        # Match the full label before checking its split OCR form.
        if name_match:
            inline_value = (
                name_match.group(1) or ""
            ).strip()

            if _is_valid_maybank_scan_pay_name(
                inline_value
            ):
                return inline_value

            if inline_value:
                continue

            next_index = index + 1

            while next_index < len(lines):
                candidate = lines[next_index].strip()

                if candidate:
                    if _is_valid_maybank_scan_pay_name(
                        candidate
                    ):
                        return candidate

                    break

                next_index += 1

            continue

        if current.upper() != name_type.upper():
            continue

        next_index = index + 1

        while (
            next_index < len(lines)
            and not lines[next_index].strip()
        ):
            next_index += 1

        if next_index >= len(lines):
            continue

        name_label = lines[next_index].strip()

        if not re.fullmatch(
            r"Name\s*[:\-]?",
            name_label,
            re.IGNORECASE,
        ):
            continue

        next_index += 1

        while next_index < len(lines):
            candidate = lines[next_index].strip()

            if not candidate:
                next_index += 1
                continue

            if _is_valid_maybank_scan_pay_name(candidate):
                return candidate

            break

    return None


def _is_maybank_scan_pay_reference_label(value):
    upper = value.strip().upper()

    for label in MAYBANK_SCAN_PAY_REFERENCE_LABELS:
        if upper == label:
            return True

        if re.match(
            rf"^{re.escape(label)}(?:\s*[:\-]\s*|\s+).+$",
            upper,
        ):
            return True

    return False


def _looks_like_maybank_scan_pay_date_time(value):
    date_time_patterns = [
        *UNIVERSAL_DATE_PATTERNS,
        r"\b\d{1,2}:\d{2}(?::\d{2})?"
        r"\s*(?:AM|PM)?\b",
        MAYBANK_SCAN_PAY_COMPACT_TIME_PATTERN,
    ]

    return any(
        re.search(pattern, value, re.IGNORECASE)
        for pattern in date_time_patterns
    )


def _is_valid_maybank_scan_pay_reference(value):
    if not value:
        return False

    candidate = value.strip()

    if not candidate:
        return False

    if _is_maybank_scan_pay_reference_label(candidate):
        return False

    if _looks_like_maybank_scan_pay_date_time(candidate):
        return False

    if not re.fullmatch(r"[A-Za-z0-9\-]+", candidate):
        return False

    if not re.search(r"[A-Za-z]", candidate):
        return False

    if not re.search(r"\d", candidate):
        return False

    return True


def extract_maybank_scan_pay_reference(lines):
    for index, line in enumerate(lines):
        current = line.strip()

        reference_match = re.match(
            r"^Reference\s+ID"
            r"(?:$|(?:\s*[:\-]\s*|\s+)(.*)$)",
            current,
            re.IGNORECASE,
        )

        if not reference_match:
            continue

        inline_value = (
            reference_match.group(1) or ""
        ).strip()

        if _is_valid_maybank_scan_pay_reference(inline_value):
            return inline_value

        checked_lines = 0

        for following_line in lines[index + 1:]:
            candidate = following_line.strip()

            if not candidate:
                continue

            checked_lines += 1

            if checked_lines > MAYBANK_SCAN_PAY_REFERENCE_SCAN_LIMIT:
                break

            if _is_valid_maybank_scan_pay_reference(candidate):
                return candidate

    return None


def extract_maybank_scan_pay_compact_time(text):
    for match in re.finditer(
        MAYBANK_SCAN_PAY_COMPACT_TIME_PATTERN,
        text,
        re.IGNORECASE,
    ):
        digits = match.group(1)
        period = match.group(2).upper()

        if len(digits) == 3:
            hour = int(digits[0])
        else:
            hour = int(digits[:2])

        minute = int(digits[-2:])

        if 1 <= hour <= 12 and 0 <= minute <= 59:
            return f"{hour}:{minute:02d} {period}"

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


def is_touch_n_go_receipt(text):
    """Return True for common Touch 'n Go eWallet OCR spellings."""

    upper = text.upper()

    return any(marker in upper for marker in [
        "TOUCH 'N GO",
        "TOUCH N GO",
        "TNG EWALLET",
        "TNG E-WALLET",
    ])

# ==========================
# UNIVERSAL VALIDATION ENGINE V1
# ==========================

def is_invalid_value(value, invalid_words):

    if not value:
        return True

    upper = value.upper().strip()

    return upper in [word.upper() for word in invalid_words]


def is_person_name(name):

    

    if not name:
        return False

    upper = name.upper()

    person_keywords = [
        " BIN ",
        " BINTI ",
        " A/L ",
        " A/P "
    ]

    company_keywords = [
        "SDN",
        "BHD",
        "ENTERPRISE",
        "TRADING",
        "STORE",
        "MART",
        "CAFE",
        "RESTAURANT",
        "RESTORAN",
        "HOTEL",
        "PHARMACY",
        "DIY",
        "7-ELEVEN",
        "TEALIVE",
        "LOTUS"
    ]

    for keyword in company_keywords:
        if keyword in upper:
            return False

    for keyword in person_keywords:
        if keyword in upper:
            return True

    return False

    if not value:
        return True

    upper = value.upper().strip()

    return upper in [word.upper() for word in invalid_words]

# ==========================
# BANK TRANSFER PARSER V1
# ==========================

def parse_bank_transfer(lines):

    receipt_date = "-"
    receipt_time = "-"
    confidence = 100

    recipient = get_value_after_label(
        
        lines,
        UNIVERSAL_LABELS["merchant"]
    )

    reference = get_value_after_label(
        lines,
        UNIVERSAL_LABELS["reference"]
    )

    amount = get_value_after_label(
        lines,
        UNIVERSAL_LABELS["amount"]
    )

    return {
    "merchant": "Maybank Transfer",
    "recipient": recipient if recipient else "-",
    "amount": amount,
    "category": "Transfer",
    "receipt_date": receipt_date,
    "receipt_time": receipt_time,
    "reference": reference,
    "confidence": confidence,
    }


def clean_ocr_text(text):
    text = text.replace("|", "I")
    text = text.replace("RM ", "RM")
    text = text.replace("RM.", "RM")
    text = text.replace("R M", "RM")

    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)

    return text.strip()


def find_merchant_in_database(lines, database):
    for line in lines[:15]:
        upper = line.upper()

        for key, value in database.items():
            if key in upper:
                return value["name"], value["category"]

    return None


def find_first_pattern(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)

        if match:
            return match

    return None

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
    
    text = clean_ocr_text(text)

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    transaction_type = detect_transaction_type(text)

    if transaction_type == "BANK_TRANSFER":
        return parse_bank_transfer(lines)

    normalized_upper_text = text.upper()

    is_maybank_scan_pay = (
        transaction_type == "QR_PAYMENT"
        and "MAYBANK" in normalized_upper_text
        and "SCAN & PAY" in normalized_upper_text
    )

    maybank_scan_pay_merchant_name = None
    maybank_scan_pay_recipient_name = None
    maybank_scan_pay_reference = None

    if is_maybank_scan_pay:
        maybank_scan_pay_merchant_name = (
            extract_maybank_scan_pay_name(lines, "Merchant")
        )
        maybank_scan_pay_recipient_name = (
            extract_maybank_scan_pay_name(lines, "Recipient")
        )
        maybank_scan_pay_reference = (
            extract_maybank_scan_pay_reference(lines)
        )

        if (
            maybank_scan_pay_merchant_name
            or maybank_scan_pay_recipient_name
        ):
            merchant = (
                maybank_scan_pay_merchant_name
                or maybank_scan_pay_recipient_name
            )
            recipient = (
                maybank_scan_pay_recipient_name
                or maybank_scan_pay_merchant_name
            )
            category = "QR Payment"

    custom_db = load_custom_merchants()

    # TNG receipts may use a merchant label for the payee.  Keep that
    # merchant name, but consistently classify the payment method.
    is_tng_receipt = is_touch_n_go_receipt(text)

# ==========================
# UNIVERSAL MERCHANT LABEL V4
# ==========================

    merchant_from_label = get_value_after_label(
        lines,
        UNIVERSAL_LABELS["merchant"]
    )
    
    if merchant_from_label:

        merchant = merchant_from_label.strip()

        if is_tng_receipt:
            category = "E-Wallet"

        if is_person_name(merchant):

            recipient = merchant
            merchant = "Maybank QR"
            category = "Transfer"

    else:

        category = "Lain-lain"
        
        # Merchant
        if merchant == "Tidak Dikenal":
            database_match = find_merchant_in_database(lines, MERCHANT_DB)

            if database_match:
                merchant, category = database_match
            
    # Custom Merchant Database
    if merchant == "Tidak Dikenal":
    
        database_match = find_merchant_in_database(lines, custom_db)

        if database_match:
            merchant, category = database_match

    # Bank / E-Wallet Detection
    if merchant == "Tidak Dikenal":

        database_match = find_merchant_in_database(lines, BANK_DB)

        if database_match:
            merchant, category = database_match

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
    
    receipt_date = get_value_after_label(
        lines,
        [
            "Transaction Date",
            "Date",
            "Payment Date",
            "Transfer Date",
            "Date & Time",
            "Transaction Date & Time",
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
    
    if not receipt_date or receipt_date == "-":
        match = find_first_pattern(date_patterns, text)

        if match:
            receipt_date = match.group(1)

    if is_maybank_scan_pay and not receipt_date:
        receipt_date = "-"

    # ==========================
    # SMART TIME DETECTION V2
    # ==========================
    
    time_patterns = [
    
        r"(\d{1,2}:\d{2}:\d{2})",
    
        r"(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm))",
    
        r"(\d{1,2}:\d{2})",
    
    ]
    
    match = find_first_pattern(time_patterns, text)

    if match:
        receipt_time = match.group(1).upper()
        receipt_time = receipt_time.replace("AM", " AM")
        receipt_time = receipt_time.replace("PM", " PM")
        receipt_time = re.sub(r"\s{2,}", " ", receipt_time)

    if is_maybank_scan_pay and receipt_time == "-":
        compact_time = extract_maybank_scan_pay_compact_time(text)

        if compact_time:
            receipt_time = compact_time

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
    
    if not recipient or recipient == "-":
    
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
    
    if not recipient or recipient == "-":

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

    # Preserve confirmed Maybank Scan & Pay values after all generic
    # merchant and recipient fallbacks have completed.
    if is_maybank_scan_pay:
        merchant = (
            maybank_scan_pay_merchant_name
            or maybank_scan_pay_recipient_name
            or "Tidak Dikenal"
        )
        recipient = (
            maybank_scan_pay_recipient_name
            or maybank_scan_pay_merchant_name
            or "-"
        )
        category = "QR Payment"

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
            "Transaction No",
            "Transaction No.",
            "Transaction Number",
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

        r"Transaction\s*(?:No\.?|Number)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"DuitNow\s*Ref\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"FPX\s*Ref\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Receipt\s*Reference\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Reference\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    
        r"Ref\s*#?\s*([A-Za-z0-9\-]+)",
    
    ]
    
    if not reference or reference == "-":
        match = find_first_pattern(reference_patterns, text)

        if match:
            reference = match.group(1).strip()

    if is_maybank_scan_pay:
        reference = maybank_scan_pay_reference or "-"

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
    
    match = find_first_pattern(patterns, text)

    if match:
        amount = float(match.group(1))

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

            # Hanya pertimbangkan nilai berbentuk mata wang atau nilai perpuluhan.
            # Ini mengelakkan nombor telefon, rujukan dan tahun OCR dipilih
            # sebagai jumlah belanja.
            nums = re.findall(
                r"(?:RM\s*)?(\d+\.\d{1,2})\b",
                line,
                re.IGNORECASE
            )

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
