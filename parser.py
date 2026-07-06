import re

MERCHANTS = {
    "MASLEE": "Maslee",
    "LOTUSS": "Lotus's",
    "TESCO": "Lotus's",
    "MYDIN": "Mydin",
    "99 SPEEDMART": "99 Speedmart",
    "ECONSAVE": "Econsave",
    "KK MART": "KK Mart",
    "FAMILYMART": "FamilyMart",
    "7-ELEVEN": "7-Eleven",
    "PETRONAS": "Petronas",
    "SHELL": "Shell",
    "CALTEX": "Caltex",
    "AEON": "AEON",
    "MR DIY": "MR DIY",
    "WATSONS": "Watsons",
    "GUARDIAN": "Guardian",
    "GRAB": "Grab",
    "SHOPEE": "Shopee",
    "GXBANK": "GXBank",
}

CATEGORY = {
    "Maslee": "Grocery",
    "Lotus's": "Grocery",
    "Mydin": "Grocery",
    "99 Speedmart": "Grocery",
    "Econsave": "Grocery",
    "KK Mart": "Convenience",
    "FamilyMart": "Convenience",
    "7-Eleven": "Convenience",
    "Petronas": "Fuel",
    "Shell": "Fuel",
    "Caltex": "Fuel",
    "Grab": "Transport",
    "Shopee": "Shopping",
    "Watsons": "Health",
    "Guardian": "Health",
    "MR DIY": "Home",
    "AEON": "Shopping",
    "GXBank": "Transfer",
}


def parse_receipt(text):

    merchant = "Tidak Dikenal"
    amount = 0.0
    category = "Lain-lain"

    lines = [x.strip() for x in text.splitlines() if x.strip()]

    # Merchant
    for line in lines[:15]:
        upper = line.upper()

        for key, value in MERCHANTS.items():
            if key in upper:
                merchant = value
                break

        if merchant != "Tidak Dikenal":
            break

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

    if merchant in CATEGORY:
        category = CATEGORY[merchant]

    return {
        "merchant": merchant,
        "amount": amount,
        "category": category,
    }