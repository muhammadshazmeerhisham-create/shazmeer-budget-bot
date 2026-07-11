from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

from logging_config import get_logger


logger = get_logger(__name__)


class HealthHandler(BaseHTTPRequestHandler):

    def _request_path(self):
        try:
            return urlsplit(self.path).path
        except ValueError:
            return ""

    def _send_text_response(self, status_code, body):
        body_bytes = body.encode("utf-8")

        self.send_response(status_code)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body_bytes)),
        )
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body_bytes)

    def _readiness_status(self):
        try:
            return bool(self.server.readiness_callback())
        except Exception as error:
            logger.error(
                "Health readiness check failed | Exception=%s",
                type(error).__name__,
            )
            return False

    def do_GET(self):
        path = self._request_path()

        if path == "/":
            self._send_text_response(
                200,
                "SAFIA is running!",
            )
            return

        if path == "/ping":
            self._send_text_response(200, "ok")
            return

        if path == "/status":
            if self._readiness_status():
                self._send_text_response(200, "ok")
            else:
                self._send_text_response(503, "unavailable")
            return

        self._send_text_response(404, "not found")

    def log_message(self, format, *args):
        logger.debug(
            "Health request | Path=%s",
            self._request_path(),
        )


def create_health_server(host, port, readiness_callback):
    server = ThreadingHTTPServer(
        (host, port),
        HealthHandler,
    )
    server.readiness_callback = readiness_callback
    return server


def run_health_server(server):
    try:
        server.serve_forever()
    except Exception:
        logger.exception("Health server crashed")
        raise
