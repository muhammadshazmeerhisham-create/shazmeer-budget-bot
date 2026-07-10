import logging


logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO
)


def get_logger(name):
    return logging.getLogger(name)
