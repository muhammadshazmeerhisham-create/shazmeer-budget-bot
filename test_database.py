import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, call, patch

import database


REAL_CONNECT = sqlite3.connect


def make_operational_error(error_code):
    error = sqlite3.OperationalError("simulated database error")
    error.sqlite_errorcode = error_code

    error_names = {
        sqlite3.SQLITE_BUSY: "SQLITE_BUSY",
        sqlite3.SQLITE_LOCKED: "SQLITE_LOCKED",
        sqlite3.SQLITE_ERROR: "SQLITE_ERROR",
        sqlite3.SQLITE_READONLY: "SQLITE_READONLY",
    }
    error.sqlite_errorname = error_names.get(
        error_code & 0xFF,
        "SQLITE_UNKNOWN",
    )

    return error


def make_mock_connection(
    *,
    execute_error=None,
    rows=None,
    total=0,
    in_transaction=False,
):
    connection = Mock()
    connection.in_transaction = in_transaction

    cursor = Mock()
    cursor.fetchall.return_value = [] if rows is None else rows
    cursor.fetchone.return_value = (total,)

    if execute_error is None:
        connection.execute.return_value = cursor
    else:
        connection.execute.side_effect = execute_error

    return connection


class CommitBusyConnection:

    def __init__(self, connection, error):
        self._connection = connection
        self._error = error
        self.rollback_called = False
        self.close_called = False

    @property
    def in_transaction(self):
        return self._connection.in_transaction

    def execute(self, sql, parameters=()):
        return self._connection.execute(sql, parameters)

    def commit(self):
        raise self._error

    def rollback(self):
        self.rollback_called = True
        self._connection.rollback()

    def close(self):
        self.close_called = True
        self._connection.close()


