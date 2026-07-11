import time

import requests

from config import OCR_API_KEY
from logging_config import get_logger


logger = get_logger(__name__)

OCR_URL = "https://api.ocr.space/parse/image"
OCR_TIMEOUT = (5, 30)
MAX_ATTEMPTS = 3
RETRYABLE_STATUS_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}
RETRYABLE_EXCEPTIONS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ReadTimeout,
)


def scan_receipt(filename):
    logger.debug("OCR scan started")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            # Re-open the image for every attempt so multipart uploads
            # always begin at the start of the file.
            with open(filename, "rb") as image_file:
                response = requests.post(
                    OCR_URL,
                    files={"filename": image_file},
                    data={
                        "apikey": OCR_API_KEY,
                        "language": "eng",
                    },
                    timeout=OCR_TIMEOUT,
                )

        except RETRYABLE_EXCEPTIONS as error:
            if attempt == MAX_ATTEMPTS:
                raise

            next_attempt = attempt + 1
            logger.warning(
                "OCR retry attempt | Attempt=%s/%s | Exception=%s",
                next_attempt,
                MAX_ATTEMPTS,
                type(error).__name__,
            )
            time.sleep(2 ** (attempt - 1))
            continue

        if response.status_code in RETRYABLE_STATUS_CODES:
            if attempt == MAX_ATTEMPTS:
                response.raise_for_status()

            next_attempt = attempt + 1
            logger.warning(
                "OCR retry attempt | Attempt=%s/%s | HTTP status=%s",
                next_attempt,
                MAX_ATTEMPTS,
                response.status_code,
            )
            time.sleep(2 ** (attempt - 1))
            continue

        # Non-retryable HTTP errors fail immediately.
        response.raise_for_status()

        result = response.json()

        logger.debug(
            "OCR response received | Status Code: %s",
            response.status_code,
        )
        logger.debug("OCR response body: %s", result)

        parsed_results = result.get("ParsedResults")

        if not parsed_results:
            logger.warning("OCR completed with no parsed results")
            return ""

        text = parsed_results[0]["ParsedText"]

        logger.debug("OCR parsed text: %r", text)
        logger.info("OCR completed successfully")

        return text
