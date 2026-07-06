import requests

from config import OCR_API_KEY


def scan_receipt(filename):
    print("OCR Module Loaded")

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

    print("========== OCR DEBUG ==========")
    print("Status Code:", response.status_code)
    print(result)
    print("===============================")

    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    print("===== OCR TEXT =====")
    print(repr(text))
    print("====================")

    return text
