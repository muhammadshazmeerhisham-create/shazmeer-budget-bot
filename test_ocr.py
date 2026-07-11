import io
import unittest
from unittest.mock import Mock, patch

import requests

from ocr import OCR_TIMEOUT, scan_receipt


def make_response(status_code=200, payload=None):
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload

    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(
            f"HTTP {status_code}",
            response=response,
        )

    return response


class OCRTests(unittest.TestCase):

    @patch("ocr.requests.post")
    def test_success_returns_parsed_text(self, mock_post):
        mock_post.return_value = make_response(
            payload={
                "ParsedResults": [
                    {"ParsedText": "TOTAL RM12.50"}
                ]
            }
        )

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "TOTAL RM12.50")
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(
            mock_post.call_args.kwargs["timeout"],
            OCR_TIMEOUT,
        )

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_connection_error_is_retried(
        self,
        mock_post,
        mock_sleep,
    ):
        mock_post.side_effect = [
            requests.ConnectionError("connection failed"),
            make_response(
                payload={
                    "ParsedResults": [
                        {"ParsedText": "RETRY SUCCESS"}
                    ]
                }
            ),
        ]

        with patch(
            "builtins.open",
            side_effect=[
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
            ],
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "RETRY SUCCESS")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_timeout_uses_all_three_attempts(
        self,
        mock_post,
        mock_sleep,
    ):
        mock_post.side_effect = requests.ReadTimeout("read timed out")

        with patch(
            "builtins.open",
            side_effect=[
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
            ],
        ):
            with self.assertRaises(requests.ReadTimeout):
                scan_receipt("receipt.jpg")

        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [1, 2],
        )

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_read_timeout_twice_then_success_on_third_attempt(
        self,
        mock_post,
        mock_sleep,
    ):
        parsed_text = "SHOP NAME\r\nTOTAL RM18.90\r\n"
        mock_post.side_effect = [
            requests.ReadTimeout("attempt 1 timed out"),
            requests.ReadTimeout("attempt 2 timed out"),
            make_response(
                payload={
                    "ParsedResults": [
                        {"ParsedText": parsed_text}
                    ]
                }
            ),
        ]

        with patch(
            "builtins.open",
            side_effect=[
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
            ],
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, parsed_text)
        self.assertEqual(mock_post.call_count, 3)
        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [1, 2],
        )

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_connect_timeout_is_retried(
        self,
        mock_post,
        mock_sleep,
    ):
        mock_post.side_effect = [
            requests.ConnectTimeout("connect timed out"),
            make_response(
                payload={
                    "ParsedResults": [
                        {"ParsedText": "CONNECTED"}
                    ]
                }
            ),
        ]

        with patch(
            "builtins.open",
            side_effect=[
                io.BytesIO(b"image"),
                io.BytesIO(b"image"),
            ],
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "CONNECTED")
        self.assertEqual(mock_post.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_retryable_http_statuses_are_retried(
        self,
        mock_post,
        mock_sleep,
    ):
        retryable_statuses = (408, 429, 500, 502, 503, 504)

        for status_code in retryable_statuses:
            with self.subTest(status_code=status_code):
                mock_post.reset_mock()
                mock_sleep.reset_mock()
                mock_post.side_effect = [
                    make_response(status_code=status_code),
                    make_response(
                        payload={
                            "ParsedResults": [
                                {"ParsedText": "HTTP RETRY SUCCESS"}
                            ]
                        }
                    ),
                ]

                with patch(
                    "builtins.open",
                    side_effect=[
                        io.BytesIO(b"image"),
                        io.BytesIO(b"image"),
                    ],
                ):
                    result = scan_receipt("receipt.jpg")

                self.assertEqual(result, "HTTP RETRY SUCCESS")
                self.assertEqual(mock_post.call_count, 2)
                mock_sleep.assert_called_once_with(1)

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_non_retryable_http_status_fails_immediately(
        self,
        mock_post,
        mock_sleep,
    ):
        mock_post.return_value = make_response(status_code=401)

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            with self.assertRaises(requests.HTTPError):
                scan_receipt("receipt.jpg")

        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_invalid_json_is_not_retried(
        self,
        mock_post,
        mock_sleep,
    ):
        response = make_response()
        response.json.side_effect = requests.exceptions.JSONDecodeError(
            "invalid JSON",
            "not-json",
            0,
        )
        mock_post.return_value = response

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            with self.assertRaises(requests.exceptions.JSONDecodeError):
                scan_receipt("receipt.jpg")

        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

    @patch("ocr.requests.post")
    def test_missing_parsed_results_returns_empty_string(
        self,
        mock_post,
    ):
        mock_post.return_value = make_response(payload={})

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "")
        self.assertEqual(mock_post.call_count, 1)

    @patch("ocr.requests.post")
    def test_empty_parsed_results_returns_empty_string(
        self,
        mock_post,
    ):
        mock_post.return_value = make_response(
            payload={"ParsedResults": []}
        )

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "")
        self.assertEqual(mock_post.call_count, 1)

    @patch("ocr.requests.post")
    def test_valid_parsed_text_is_preserved_exactly(
        self,
        mock_post,
    ):
        parsed_text = "SHOP NAME\r\nTOTAL  RM 42.00\r\n"
        mock_post.return_value = make_response(
            payload={
                "ParsedResults": [
                    {"ParsedText": parsed_text}
                ]
            }
        )

        with patch(
            "builtins.open",
            return_value=io.BytesIO(b"image"),
        ):
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, parsed_text)

    @patch("ocr.time.sleep")
    @patch("ocr.requests.post")
    def test_multipart_stream_is_reopened_for_every_attempt(
        self,
        mock_post,
        mock_sleep,
    ):
        streams = [
            io.BytesIO(b"same-image-content"),
            io.BytesIO(b"same-image-content"),
            io.BytesIO(b"same-image-content"),
        ]
        posted_streams = []
        posted_content = []

        def post_side_effect(*args, **kwargs):
            stream = kwargs["files"]["filename"]
            posted_streams.append(stream)
            posted_content.append(stream.read())

            if len(posted_streams) < 3:
                raise requests.ConnectionError("temporary failure")

            return make_response(
                payload={
                    "ParsedResults": [
                        {"ParsedText": "SUCCESS"}
                    ]
                }
            )

        mock_post.side_effect = post_side_effect

        with patch("builtins.open", side_effect=streams) as mock_open:
            result = scan_receipt("receipt.jpg")

        self.assertEqual(result, "SUCCESS")
        self.assertEqual(mock_open.call_count, 3)
        self.assertEqual(mock_post.call_count, 3)
        self.assertIsNot(posted_streams[0], posted_streams[1])
        self.assertIsNot(posted_streams[1], posted_streams[2])
        self.assertEqual(
            posted_content,
            [
                b"same-image-content",
                b"same-image-content",
                b"same-image-content",
            ],
        )
        self.assertEqual(
            [call.args[0] for call in mock_sleep.call_args_list],
            [1, 2],
        )


if __name__ == "__main__":
    unittest.main()