class DatabaseTests(unittest.TestCase):

    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.database_path = (
            Path(self.temporary_directory.name) / "test_safia.db"
        )
        self.connections = []

        self.connect_patcher = patch(
            "database.sqlite3.connect",
            side_effect=self._open_temporary_database,
        )
        self.mock_connect = self.connect_patcher.start()

    def tearDown(self):
        self.connect_patcher.stop()
        self.temporary_directory.cleanup()

    def _open_temporary_database(
        self,
        database_path,
        *,
        timeout,
    ):
        self.assertEqual(database_path, "safia.db")
        self.assertEqual(timeout, 2.0)

        connection = REAL_CONNECT(
            self.database_path,
            timeout=timeout,
        )
        self.connections.append(connection)
        return connection

    def _query_temporary_database(self, sql, parameters=()):
        connection = REAL_CONNECT(self.database_path)

        try:
            return connection.execute(sql, parameters).fetchall()
        finally:
            connection.close()

    def test_initialization_creates_exact_existing_schema(self):
        database.initialize_database()

        expenses_schema = self._query_temporary_database(
            "PRAGMA table_info(expenses)"
        )
        salary_schema = self._query_temporary_database(
            "PRAGMA table_info(salary)"
        )

        self.assertEqual(
            expenses_schema,
            [
                (0, "id", "INTEGER", 0, None, 1),
                (1, "date", "TEXT", 0, None, 0),
                (2, "merchant", "TEXT", 0, None, 0),
                (3, "amount", "REAL", 0, None, 0),
                (4, "category", "TEXT", 0, None, 0),
                (5, "note", "TEXT", 0, None, 0),
            ],
        )
        self.assertEqual(
            salary_schema,
            [
                (0, "id", "INTEGER", 0, None, 1),
                (1, "salary_type", "TEXT", 0, None, 0),
                (2, "amount", "REAL", 0, None, 0),
            ],
        )

    def test_connection_factory_uses_existing_path_and_timeout(self):
        connection = make_mock_connection()
        self.mock_connect.side_effect = [connection]

        database.get_expenses()

        self.mock_connect.assert_called_once_with(
            "safia.db",
            timeout=2.0,
        )

    def test_insert_succeeds_on_first_attempt(self):
        database.initialize_database()
        self.mock_connect.reset_mock()
        self.connections.clear()

        database.save_expense(
            "2026-07-12 10:30:00",
            "Kedai Ujian",
            12.50,
            "Makanan",
            "",
        )

        rows = self._query_temporary_database(
            """
            SELECT date, merchant, amount, category, note
            FROM expenses
            """
        )

        self.assertEqual(
            rows,
            [
                (
                    "2026-07-12 10:30:00",
                    "Kedai Ujian",
                    12.50,
                    "Makanan",
                    "",
                )
            ],
        )
        self.assertEqual(self.mock_connect.call_count, 1)

    @patch("database.time.sleep")
    def test_busy_twice_then_success_uses_exact_backoff_and_connections(
        self,
        mock_sleep,
    ):
        first_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_BUSY
            )
        )
        second_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_BUSY
            )
        )
        expected_rows = [
            ("2026-07-12", "Merchant", 8.90, "Makanan")
        ]
        third_connection = make_mock_connection(rows=expected_rows)

        self.mock_connect.side_effect = [
            first_connection,
            second_connection,
            third_connection,
        ]

        rows = database.get_expenses()

        self.assertEqual(rows, expected_rows)
        self.assertEqual(self.mock_connect.call_count, 3)
        self.assertIsNot(first_connection, second_connection)
        self.assertIsNot(second_connection, third_connection)
        self.assertTrue(first_connection.close.called)
        self.assertTrue(second_connection.close.called)
        self.assertTrue(third_connection.close.called)
        self.assertEqual(
            mock_sleep.call_args_list,
            [call(0.1), call(0.2)],
        )

    @patch("database.time.sleep")
    def test_locked_then_success(self, mock_sleep):
        locked_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_LOCKED
            )
        )
        success_connection = make_mock_connection(rows=[])

        self.mock_connect.side_effect = [
            locked_connection,
            success_connection,
        ]

        result = database.get_expenses()

        self.assertEqual(result, [])
        self.assertEqual(self.mock_connect.call_count, 2)
        mock_sleep.assert_called_once_with(0.1)

    @patch("database.time.sleep")
    def test_three_retryable_failures_propagate_final_exception(
        self,
        mock_sleep,
    ):
        first_error = make_operational_error(sqlite3.SQLITE_BUSY)
        second_error = make_operational_error(sqlite3.SQLITE_LOCKED)
        final_error = make_operational_error(sqlite3.SQLITE_BUSY)

        self.mock_connect.side_effect = [
            make_mock_connection(execute_error=first_error),
            make_mock_connection(execute_error=second_error),
            make_mock_connection(execute_error=final_error),
        ]

        with self.assertRaises(sqlite3.OperationalError) as context:
            database.get_expenses()

        self.assertIs(context.exception, final_error)
        self.assertEqual(self.mock_connect.call_count, 3)
        self.assertEqual(
            mock_sleep.call_args_list,
            [call(0.1), call(0.2)],
        )

    @patch("database.time.sleep")
    def test_connection_is_closed_before_backoff(self, mock_sleep):
        first_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_BUSY
            )
        )
        second_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_BUSY
            )
        )
        third_connection = make_mock_connection(rows=[])

        retry_connections = [
            first_connection,
            second_connection,
        ]
        sleep_calls = []

        def verify_closed_before_sleep(delay):
            connection = retry_connections[len(sleep_calls)]
            self.assertTrue(connection.close.called)
            sleep_calls.append(delay)

        mock_sleep.side_effect = verify_closed_before_sleep
        self.mock_connect.side_effect = [
            first_connection,
            second_connection,
            third_connection,
        ]

        database.get_expenses()

        self.assertEqual(sleep_calls, [0.1, 0.2])

    @patch("database.time.sleep")
    def test_rollback_occurs_before_retry_when_transaction_is_active(
        self,
        mock_sleep,
    ):
        events = []
        first_connection = make_mock_connection(
            execute_error=make_operational_error(
                sqlite3.SQLITE_BUSY
            ),
            in_transaction=True,
        )
        second_connection = make_mock_connection()

        first_connection.rollback.side_effect = lambda: events.append(
            "rollback"
        )
        first_connection.close.side_effect = lambda: events.append(
            "close"
        )
        mock_sleep.side_effect = lambda delay: events.append("sleep")

        self.mock_connect.side_effect = [
            first_connection,
            second_connection,
        ]

        database.save_expense(
            "2026-07-12 10:30:00",
            "Merchant",
            5.00,
            "Lain-lain",
            "",
        )

        self.assertEqual(
            events[:3],
            ["rollback", "close", "sleep"],
        )
        first_connection.rollback.assert_called_once_with()
        mock_sleep.assert_called_once_with(0.1)

    def test_rollback_failure_does_not_replace_original_exception(self):
        original_error = make_operational_error(
            sqlite3.SQLITE_ERROR
        )
        connection = make_mock_connection(
            execute_error=original_error,
            in_transaction=True,
        )
        connection.rollback.side_effect = RuntimeError(
            "rollback failed"
        )
        self.mock_connect.side_effect = [connection]

        with self.assertLogs("database", level="ERROR"):
            with self.assertRaises(sqlite3.OperationalError) as context:
                database.save_expense(
                    "2026-07-12 10:30:00",
                    "Merchant",
                    5.00,
                    "Lain-lain",
                    "",
                )

        self.assertIs(context.exception, original_error)
        self.assertEqual(self.mock_connect.call_count, 1)

    def test_commit_busy_followed_by_retry_stores_exactly_one_row(self):
        database.initialize_database()

        first_real_connection = REAL_CONNECT(
            self.database_path,
            timeout=2.0,
        )
        second_real_connection = REAL_CONNECT(
            self.database_path,
            timeout=2.0,
        )
        commit_error = make_operational_error(
            sqlite3.SQLITE_BUSY
        )
        busy_connection = CommitBusyConnection(
            first_real_connection,
            commit_error,
        )

        self.mock_connect.reset_mock()
        self.mock_connect.side_effect = [
            busy_connection,
            second_real_connection,
        ]

        with patch("database.time.sleep") as mock_sleep:
            database.save_expense(
                "2026-07-12 11:00:00",
                "Merchant",
                19.90,
                "Makanan",
                "",
            )

        rows = self._query_temporary_database(
            """
            SELECT date, merchant, amount, category, note
            FROM expenses
            """
        )

        self.assertTrue(busy_connection.rollback_called)
        self.assertTrue(busy_connection.close_called)
        self.assertEqual(self.mock_connect.call_count, 2)
        mock_sleep.assert_called_once_with(0.1)
        self.assertEqual(
            rows,
            [
                (
                    "2026-07-12 11:00:00",
                    "Merchant",
                    19.90,
                    "Makanan",
                    "",
                )
            ],
        )

    @patch("database.time.sleep")
    def test_non_retryable_operational_error_is_attempted_once(
        self,
        mock_sleep,
    ):
        error = make_operational_error(sqlite3.SQLITE_ERROR)
        connection = make_mock_connection(execute_error=error)
        self.mock_connect.side_effect = [connection]

        with self.assertRaises(sqlite3.OperationalError) as context:
            database.get_expenses()

        self.assertIs(context.exception, error)
        self.assertEqual(self.mock_connect.call_count, 1)
        self.assertTrue(connection.close.called)
        mock_sleep.assert_not_called()

    @patch("database.time.sleep")
    def test_operational_error_without_code_is_not_retried(
        self,
        mock_sleep,
    ):
        error = sqlite3.OperationalError("missing error code")
        connection = make_mock_connection(execute_error=error)
        self.mock_connect.side_effect = [connection]

        with self.assertRaises(sqlite3.OperationalError) as context:
            database.get_expenses()

        self.assertIs(context.exception, error)
        self.assertEqual(self.mock_connect.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("database.time.sleep")
    def test_integrity_error_is_not_retried(self, mock_sleep):
        error = sqlite3.IntegrityError("constraint failed")
        connection = make_mock_connection(execute_error=error)
        self.mock_connect.side_effect = [connection]

        with self.assertRaises(sqlite3.IntegrityError) as context:
            database.save_expense(
                "2026-07-12 10:30:00",
                "Merchant",
                5.00,
                "Lain-lain",
                "",
            )

        self.assertIs(context.exception, error)
        self.assertEqual(self.mock_connect.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("database.time.sleep")
    def test_programming_error_is_not_retried(self, mock_sleep):
        error = sqlite3.ProgrammingError("invalid operation")
        connection = make_mock_connection(execute_error=error)
        self.mock_connect.side_effect = [connection]

        with self.assertRaises(sqlite3.ProgrammingError) as context:
            database.get_expenses()

        self.assertIs(context.exception, error)
        self.assertEqual(self.mock_connect.call_count, 1)
        mock_sleep.assert_not_called()

    def test_get_expenses_preserves_fields_and_descending_order(self):
        database.initialize_database()

        database.save_expense(
            "2026-07-12 09:00:00",
            "First Merchant",
            10.00,
            "Makanan",
            "first note",
        )
        database.save_expense(
            "2026-07-12 10:00:00",
            "Second Merchant",
            20.00,
            "Pengangkutan",
            "second note",
        )

        rows = database.get_expenses()

        self.assertEqual(
            rows,
            [
                (
                    "2026-07-12 10:00:00",
                    "Second Merchant",
                    20.00,
                    "Pengangkutan",
                ),
                (
                    "2026-07-12 09:00:00",
                    "First Merchant",
                    10.00,
                    "Makanan",
                ),
            ],
        )

    def test_get_total_expenses_preserves_empty_and_populated_values(
        self,
    ):
        database.initialize_database()

        empty_total = database.get_total_expenses()

        database.save_expense(
            "2026-07-12 09:00:00",
            "First Merchant",
            12.50,
            "Makanan",
            "",
        )
        database.save_expense(
            "2026-07-12 10:00:00",
            "Second Merchant",
            7.50,
            "Makanan",
            "",
        )

        populated_total = database.get_total_expenses()

        self.assertEqual(empty_total, 0)
        self.assertEqual(populated_total, 20.0)


if __name__ == "__main__":
    unittest.main()
