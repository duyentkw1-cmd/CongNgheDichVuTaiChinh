import unittest
import sys
from pathlib import Path
from datetime import date, timedelta

# Isolation setup
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _isolation import TEMP_DIR
from backend.local_parse import parse_fields, money_candidates
from backend.db import today

class FixedIssuesTests(unittest.TestCase):
    """Regression tests for recently fixed parsing and normalization issues."""

    def test_fractions_are_not_dates(self):
        """Measurement fractions like 1/2 kg, 3/4 lit must not become dates."""
        current_today = today().isoformat()
        
        fraction_cases = [
            'Mua 1/2 kg thịt bò 120k',
            'Mua 3/4 lít dầu ăn 45k',
            'Mua 1/4 con gà 50k',
            'Mua 1/2 quả dưa hấu 30k',
            'Bán 1/2 hộp bánh 80k',
        ]
        for text in fraction_cases:
            res = parse_fields(text)
            self.assertEqual(res['date'], current_today, f"Failed for '{text}': got {res['date']}")

    def test_explicit_dates_still_work(self):
        """Explicit dates must continue to be parsed correctly."""
        d1 = parse_fields('Bán hàng ngày 15/10 được 200k')
        self.assertEqual(d1['date'], f"{today().year}-10-15")
        
        d2 = parse_fields('Giao dịch 2026-10-15 chuyển khoản 500k')
        self.assertEqual(d2['date'], '2026-10-15')
        
        yesterday = (today() - timedelta(days=1)).isoformat()
        d3 = parse_fields('Hôm qua bán được 400k')
        self.assertEqual(d3['date'], yesterday)

    def test_digit_word_combinations(self):
        """Combinations like '2 trăm nghìn', '5 trăm k' must parse full amount."""
        self.assertEqual(parse_fields('mua đồ 2 trăm nghìn')['amount'], 200000)
        self.assertEqual(parse_fields('mua đồ 5 trăm nghìn')['amount'], 500000)
        self.assertEqual(parse_fields('mua đồ 2 tram k')['amount'], 200000)
        self.assertEqual(parse_fields('mua đồ hai trăm nghìn')['amount'], 200000)

    def test_billion_unit_ty(self):
        """Support for 'tỷ' (billion) amounts."""
        self.assertEqual(parse_fields('Thu 1 tỷ 200 triệu tiền bán đất')['amount'], 1200000000)
        self.assertEqual(parse_fields('Vốn 2 tỷ đồng')['amount'], 2000000000)
        self.assertEqual(parse_fields('Chi 1 ty 500 tr')['amount'], 1500000000)

    def test_slang_and_casual_amounts(self):
        """Support for 'xị', 'nửa triệu', '1tr50k'."""
        # STT=True for voice slang
        self.assertEqual(parse_fields('chi 2 xị đi ăn', stt=True)['amount'], 200000)
        self.assertEqual(parse_fields('chi 5 xị mua quà', stt=True)['amount'], 500000)
        self.assertEqual(parse_fields('thu 3 củ tiền hàng', stt=True)['amount'], 3000000)
        
        # General slang works both with stt=True and False
        self.assertEqual(parse_fields('mua đồ nửa triệu')['amount'], 500000)
        self.assertEqual(parse_fields('bán được nửa củ', stt=True)['amount'], 500000)
        self.assertEqual(parse_fields('chi 1tr50k mua đồ')['amount'], 1050000)
        self.assertEqual(parse_fields('chi 1tr5 mua đồ')['amount'], 1500000)
        self.assertEqual(parse_fields('thu 2.5 triệu')['amount'], 2500000)
        self.assertEqual(parse_fields('thu 2,5 triệu')['amount'], 2500000)

if __name__ == '__main__':
    unittest.main()
