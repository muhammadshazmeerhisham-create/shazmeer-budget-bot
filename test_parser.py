import unittest

from parser import (
    detect_transaction_type,
    parse_bank_transfer,
    parse_receipt,
)


class BankTransferParserTests(unittest.TestCase):

    RECIPIENT_NAME = "NUR HAZIRAH BINTI SAMSUDI"

    def build_transfer(self, body="", bank="Maybank"):
        parts = [bank, "Third Party Transfer"]

        if body:
            parts.append(body)

        return "\n".join(parts) + "\n"

    def parse_transfer(self, body="", bank="Maybank"):
        result = parse_receipt(
            self.build_transfer(body, bank)
        )

        self.assertEqual(result["category"], "Transfer")

        return result

    def test_parses_complete_maybank_third_party_transfer(self):
        receipt = """Maybank
Third Party Transfer
Successful
Beneficiary Name
NUR HAZIRAH BINTI SAMSUDI
Beneficiary Account Number
008057015436
Recipient Reference
Family transfer
Transaction Reference
MB123456789
Amount
RM 200.00
7 Jul 2026, 4:49 PM
"""

        result = parse_receipt(receipt)

        self.assertEqual(
            result,
            {
                "merchant": "Maybank Transfer",
                "recipient": self.RECIPIENT_NAME,
                "amount": 200.0,
                "category": "Transfer",
                "receipt_date": "7 Jul 2026",
                "receipt_time": "4:49 PM",
                "reference": "MB123456789",
                "confidence": 100,
            },
        )

    def test_recipient_reference_is_not_transaction_reference(self):
        result = self.parse_transfer(
            """Recipient Reference
Family transfer
Amount
RM 20.00"""
        )

        self.assertEqual(result["reference"], "-")

    def test_transaction_reference_wins_over_recipient_reference(self):
        result = self.parse_transfer(
            """Recipient Reference
Family transfer
Transaction Reference
MB123456789
Amount
RM 20.00"""
        )

        self.assertEqual(result["reference"], "MB123456789")

    def test_recipient_name_label_layouts(self):
        layouts = [
            f"Beneficiary Name\n{self.RECIPIENT_NAME}",
            f"Beneficiary Name: {self.RECIPIENT_NAME}",
            f"Recipient Name - {self.RECIPIENT_NAME}",
            f"Recipient Name {self.RECIPIENT_NAME}",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(
                    result["recipient"],
                    self.RECIPIENT_NAME,
                )

    def test_strict_split_name_layouts(self):
        layouts = [
            f"Beneficiary\nName\n{self.RECIPIENT_NAME}",
            f"Recipient\nName:\n{self.RECIPIENT_NAME}",
            f"Recipient\nName-\n{self.RECIPIENT_NAME}",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(
                    result["recipient"],
                    self.RECIPIENT_NAME,
                )

    def test_invalid_split_name_layouts(self):
        layouts = [
            "Beneficiary\nCustomer Copy",
            "Recipient\nAccount Number",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], "-")

    def test_missing_name_stops_at_next_semantic_label(self):
        layouts = [
            """Beneficiary Name
Beneficiary Account Number
008057015436
Recipient Reference
Family transfer""",
            """Beneficiary Name
Recipient Reference
Family transfer""",
            """Beneficiary Name
Amount
RM 200.00""",
            """Beneficiary Name
Transaction Reference
MB123456789""",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], "-")

    def test_missing_name_can_fall_back_to_lower_priority_semantic(self):
        layouts = [
            "Beneficiary Name\nRecipient JOHN DOE",
            "Beneficiary Name\nPayee: JOHN DOE",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], "JOHN DOE")

    def test_specific_recipient_fields_do_not_fall_through(self):
        layouts = [
            """Beneficiary Bank
Maybank
Beneficiary Account Number
008057015436""",
            """Beneficiary Name
Beneficiary Bank
Maybank
Beneficiary Account Number
008057015436""",
            """Recipient Bank
CIMB""",
            """Recipient Account Number
008057015436
Recipient Reference
Family transfer""",
            """Beneficiary Account Number
008057015436
Recipient Reference
Family transfer""",
            """Payee Bank
CIMB""",
            """Receiver Bank
Maybank""",
            """To Bank
GXBank""",
            """Payee Account Number
008057015436""",
            """Receiver Reference
ABC123""",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], "-")

    def test_merchant_name_field_is_not_generic_recipient(self):
        result = parse_bank_transfer(
            ["Merchant Name", "SOME MERCHANT"]
        )

        self.assertEqual(result["recipient"], "-")

    def test_bank_word_remains_valid_in_company_name(self):
        result = self.parse_transfer(
            "Beneficiary Name: BANK RAKYAT TRADING"
        )

        self.assertEqual(
            result["recipient"],
            "BANK RAKYAT TRADING",
        )

    def test_numeric_account_number_is_not_recipient(self):
        result = self.parse_transfer(
            """Beneficiary Name
008057015436"""
        )

        self.assertEqual(result["recipient"], "-")

    def test_all_recipient_semantics_are_supported(self):
        layouts = [
            f"Beneficiary Name: {self.RECIPIENT_NAME}",
            f"Recipient Name: {self.RECIPIENT_NAME}",
            f"Beneficiary: {self.RECIPIENT_NAME}",
            f"Beneficiary {self.RECIPIENT_NAME}",
            f"Recipient - {self.RECIPIENT_NAME}",
            f"Payee {self.RECIPIENT_NAME}",
            f"Receiver: {self.RECIPIENT_NAME}",
            f"To {self.RECIPIENT_NAME}",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(
                    result["recipient"],
                    self.RECIPIENT_NAME,
                )

    def test_beneficiary_name_precedes_recipient_name(self):
        result = self.parse_transfer(
            """Recipient Name
EARLIER RECIPIENT
Beneficiary Name
NUR HAZIRAH BINTI SAMSUDI"""
        )

        self.assertEqual(
            result["recipient"],
            self.RECIPIENT_NAME,
        )

    def test_transfer_name_labels_require_clear_boundaries(self):
        invalid_lines = [
            "Beneficiary Namespace",
            "Recipient Nameplate",
            "BeneficiaryAccount",
            "RecipientReferenceText",
        ]

        for invalid_line in invalid_lines:
            with self.subTest(invalid_line=invalid_line):
                result = self.parse_transfer(invalid_line)

                self.assertEqual(result["recipient"], "-")

    def test_invalid_recipient_candidates_are_rejected(self):
        invalid_candidates = [
            "Beneficiary Name",
            "Beneficiary Account Number",
            "Recipient Name",
            "Recipient Reference",
            "Merchant Name",
            "Account Number",
            "Amount",
            "Transfer Amount",
            "Amount Paid",
            "Successful:",
            "Transaction Reference",
            "Reference ID",
            "Date",
            "Time",
            "",
            "008057015436",
            "RM 200.00",
            "MB123456789",
        ]

        for candidate in invalid_candidates:
            with self.subTest(candidate=candidate):
                lines = [
                    "Maybank",
                    "Third Party Transfer",
                    f"Beneficiary Name: {candidate}",
                ]

                result = parse_bank_transfer(lines)

                self.assertEqual(result["recipient"], "-")

    def test_legitimate_label_like_names_are_preserved(self):
        layouts = [
            ("Beneficiary Name: BANK RAKYAT TRADING", "BANK RAKYAT TRADING"),
            ("Beneficiary Name: REFERENCE CAFE", "REFERENCE CAFE"),
            ("Beneficiary Name: AMOUNT DESIGN STUDIO", "AMOUNT DESIGN STUDIO"),
            ("Beneficiary Name: TO THE MOON SDN BHD", "TO THE MOON SDN BHD"),
            ("Recipient Name: RECEIVER LOGISTICS", "RECEIVER LOGISTICS"),
            ("Payee: PAYEE SERVICES", "PAYEE SERVICES"),
        ]

        for layout, expected_name in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], expected_name)

    def test_separate_line_label_like_names_are_preserved(self):
        layouts = [
            (
                "Beneficiary Name\nREFERENCE CAFE",
                "REFERENCE CAFE",
            ),
            (
                "Beneficiary Name\nAMOUNT DESIGN STUDIO",
                "AMOUNT DESIGN STUDIO",
            ),
            (
                "Beneficiary Name\nBANK RAKYAT TRADING",
                "BANK RAKYAT TRADING",
            ),
            (
                "Recipient Name\nRECEIVER LOGISTICS",
                "RECEIVER LOGISTICS",
            ),
        ]

        for layout, expected_name in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["recipient"], expected_name)

    def test_recipient_preserves_original_text(self):
        expected_name = "Nur Hazirah Binti Samsudi"

        result = self.parse_transfer(
            f"Beneficiary Name: {expected_name}"
        )

        self.assertEqual(result["recipient"], expected_name)

    def test_labelled_amount_layouts(self):
        cases = [
            ("Amount\nRM 50.00", 50.0),
            ("Amount: RM 50.00", 50.0),
            ("Amount RM50.00", 50.0),
            ("Transfer Amount - 200.00", 200.0),
            ("Amount Paid: RM 1,234.56", 1234.56),
        ]

        for layout, expected_amount in cases:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(
                    result["amount"],
                    expected_amount,
                )

    def test_amount_label_precedence(self):
        result = self.parse_transfer(
            """Amount 300.00
Amount Paid 200.00
Transfer Amount 100.00"""
        )

        self.assertEqual(result["amount"], 100.0)

    def test_missing_amount_does_not_use_other_numbers(self):
        result = self.parse_transfer(
            """Beneficiary Account Number
008057015436
Transaction Reference
123456789012"""
        )

        self.assertEqual(result["amount"], 0.0)

    def test_complete_date_time_layouts(self):
        layouts = [
            "7 Jul 2026, 4:49 PM",
            "Transaction Date & Time: 7 Jul 2026, 4:49 PM",
            "Date: 7 Jul 2026\nTime: 4:49 PM",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(
                    result["receipt_date"],
                    "7 Jul 2026",
                )
                self.assertEqual(
                    result["receipt_time"],
                    "4:49 PM",
                )

    def test_missing_or_incomplete_date_time_uses_dashes(self):
        layouts = [
            "",
            "Date: 8 2026",
        ]

        for layout in layouts:
            with self.subTest(layout=layout):
                result = self.parse_transfer(layout)

                self.assertEqual(result["receipt_date"], "-")
                self.assertEqual(result["receipt_time"], "-")

    def test_transaction_reference_labels(self):
        labels = [
            "Transaction Reference",
            "Transaction ID",
            "Transaction Number",
            "Transaction No",
            "Transfer Reference",
            "DuitNow Ref",
            "FPX Ref",
            "Reference ID",
            "Reference No",
            "Reference",
        ]

        for label in labels:
            with self.subTest(label=label):
                result = self.parse_transfer(
                    f"{label}: TX-123"
                )

                self.assertEqual(result["reference"], "TX-123")

    def test_numeric_transaction_reference_is_preserved(self):
        result = self.parse_transfer(
            """Transaction ID
000123456789"""
        )

        self.assertEqual(result["reference"], "000123456789")

    def test_transaction_reference_semantic_precedence(self):
        result = self.parse_transfer(
            """Reference ID LOW123
Transfer Reference MID123
Transaction Reference HIGH123"""
        )

        self.assertEqual(result["reference"], "HIGH123")

    def test_bank_issuer_display_names(self):
        cases = [
            ("Maybank", "Maybank Transfer"),
            ("CIMB", "CIMB Transfer"),
            ("AmBank", "AmBank Transfer"),
            ("GXBank", "GXBank Transfer"),
            ("Online Banking", "Bank Transfer"),
        ]

        for bank, expected_merchant in cases:
            with self.subTest(bank=bank):
                result = self.parse_transfer(bank=bank)

                self.assertEqual(
                    result["merchant"],
                    expected_merchant,
                )

    def test_beneficiary_bank_is_not_treated_as_issuer(self):
        result = self.parse_transfer(
            """Beneficiary Bank
Maybank
Beneficiary Name
NUR HAZIRAH BINTI SAMSUDI""",
            bank="Online Banking",
        )

        self.assertEqual(result["merchant"], "Bank Transfer")

    def test_recipient_bank_fields_stop_issuer_detection(self):
        cases = [
            "Payee Bank\nCIMB",
            "Payee Bank: CIMB",
            "Receiver Bank\nMaybank",
            "To Bank\nGXBank",
        ]

        for body in cases:
            with self.subTest(body=body):
                result = self.parse_transfer(
                    body,
                    bank="Online Banking",
                )

                self.assertEqual(
                    result["merchant"],
                    "Bank Transfer",
                )

    def test_issuer_before_recipient_bank_field_is_preserved(self):
        result = self.parse_transfer(
            "Payee Bank\nCIMB",
            bank="Maybank",
        )

        self.assertEqual(result["merchant"], "Maybank Transfer")

    def test_status_before_issuer_does_not_hide_bank_branding(self):
        receipt = """Third Party Transfer
Successful
Maybank
Beneficiary Name
NUR HAZIRAH BINTI SAMSUDI
"""

        result = parse_receipt(receipt)

        self.assertEqual(result["merchant"], "Maybank Transfer")

    def test_bank_transfer_routing_markers(self):
        markers = [
            "THIRD PARTY TRANSFER",
            "BENEFICIARY",
            "TRANSFER SUCCESSFUL",
            "TRANSFER DETAILS",
        ]

        for marker in markers:
            with self.subTest(marker=marker):
                self.assertEqual(
                    detect_transaction_type(marker),
                    "BANK_TRANSFER",
                )

    def test_qr_detection_keeps_precedence(self):
        receipt = """Maybank
Scan & Pay
Beneficiary Name
NUR HAZIRAH BINTI SAMSUDI
"""

        self.assertEqual(
            detect_transaction_type(receipt),
            "QR_PAYMENT",
        )

    def test_gxbank_payment_successful_is_not_bank_transfer(self):
        receipt = """GXBank Payment Successful
Recipient Name
NUR HAZIRAH BINTI SAMSUDI
"""

        self.assertNotEqual(
            detect_transaction_type(receipt),
            "BANK_TRANSFER",
        )

    def test_missing_optional_values_preserve_output_contract(self):
        result = self.parse_transfer()

        self.assertEqual(
            result,
            {
                "merchant": "Maybank Transfer",
                "recipient": "-",
                "amount": 0.0,
                "category": "Transfer",
                "receipt_date": "-",
                "receipt_time": "-",
                "reference": "-",
                "confidence": 100,
            },
        )


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
