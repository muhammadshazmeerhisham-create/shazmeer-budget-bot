import requests

from config import OCR_API_KEY
from logging_config import get_logger


logger = get_logger(__name__)


def scan_receipt(filename):
    logger.info("OCR Module Loaded")

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

    logger.debug("OCR response received | Status Code: %s", response.status_code)
    logger.debug("OCR response body: %s", result)

    text = ""

    if result.get("ParsedResults"):
        text = result["ParsedResults"][0]["ParsedText"]

    logger.debug("OCR parsed text: %r", text)

    return text
