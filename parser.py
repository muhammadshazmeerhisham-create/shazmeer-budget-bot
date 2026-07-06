import re

from merchant_db import MERCHANT_DB
from bank_db import BANK_DB

def parse_receipt(text):

    merchant = "Tidak Dikenal"
    amount = 0.0
    category = "Lain-lain"

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

    # Total
    patterns = [
        r"GRAND\s*TOTAL.*?(\d+\.\d{2})",
        r"TOTAL.*?(\d+\.\d{2})",
        r"NET\s*TOTAL.*?(\d+\.\d{2})",
        r"AMOUNT.*?(\d+\.\d{2})",
        r"RM\s*(\d+\.\d{2})",
    ]

    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)

        if m:
            amount = float(m.group(1))
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
        "amount": amount,
        "category": category,
    }