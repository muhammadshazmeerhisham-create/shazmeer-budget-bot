import http.client
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import database
from health import (
    create_health_server,
    run_health_server,
)


FAKE_BOT_TOKEN = (
    "123456789:"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijk"
)
FAKE_OCR_API_KEY = "test-ocr-key"


with patch.object(database, "initialize_database"):
    with patch.dict(
        os.environ,
        {
            "BOT_TOKEN": FAKE_BOT_TOKEN,
            "OCR_API_KEY": FAKE_OCR_API_KEY,
        },
    ):
        import bot


class HealthEndpointTests(unittest.TestCase):

    def setUp(self):
        self.readiness_callback = Mock(return_value=True)
        self.server = create_health_server(
            "127.0.0.1",
            0,
            self.readiness_callback,
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()

        self.host, self.port = self.server.server_address

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _request(self, path):
        connection = http.client.HTTPConnection(
            self.host,
            self.port,
            timeout=2,
        )

        try:
            connection.request("GET", path)
            response = connection.getresponse()
            body = response.read()

            return response, body
        finally:
            connection.close()

    def test_root_returns_exact_legacy_response(self):
        response, body = self._request("/")

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"SAFIA is running!")

    def test_ping_returns_ok(self):
        response, body = self._request("/ping")

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"ok")

    def test_status_returns_200_when_callback_returns_true(self):
        self.readiness_callback.return_value = True

        response, body = self._request("/status")

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"ok")
        self.readiness_callback.assert_called_once_with()

    def test_status_returns_503_when_callback_returns_false(self):
        self.readiness_callback.return_value = False

        response, body = self._request("/status")

        self.assertEqual(response.status, 503)
        self.assertEqual(body, b"unavailable")
        self.readiness_callback.assert_called_once_with()

    def test_callback_exception_is_safely_logged(self):
        secret_values = [
            "telegram-token-value",
            "ocr-api-key-value",
            "9876.54",
            "C:\\private\\safia.db",
        ]
        exception_message = " | ".join(secret_values)
        self.readiness_callback.side_effect = RuntimeError(
            exception_message
        )

        with self.assertLogs("health", level="ERROR") as logs:
            response, body = self._request("/status")

        self.assertEqual(response.status, 503)
        self.assertEqual(body, b"unavailable")

        decoded_body = body.decode("utf-8")
        combined_logs = "\n".join(logs.output)

        self.assertIn("RuntimeError", combined_logs)
        self.assertNotIn(exception_message, combined_logs)
        self.assertNotIn(exception_message, decoded_body)
        self.assertNotIn("Traceback", combined_logs)

        for secret_value in secret_values:
            self.assertNotIn(secret_value, combined_logs)
            self.assertNotIn(secret_value, decoded_body)

    def test_unknown_route_returns_404(self):
        response, body = self._request("/unknown")

        self.assertEqual(response.status, 404)
        self.assertEqual(body, b"not found")

    def test_query_string_does_not_change_route_matching(self):
        response, body = self._request(
            "/ping?token=secret-query-value"
        )

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"ok")

    def test_response_headers_are_correct(self):
        response, body = self._request("/ping")

        self.assertEqual(
            response.getheader("Content-Type"),
            "text/plain; charset=utf-8",
        )
        self.assertEqual(
            response.getheader("Cache-Control"),
            "no-store",
        )
        self.assertEqual(
            response.getheader("Content-Length"),
            str(len(body)),
        )

    def test_content_length_matches_encoded_body(self):
        response, body = self._request("/")

        expected_body = "SAFIA is running!".encode("utf-8")

        self.assertEqual(body, expected_body)
        self.assertEqual(
            int(response.getheader("Content-Length")),
            len(expected_body),
        )

    def test_secret_query_string_is_not_logged(self):
        secret_value = "secret-query-value"

        with self.assertLogs("health", level="DEBUG") as logs:
            response, body = self._request(
                f"/ping?token={secret_value}"
            )

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"ok")

        combined_logs = "\n".join(logs.output)

        self.assertNotIn(secret_value, combined_logs)
        self.assertIn("/ping", combined_logs)

    def test_readiness_response_never_exposes_sensitive_values(self):
        sensitive_values = [
            FAKE_BOT_TOKEN,
            FAKE_OCR_API_KEY,
            "12345.67",
            "C:\\users\\private\\safia.db",
        ]
        self.readiness_callback.return_value = {
            "values": sensitive_values
        }

        response, body = self._request("/status")

        self.assertEqual(response.status, 200)
        self.assertEqual(body, b"ok")

        decoded_body = body.decode("utf-8")

        for sensitive_value in sensitive_values:
            self.assertNotIn(sensitive_value, decoded_body)


