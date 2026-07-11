import sqlite3
import time

from logging_config import get_logger


logger = get_logger(__name__)

MAX_ATTEMPTS = 3
BACKOFF_DELAYS = (0.1, 0.2)
RETRYABLE_ERROR_CODES = {
    sqlite3.SQLITE_BUSY,
    sqlite3.SQLITE_LOCKED,
}


def _create_connection():
    return sqlite3.connect("safia.db", timeout=2.0)


def _get_primary_error_code(error):
    error_code = getattr(error, "sqlite_errorcode", None)

    if error_code is None:
        return None

    return error_code & 0xFF


def _is_retryable_error(error):
    return _get_primary_error_code(error) in RETRYABLE_ERROR_CODES


def _rollback_safely(connection):
    if not connection.in_transaction:
        return

    try:
        connection.rollback()
    except Exception:
        # The rollback failure must not replace the original exception.
        logger.exception("Database rollback failed")


def _run_database_operation(operation):
    for attempt in range(1, MAX_ATTEMPTS + 1):
        connection = None
        retry_error = None

        try:
            connection = _create_connection()
            return operation(connection)

        except sqlite3.OperationalError as error:
            if connection is not None:
                _rollback_safely(connection)

            if not _is_retryable_error(error) or attempt == MAX_ATTEMPTS:
                raise

            retry_error = error

        except Exception:
            if connection is not None:
                _rollback_safely(connection)

            raise

        finally:
            if connection is not None:
                connection.close()

        error_code = getattr(retry_error, "sqlite_errorcode", None)
        error_name = getattr(
            retry_error,
            "sqlite_errorname",
            "UNKNOWN",
        )

        logger.warning(
            "Database retry attempt | Attempt=%s/%s | "
            "SQLite error=%s (%s)",
            attempt + 1,
            MAX_ATTEMPTS,
            error_name,
            error_code,
        )
        time.sleep(BACKOFF_DELAYS[attempt - 1])


def initialize_database():
    def operation(connection):
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                merchant TEXT,
                amount REAL,
                category TEXT,
                note TEXT
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS salary(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                salary_type TEXT,
                amount REAL
            )
            """
        )

        connection.commit()

    _run_database_operation(operation)


def save_expense(date, merchant, amount, category, note):
    def operation(connection):
        connection.execute(
            """
            INSERT INTO expenses
            (date, merchant, amount, category, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                date,
                merchant,
                amount,
                category,
                note,
            ),
        )
        connection.commit()

    _run_database_operation(operation)
    logger.info("Database Saved")


def get_expenses():
    def operation(connection):
        cursor = connection.execute(
            """
            SELECT date, merchant, amount, category
            FROM expenses
            ORDER BY id DESC
            """
        )
        return cursor.fetchall()

    return _run_database_operation(operation)


def get_total_expenses():
    def operation(connection):
        cursor = connection.execute(
            """
            SELECT IFNULL(SUM(amount),0)
            FROM expenses
            """
        )
        return cursor.fetchone()[0]

    return _run_database_operation(operation)
