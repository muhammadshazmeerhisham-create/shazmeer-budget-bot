import re

from merchant_db import MERCHANT_DB
from bank_db import BANK_DB

def parse_receipt(text):

    merchant = "Tidak Dikenal"
    amount = 0.0
    category = "Lain-lain"
    
    receipt_date = "-"
    receipt_time = "-"
    reference = "-"
    recipient = "-"

    lines = [x.strip() for x in text.splitlines() if x.strip()]

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

    # Date Detection
    date_patterns = [
        r"(\d{2}/\d{2}/\d{2,4})",
        r"(\d{2}-\d{2}-\d{2,4})",
    ]

    for p in date_patterns:
        m = re.search(p, text)
        if m:
            receipt_date = m.group(1)
            break

    # Time Detection
    time_patterns = [
        r"(\d{2}:\d{2}:\d{2})",
        r"(\d{2}:\d{2})",
    ]

    for p in time_patterns:
        m = re.search(p, text)
        if m:
            receipt_time = m.group(1)
            break

    # Recipient Detection
    recipient_patterns = [
        r"Recipient\s*[:\-]?\s*(.+)",
        r"Penerima\s*[:\-]?\s*(.+)",
    ]

    for pattern in recipient_patterns:
        match = re.search(pattern, text,       re.IGNORECASE)
        if match:
            recipient = match.group(1).strip()
            break

    # Invoice Detection
    reference_patterns = [

    r"Invoice\s*No\.?\s*[: ]*\s*([A-Za-z0-9]+)",

    r"Receipt\s*No\.?\s*[: ]*\s*([A-Za-z0-9]+)",

    r"Ref\s*#?\s*([A-Za-z0-9]+)",

   r"Transaction\s*ID\s*[: ]*\s*([A-Za-z0-9]+)",

    ]

    # Reference Detection
    reference_patterns = [
       r"Ref\s*#?\s*([A-Za-z0-9]+)",
       r"Reference\s*[:\-]?\s*([A-Za-z0-9]+)",
       r"Receipt\s*reference\s*[:\-]?\s*([A-Za-z0-9]+)",
       r"Transaction\s*ID\s*[:\-]?\s*([A-Za-z0-9]+)",
]

    for pattern in reference_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            reference =match.group(1).strip()
            break

    # Total
    patterns = [
        r"GRAND\s*TOTAL\s*[: ]*RM?\s*(\d+\.\d{2})",
        r"TOTAL\s*[: ]*RM?\s*(\d+\.\d{2})",
        r"SUB\s*TOTAL\s*[: ]*RM?\s*(\d+\.\d{2})",
        r"AMOUNT\s*PAID\s*[: ]*RM?\s*(\d+\.\d{2})",
        r"TENDER\s*[: ]*RM?\s*(\d+\.\d{2})",
        r"BALANCE\s*[: ]*RM?\s*(\d+\.\d{2})",
    ]

    for line in reversed(lines):
        for p in patterns:
            m = re.search(p, line, re.IGNORECASE)

            if m:
                amount = float(m.group(1))
                break

    if amount > 0:
        break

    if amount == 0:
        numbers = re.findall(r"\d+\.\d{2}", text)

        values = []

        for n in numbers:
            try:
                x = float(n)

                if 1 <= x <= 10000:
                values.append(x)
            except:
                pass

        if values:
            amount = max(values)

    return {
        "merchant": merchant,
        "recipient": recipient,
        "amount": amount,
        "category": category,
        "receipt_date": receipt_date,
        "receipt_time": receipt_time,
        "reference": reference,
    }