class HealthServerTests(unittest.TestCase):

    def test_factory_returns_threading_http_server(self):
        from http.server import ThreadingHTTPServer

        server = create_health_server(
            "127.0.0.1",
            0,
            lambda: True,
        )

        try:
            self.assertIsInstance(server, ThreadingHTTPServer)
        finally:
            server.server_close()

    def test_server_runner_logs_and_reraises_crash(self):
        server = Mock()
        server.serve_forever.side_effect = RuntimeError(
            "server crashed"
        )

        with self.assertLogs("health", level="ERROR"):
            with self.assertRaises(RuntimeError):
                run_health_server(server)


class BotHealthConfigurationTests(unittest.TestCase):

    @patch("bot.create_health_server")
    def test_valid_port_is_used(self, mock_create_server):
        expected_server = Mock()
        mock_create_server.return_value = expected_server

        with patch.dict(
            bot.os.environ,
            {"PORT": "12345"},
            clear=True,
        ):
            result = bot.create_configured_health_server()

        self.assertIs(result, expected_server)
        mock_create_server.assert_called_once_with(
            "0.0.0.0",
            12345,
            bot.is_ready,
        )

    @patch("bot.create_health_server")
    def test_missing_port_falls_back_to_10000(
        self,
        mock_create_server,
    ):
        expected_server = Mock()
        mock_create_server.return_value = expected_server

        with patch.dict(bot.os.environ, {}, clear=True):
            result = bot.create_configured_health_server()

        self.assertIs(result, expected_server)
        mock_create_server.assert_called_once_with(
            "0.0.0.0",
            10000,
            bot.is_ready,
        )

    @patch("bot.create_health_server")
    def test_invalid_port_stops_startup(
        self,
        mock_create_server,
    ):
        with patch.dict(
            bot.os.environ,
            {"PORT": "invalid"},
            clear=True,
        ):
            with self.assertLogs("SAFIA", level="ERROR"):
                with self.assertRaises(ValueError):
                    bot.create_configured_health_server()

        mock_create_server.assert_not_called()

    @patch("bot.create_health_server")
    def test_bind_oserror_stops_startup(
        self,
        mock_create_server,
    ):
        bind_error = OSError("address already in use")
        mock_create_server.side_effect = bind_error

        with patch.dict(
            bot.os.environ,
            {"PORT": "10000"},
            clear=True,
        ):
            with self.assertLogs("SAFIA", level="ERROR"):
                with self.assertRaises(OSError) as context:
                    bot.create_configured_health_server()

        self.assertIs(context.exception, bind_error)
        mock_create_server.assert_called_once_with(
            "0.0.0.0",
            10000,
            bot.is_ready,
        )

    def test_render_uses_ping_health_check(self):
        render_config = Path("render.yaml").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "healthCheckPath: /ping",
            render_config,
        )


class BotReadinessTests(unittest.TestCase):

    @patch("bot.get_total_expenses")
    def test_not_ready_when_application_is_not_running(
        self,
        mock_get_total,
    ):
        with patch.object(
            bot,
            "app",
            Mock(running=False),
        ):
            with patch.object(
                bot,
                "OCR_API_KEY",
                FAKE_OCR_API_KEY,
            ):
                result = bot.is_ready()

        self.assertFalse(result)
        mock_get_total.assert_not_called()

    @patch("bot.get_total_expenses")
    def test_not_ready_when_ocr_key_is_missing(
        self,
        mock_get_total,
    ):
        with patch.object(
            bot,
            "app",
            Mock(running=True),
        ):
            with patch.object(bot, "OCR_API_KEY", None):
                result = bot.is_ready()

        self.assertFalse(result)
        mock_get_total.assert_not_called()

    @patch("bot.get_total_expenses")
    def test_ready_when_all_checks_succeed(
        self,
        mock_get_total,
    ):
        mock_get_total.return_value = 98765.43

        with patch.object(
            bot,
            "app",
            Mock(running=True),
        ):
            with patch.object(
                bot,
                "OCR_API_KEY",
                FAKE_OCR_API_KEY,
            ):
                result = bot.is_ready()

        self.assertTrue(result)
        mock_get_total.assert_called_once_with()

    @patch("bot.get_total_expenses")
    def test_database_exception_propagates_to_health_handler(
        self,
        mock_get_total,
    ):
        database_error = RuntimeError(
            "private database failure details"
        )
        mock_get_total.side_effect = database_error

        with patch.object(
            bot,
            "app",
            Mock(running=True),
        ):
            with patch.object(
                bot,
                "OCR_API_KEY",
                FAKE_OCR_API_KEY,
            ):
                with self.assertRaises(RuntimeError) as context:
                    bot.is_ready()

        self.assertIs(context.exception, database_error)


if __name__ == "__main__":
    unittest.main()
