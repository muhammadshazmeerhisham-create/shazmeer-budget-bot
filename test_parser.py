import unittest

from parser import parse_receipt


class MaybankScanPayParserTests(unittest.TestCase):

    def build_receipt(self, recipient_block):
        return f"""Maybank
Scan & Pay
Successful
Reference ID
041724463Q
7 Jul 2026, 4:49 PM
{recipient_block}
Recipient Account Number
008057015436
Amount
RM 50.00
"""

    def assert_scan_pay_recipient(self, result):
        expected_name = "NUR HAZIRAH BINTI SAMSUDI"

        self.assertEqual(result["merchant"], expected_name)
        self.assertEqual(result["recipient"], expected_name)
        self.assertEqual(result["category"], "QR Payment")
        self.assertNotEqual(result["recipient"], "Name")

    def build_merchant_receipt(self, merchant_block):
        return f"""@Maybank
scan & Pay
Reference ID
QR76719ns
{merchant_block}
Amount
RM 53.05
"""

    def assert_scan_pay_merchant(self, result):
        expected_name = "MASLEE EXPRESS-PULAI UTAM"

        self.assertEqual(result["merchant"], expected_name)
        self.assertEqual(result["recipient"], expected_name)
        self.assertEqual(result["category"], "QR Payment")

    def test_parses_standard_maybank_scan_pay_receipt(self):
        receipt = self.build_receipt(
            """Recipient Name
NUR HAZIRAH BINTI SAMSUDI"""
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_recipient(result)
        self.assertEqual(result["amount"], 50.0)
        self.assertEqual(result["receipt_date"], "7 Jul 2026")
        self.assertEqual(result["receipt_time"], "4:49 PM")
        self.assertEqual(result["reference"], "041724463Q")

    def test_parses_same_line_recipient_with_colon(self):
        receipt = self.build_receipt(
            "Recipient Name: NUR HAZIRAH BINTI SAMSUDI"
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_recipient(result)

    def test_parses_inline_recipient_without_colon(self):
        receipt = self.build_receipt(
            "Recipient Name NUR HAZIRAH BINTI SAMSUDI"
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_recipient(result)

    def test_parses_ocr_split_recipient_label(self):
        receipt = self.build_receipt(
            """Recipient
Name
NUR HAZIRAH BINTI SAMSUDI"""
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_recipient(result)
        self.assertNotEqual(result["recipient"], "Recipient")
        self.assertNotEqual(result["recipient"], "Recipient Name")

    def test_missing_recipient_value_does_not_return_name(self):
        receipt = self.build_receipt("Recipient Name")

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "Tidak Dikenal")
        self.assertEqual(result["recipient"], "-")
        self.assertEqual(result["category"], "QR Payment")
        self.assertNotEqual(result["recipient"], "Name")

    def test_recipient_account_number_is_not_used_as_name(self):
        receipt = self.build_receipt("Recipient Name")

        result = parse_receipt(receipt)

        self.assertNotEqual(
            result["recipient"],
            "Recipient Account Number",
        )
        self.assertNotEqual(
            result["recipient"],
            "Account Number",
        )
        self.assertNotEqual(
            result["recipient"],
            "008057015436",
        )

    def test_parses_maybank_scan_pay_merchant_name(self):
        receipt = self.build_merchant_receipt(
            """Merchant Name
MASLEE EXPRESS-PULAI UTAM"""
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_merchant(result)
        self.assertEqual(result["amount"], 53.05)
        self.assertEqual(result["reference"], "QR76719ns")
        self.assertEqual(result["receipt_date"], "-")
        self.assertEqual(result["receipt_time"], "-")

    def test_parses_same_line_merchant_with_colon(self):
        receipt = self.build_merchant_receipt(
            "Merchant Name: MASLEE EXPRESS-PULAI UTAM"
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_merchant(result)

    def test_parses_inline_merchant_without_colon(self):
        receipt = self.build_merchant_receipt(
            "Merchant Name MASLEE EXPRESS-PULAI UTAM"
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_merchant(result)

    def test_parses_ocr_split_merchant_label(self):
        receipt = self.build_merchant_receipt(
            """Merchant
Name
MASLEE EXPRESS-PULAI UTAM"""
        )

        result = parse_receipt(receipt)

        self.assert_scan_pay_merchant(result)

    def test_skips_malformed_datetime_before_reference(self):
        receipt = """@Maybank
scan & Pay
Reference ID
8 2026.1020 PM
QR841913SS
Merchant Name
MUHAMMAD SHAZMEER BIN SAM
Amount
RM 200.00
"""

        result = parse_receipt(receipt)

        expected_name = "MUHAMMAD SHAZMEER BIN SAM"

        self.assertEqual(result["merchant"], expected_name)
        self.assertEqual(result["recipient"], expected_name)
        self.assertEqual(result["category"], "QR Payment")
        self.assertEqual(result["amount"], 200.0)
        self.assertEqual(result["reference"], "QR841913SS")
        self.assertEqual(result["receipt_date"], "-")
        self.assertEqual(result["receipt_time"], "10:20 PM")

    def test_normalizes_three_digit_compact_time(self):
        receipt = """@Maybank
scan & Pay
Reference ID
QR449ABC
449 PM
Merchant Name
MASLEE EXPRESS-PULAI UTAM
Amount
RM 53.05
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["receipt_time"], "4:49 PM")
        self.assertEqual(result["receipt_date"], "-")

    def test_merchant_and_recipient_labels_use_precedence(self):
        receipt = """@Maybank
scan & Pay
Reference ID
QRBOTH123
Recipient Name
NUR HAZIRAH BINTI SAMSUDI
Merchant Name
MASLEE EXPRESS-PULAI UTAM
Amount
RM 53.05
"""

        result = parse_receipt(receipt)

        self.assertEqual(
            result["merchant"],
            "MASLEE EXPRESS-PULAI UTAM",
        )
        self.assertEqual(
            result["recipient"],
            "NUR HAZIRAH BINTI SAMSUDI",
        )
        self.assertEqual(result["category"], "QR Payment")

    def test_rejects_account_number_and_numeric_merchant_name(self):
        invalid_merchant_blocks = [
            """Merchant Name
Merchant Account Number
008057015436""",
            """Merchant Name
008057015436""",
        ]

        for merchant_block in invalid_merchant_blocks:
            with self.subTest(merchant_block=merchant_block):
                receipt = self.build_merchant_receipt(
                    merchant_block
                )

                result = parse_receipt(receipt)

                self.assertEqual(
                    result["merchant"],
                    "Tidak Dikenal",
                )
                self.assertEqual(result["recipient"], "-")
                self.assertEqual(
                    result["category"],
                    "QR Payment",
                )

    def test_rejects_punctuated_labels_as_names(self):
        invalid_names = [
            "Name:",
            "Successful:",
            "Amount:",
            "Merchant Account Number:",
            "008057015436",
        ]

        for invalid_name in invalid_names:
            with self.subTest(invalid_name=invalid_name):
                receipt = self.build_merchant_receipt(
                    f"Merchant Name\n{invalid_name}"
                )

                result = parse_receipt(receipt)

                self.assertEqual(
                    result["merchant"],
                    "Tidak Dikenal",
                )
                self.assertEqual(result["recipient"], "-")
                self.assertEqual(
                    result["category"],
                    "QR Payment",
                )

    def test_accepts_legitimate_label_like_business_names(self):
        legitimate_names = [
            "REFERENCE CAFE",
            "AMOUNT DESIGN STUDIO",
        ]

        for expected_name in legitimate_names:
            with self.subTest(expected_name=expected_name):
                receipt = self.build_merchant_receipt(
                    f"Merchant Name\n{expected_name}"
                )

                result = parse_receipt(receipt)

                self.assertEqual(
                    result["merchant"],
                    expected_name,
                )
                self.assertEqual(
                    result["recipient"],
                    expected_name,
                )
                self.assertEqual(
                    result["category"],
                    "QR Payment",
                )

    def test_full_name_labels_require_clear_boundary(self):
        invalid_blocks = [
            "Merchant Nameplate Trading",
            "Recipient Namespace",
        ]

        for invalid_block in invalid_blocks:
            with self.subTest(invalid_block=invalid_block):
                result = parse_receipt(
                    self.build_merchant_receipt(
                        invalid_block
                    )
                )
                self.assertEqual(
                    result["merchant"],
                    "Tidak Dikenal",
                )
                self.assertEqual(result["recipient"], "-")
                self.assertEqual(
                    result["category"],
                    "QR Payment",
                )

    def test_split_name_requires_exact_name_label(self):
        invalid_blocks = [
            "Merchant\nCustomer Copy",
            "Recipient\nCustomer Copy",
        ]

        for invalid_block in invalid_blocks:
            with self.subTest(invalid_block=invalid_block):
                result = parse_receipt(
                    self.build_merchant_receipt(
                        invalid_block
                    )
                )
                self.assertEqual(
                    result["merchant"],
                    "Tidak Dikenal",
                )
                self.assertEqual(result["recipient"], "-")
                self.assertEqual(
                    result["category"],
                    "QR Payment",
                )

    def test_split_merchant_name_allows_trailing_colon(self):
        receipt = self.build_merchant_receipt(
            "Merchant\nName:\nMASLEE EXPRESS-PULAI UTAM"
        )
        result = parse_receipt(receipt)
        self.assert_scan_pay_merchant(result)

    def test_reference_id_requires_clear_boundary(self):
        receipt = """@Maybank
scan & Pay
Reference IDABC123
Merchant Name
MASLEE EXPRESS-PULAI UTAM
Amount
RM 53.05
"""
        result = parse_receipt(receipt)
        self.assertEqual(result["reference"], "-")

    def test_maybank_without_scan_pay_uses_existing_fallback(self):
        receipt = """Maybank
Successful
Reference ID
041724463Q
Amount
RM 50.00
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "Maybank")
        self.assertEqual(result["category"], "Transfer")
        self.assertNotEqual(result["category"], "QR Payment")


class TouchNGoReceiptParserTests(unittest.TestCase):

    def test_parses_touch_n_go_receipt_with_merchant_label(self):
        receipt = """Touch 'n Go eWallet
Payment Successful
Merchant Name
KEDAI MAKAN MAKMUR
Transaction No.
TNG-20260709-123456
Date & Time
09/07/2026 10:30 AM
Amount
RM 12.50
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "KEDAI MAKAN MAKMUR")
        self.assertEqual(result["category"], "E-Wallet")
        self.assertEqual(result["amount"], 12.50)
        self.assertEqual(result["reference"], "TNG-20260709-123456")
        self.assertEqual(result["receipt_date"], "09/07/2026 10:30 AM")
        self.assertEqual(result["receipt_time"], "10:30 AM")

    def test_parses_tng_ewallet_spelling_without_merchant_label(self):
        receipt = """TNG e-Wallet
Payment Successful
Amount
RM 8.90
Transaction No
TNG-001
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "TNG eWallet")
        self.assertEqual(result["category"], "E-Wallet")
        self.assertEqual(result["amount"], 8.90)
        self.assertEqual(result["reference"], "TNG-001")


class ExistingParserRegressionTests(unittest.TestCase):

    def test_existing_retail_receipt_amount_still_parses(self):
        receipt = """SHELL
TOTAL RM45.60
09/07/2026 14:05
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "Shell")
        self.assertEqual(result["category"], "Petrol")
        self.assertEqual(result["amount"], 45.60)


if __name__ == "__main__":
    unittest.main()
