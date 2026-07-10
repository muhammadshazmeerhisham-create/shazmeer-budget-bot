import unittest

from parser import parse_receipt


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
