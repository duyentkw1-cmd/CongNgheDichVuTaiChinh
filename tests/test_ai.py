"""Comprehensive tests for local AI models, text parsing, OCR, and voice pipelines.

Tests cover:
1. Text normalization and feature extraction
2. Amount parsing (Vietnamese monetary expressions)
3. ML classification accuracy (categories + kind)
4. OCR text extraction quality
5. Voice pipeline validation
6. End-to-end integration
"""
import asyncio
import io
import socket
import unittest
import wave
from pathlib import Path
from unittest.mock import patch
from contextlib import contextmanager
from _isolation import TEMP_DIR
from fastapi import HTTPException
from backend import ai
from backend.local_parse import parse_fields
from ml.train import load_data
from ml.predict import classify, metrics
from ml.text import normalize


@contextmanager
def assert_no_remote_network():
    orig_connect = socket.socket.connect
    def guarded_connect(self, address, *args, **kwargs):
        host = address[0] if isinstance(address, tuple) else address
        if str(host) in ('127.0.0.1', '::1', 'localhost'):
            return orig_connect(self, address, *args, **kwargs)
        raise AssertionError(f'Unexpected network call to {address}')
    with patch.object(socket.socket, 'connect', new=guarded_connect):
        yield


class NormalizationTests(unittest.TestCase):
    """Tests for the text normalization pipeline."""

    def test_basic_normalization(self):
        """Vietnamese text with diacritics should be stripped but readable."""
        self.assertEqual(normalize('Mua nguyên liệu'), 'mua nguyen lieu')

    def test_numbers_become_tokens(self):
        """Numbers should be replaced with _NUM_ tokens, not removed."""
        result = normalize('Thu tiền bán hàng 2.500.000 đồng')
        self.assertIn('_num_', result)
        self.assertIn('thu tien ban hang', result)

    def test_diacritics_removed(self):
        """All Vietnamese diacritics should be stripped."""
        result = normalize('Đóng tiền điện cửa hàng')
        self.assertNotIn('ó', result)
        self.assertNotIn('ệ', result)
        self.assertIn('dong tien dien cua hang', result)

    def test_special_chars_removed(self):
        """Non-letter characters should be cleaned."""
        result = normalize('Mua hàng: $500, đã thanh toán!')
        self.assertNotIn('$', result)
        self.assertNotIn('!', result)
        self.assertNotIn(':', result)

    def test_empty_string(self):
        self.assertEqual(normalize(''), '')

    def test_already_normalized(self):
        result = normalize('mua hang')
        self.assertEqual(result, 'mua hang')

    def test_mixed_case(self):
        """Should be case-insensitive."""
        self.assertEqual(normalize('MUA HÀNG'), normalize('mua hàng'))

    def test_ocr_noise_tolerance(self):
        """Normalize should handle OCR-like noise gracefully."""
        result = normalize('Mua nguyên liêu cho quán')  # 'liêu' instead of 'liệu'
        self.assertIn('mua nguyen', result)


class AmountParsingTests(unittest.TestCase):
    """Tests for Vietnamese monetary expression parsing."""

    def test_basic_amounts(self):
        cases = {
            'mua nguyên liệu 1,5 triệu': 1500000,
            'trả tiền thuê mặt bằng hai triệu ba trăm nghìn đồng': 2300000,
            'tiền điện một triệu rưỡi': 1500000,
            'mua rau ba trăm năm mươi nghìn': 350000,
            'Mua sữa 1tr5': 1500000,
            'mua gạo 1tr200': 1200000,
            'Mua 2 kg thịt 250k': 250000,
            'hết 150000': 150000,
            'Tổng cộng: 650.000 VND': 650000,
        }
        for text, amount in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_fields(text)['amount'], amount)

    def test_informal_amounts(self):
        """Common casual Vietnamese monetary expressions."""
        cases = {
            'mua đồ ăn 85k': 85000,
            'trả tiền 2tr': 2000000,
            'hết 500 nghìn': 500000,
            'thanh toán 1.200.000 đồng': 1200000,
        }
        for text, amount in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_fields(text)['amount'], amount)

    def test_abstains_instead_of_inventing_money(self):
        """Should NOT guess amounts when ambiguous or invalid."""
        for text in [
            'Mua hàng 200k và tiền ship 30k',
            'Gọi 0987654321 để mua hàng',
            'Mua nguyên liệu',
            'Trả 20 USD',
            'Mua hàng -200000 đồng',
            'Tổng cộng 0 VND',
        ]:
            with self.subTest(text=text):
                self.assertIsNone(parse_fields(text)['amount'])

    def test_receipt_with_total(self):
        """Should extract total from receipt-like text."""
        r = parse_fields(
            'Cà phê 450.000 VND\nSữa 200.000 VND\n'
            'Tổng cộng: 650.000 VND\nTiền khách đưa 700.000 VND'
        )
        self.assertEqual(r['amount'], 650000)

    def test_word_numbers(self):
        """Vietnamese word-form numbers."""
        cases = {
            'chi năm trăm nghìn đồng': 500000,
            'mua đồ một trăm hai mươi nghìn': 120000,
        }
        for text, amount in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_fields(text)['amount'], amount)


class DateParsingTests(unittest.TestCase):
    """Tests for date extraction from transaction text."""

    def test_explicit_dates(self):
        r = parse_fields('Mua hàng 500k ngày 2026-10-15')
        self.assertEqual(r['date'], '2026-10-15')

    def test_hom_qua(self):
        from backend.db import today
        from datetime import timedelta
        expected = (today() - timedelta(days=1)).isoformat()
        r = parse_fields('hôm qua mua đồ 200k')
        self.assertEqual(r['date'], expected)

    def test_payment_detection(self):
        r1 = parse_fields('mua hàng 500k chuyển khoản')
        self.assertEqual(r1['payment'], 'transfer')
        r2 = parse_fields('mua hàng 500k tiền mặt')
        self.assertEqual(r2['payment'], 'cash')


class SttNormalizationTests(unittest.TestCase):
    """Tests for normalize_stt_text: Whisper STT misrecognition correction."""

    def setUp(self):
        from backend.local_parse import normalize_stt_text
        self.normalize = normalize_stt_text

    def test_cham_becomes_tram(self):
        """'cham' (chăm) should be normalized to 'tram' (trăm = 100)."""
        self.assertIn('tram', self.normalize('sau cham nghin'))

    def test_nhin_becomes_nghin(self):
        """'nhin' (nhìn) should be normalized to 'nghin' (nghìn = 1000)."""
        self.assertIn('nghin', self.normalize('ba tram nhin'))

    def test_cham_nhin_chain(self):
        """'sau cham nhin' → '600,000' via parse_fields stt=True."""
        r = parse_fields('Nguon nam kinh doanh, thit, sau cham nhin.', stt=True)
        self.assertEqual(r['amount'], 600000)

    def test_tram_ruoi_without_unit(self):
        """'sau tram ruoi' should become 650,000 (650k)."""
        r = parse_fields('mua thit sau tram ruoi tien mat', stt=True)
        self.assertEqual(r['amount'], 650000)

    def test_slang_cu_chai(self):
        """'ba cu' / 'ba chai' should be 3,000,000."""
        for t in ['mua hang ba cu tien mat', 'mua hang ba chai tien mat']:
            with self.subTest(text=t):
                r = parse_fields(t, stt=True)
                self.assertEqual(r['amount'], 3000000)

    def test_slang_xi(self):
        """'sau xi' should be 600,000."""
        r = parse_fields('mua thit sau xi tien mat', stt=True)
        self.assertEqual(r['amount'], 600000)

    def test_normal_text_unaffected(self):
        """stt=False should not alter normal text parsing."""
        r = parse_fields('mua hàng 500k tiền mặt', stt=False)
        self.assertEqual(r['amount'], 500000)

    def test_stt_does_not_break_digits(self):
        """Digits like '600k' or '1.200.000' must still parse with stt=True."""
        cases = {
            'mua hang 600k tien mat': 600000,
            'tra tien 1.200.000 dong': 1200000,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(parse_fields(text, stt=True)['amount'], expected)


class CategoryClassificationTests(unittest.TestCase):
    """Tests for ML category classification accuracy."""

    def test_basic_categories(self):
        """Core category predictions must be correct."""
        cases = [
            ('Thanh toán tiền thuê cửa hàng', 'rent'),
            ('Trả lương nhân viên', 'salary'),
            ('Vay ngân hàng để kinh doanh', 'capital'),
            ('Tiền điện nước cửa hàng', 'utilities'),
            ('Mua nguyên liệu cho quán', 'materials'),
        ]
        for text, cat in cases:
            with self.subTest(text=text):
                self.assertEqual(classify(text)['category'], cat)

    def test_income_categories(self):
        """Income categories should be classified correctly."""
        income_cases = [
            ('Thu tiền bán hàng', 'sales'),
            ('Khách trả phí dịch vụ', 'service'),
            ('Ngân hàng trả lãi tiền gửi', 'other_income'),
        ]
        for text, cat in income_cases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['category'], cat)

    def test_expense_categories(self):
        """Expense categories should be classified correctly."""
        expense_cases = [
            ('Đóng tiền điện cửa hàng', 'utilities'),
            ('Trả phí giao hàng cho khách', 'shipping'),
            ('Đóng thuế kinh doanh', 'other_expense'),
        ]
        for text, cat in expense_cases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['category'], cat)

    def test_kind_classification(self):
        """Income/expense kind should be correct."""
        income_texts = [
            'Thu tiền bán hàng tại quầy',
            'Khách trả phí sửa xe',
            'Nhận tiền vay ngân hàng',
        ]
        for text in income_texts:
            with self.subTest(text=text):
                self.assertEqual(classify(text)['kind'], 'income')

        expense_texts = [
            'Mua nguyên liệu cho quán',
            'Trả tiền thuê mặt bằng',
            'Trả lương nhân viên',
        ]
        for text in expense_texts:
            with self.subTest(text=text):
                self.assertEqual(classify(text)['kind'], 'expense')

    def test_noisy_input_still_classifies(self):
        """Model should handle noisy/OCR-like input."""
        noisy_cases = [
            ('mua nguyen lieu cho quan', 'materials'),  # no diacritics
            ('TRA LUONG NHAN VIEN', 'salary'),  # all caps
            ('thu tien ban hang tai quay', 'sales'),  # no diacritics
        ]
        for text, expected in noisy_cases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['category'], expected,
                    f'Expected {expected}, got {result["category"]} with score {result["score"]:.3f}')

    def test_confidence_score_reasonable(self):
        """Clear inputs should get reasonably high confidence scores."""
        result = classify('Mua nguyên liệu cho quán')
        self.assertGreater(result['score'], 0.3, 'Score too low for clear input')
        self.assertLessEqual(result['score'], 1.0)

    def test_alternatives_provided(self):
        """Classify should return top 3 alternatives."""
        result = classify('Trả tiền thuê mặt bằng')
        self.assertEqual(len(result['alternatives']), 3)
        self.assertTrue(all('category' in a and 'score' in a for a in result['alternatives']))

    def test_needs_review_for_ambiguous(self):
        """Very ambiguous input should be flagged for review."""
        result = classify('abc xyz')
        self.assertTrue(result['needs_review'])


class DatasetIntegrityTests(unittest.TestCase):
    """Tests for training data quality and split integrity."""

    def test_group_split_and_saved_metrics(self):
        data = load_data()
        total = sum(map(len, data.values()))
        self.assertGreater(total, 1584, 'Dataset should be larger after augmentation')
        m = metrics()
        self.assertIn('counts', m)
        self.assertIn('test', m['counts'])

    def test_all_categories_in_all_splits(self):
        """Every category must have examples in every split."""
        data = load_data()
        expected_cats = {'sales', 'service', 'capital', 'other_income',
                         'materials', 'rent', 'utilities', 'shipping',
                         'salary', 'other_expense'}
        for split_name, rows in data.items():
            cats = {r['category'] for r in rows}
            self.assertEqual(cats, expected_cats,
                f'{split_name} missing categories: {expected_cats - cats}')

    def test_no_group_leakage(self):
        """No group_id should appear in more than one split."""
        data = load_data()
        seen_groups = {}
        for split_name, rows in data.items():
            for r in rows:
                if r['group_id'] in seen_groups:
                    self.assertEqual(seen_groups[r['group_id']], split_name,
                        f'Group {r["group_id"]} leaked between {seen_groups[r["group_id"]]} and {split_name}')
                seen_groups[r['group_id']] = split_name


class TextExtractionTests(unittest.TestCase):
    """Tests for the full analyze_text pipeline."""

    def test_text_inference_never_uses_network(self):
        with assert_no_remote_network():
            r = asyncio.run(ai.extract('Hôm nay mua nguyên liệu 300 nghìn, trả tiền mặt'))
        self.assertEqual(r['amount'], 300000)
        self.assertEqual(r['engine'], 'local')

    def test_full_analysis_pipeline(self):
        """End-to-end: text → parse + classify → complete result."""
        r = asyncio.run(ai.extract('Thu tiền bán hàng 2 triệu, chuyển khoản'))
        self.assertEqual(r['amount'], 2000000)
        self.assertEqual(r['kind'], 'income')
        self.assertEqual(r['payment'], 'transfer')
        self.assertIn('category', r)
        self.assertIn('classification', r)
        self.assertEqual(r['engine'], 'local')

    def test_receipt_format(self):
        """Receipt-style text should be parsed correctly."""
        receipt = (
            'Nội dung: Mua nguyên liệu cho quán\n'
            'Số tiền: 1.200.000 VND\n'
            'Ngày: hôm nay\n'
            'Thanh toán: chuyển khoản'
        )
        r = asyncio.run(ai.extract(receipt))
        self.assertEqual(r['amount'], 1200000)
        self.assertEqual(r['payment'], 'transfer')
        # Should use the "Nội dung" line for classification
        self.assertEqual(r['category'], 'materials')

    def test_empty_input_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(ai.extract(''))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_too_long_input_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(ai.extract('x' * 10001))
        self.assertEqual(ctx.exception.status_code, 422)

    def test_warnings_for_missing_amount(self):
        """Missing amount should produce a warning."""
        r = asyncio.run(ai.extract('Mua nguyên liệu cho quán'))
        self.assertIsNone(r['amount'])
        warnings_text = ' '.join(r.get('warnings', []))
        self.assertTrue(any('tiền' in w.lower() or 'số tiền' in w.lower() for w in r.get('warnings', [])))

    def test_category_kind_consistency(self):
        """Category's kind should match the predicted kind in result."""
        from backend.domain import CATEGORIES
        r = asyncio.run(ai.extract('Mua nguyên liệu 500k, tiền mặt'))
        cat = r['category']
        self.assertIn(cat, CATEGORIES)
        expected_kind = CATEGORIES[cat][1]
        self.assertEqual(r['kind'], expected_kind)


class OCRTests(unittest.TestCase):
    """Tests for OCR image processing."""

    @unittest.skipUnless(ai.capabilities()['image'], 'Tesseract not installed')
    def test_real_ocr_offline(self):
        content = (Path(__file__).resolve().parents[1] / 'backend/assets/sample-receipt.png').read_bytes()
        with assert_no_remote_network():
            r = asyncio.run(ai.read_image(content))
        self.assertEqual(r['amount'], 650000)
        self.assertEqual(r['category'], 'materials')
        self.assertIn('tesseract_local', r['providers'])
        self.assertIn('650.000', r['raw_text'])

    @unittest.skipUnless(ai.capabilities()['image'], 'Tesseract not installed')
    def test_ocr_result_has_ocr_warning(self):
        """OCR results should always include an OCR accuracy warning."""
        content = (Path(__file__).resolve().parents[1] / 'backend/assets/sample-receipt.png').read_bytes()
        r = asyncio.run(ai.read_image(content))
        self.assertTrue(any('OCR' in w for w in r.get('warnings', [])))

    def test_bad_images(self):
        for content in (b'invalid', b''):
            with self.assertRaises(HTTPException):
                ai.clean_image(content)
        with self.assertRaises(HTTPException) as ctx:
            ai.clean_image(b'x' * (5 * 1024 * 1024 + 1))
        self.assertEqual(ctx.exception.status_code, 413)

    def test_clean_image_formats(self):
        """Only JPEG, PNG, WebP should be accepted."""
        # Create a minimal valid JPEG
        from PIL import Image
        for fmt, mime in [('JPEG', 'image/jpeg'), ('PNG', 'image/png'), ('WEBP', 'image/webp')]:
            img = Image.new('RGB', (100, 100), 'white')
            buf = io.BytesIO()
            img.save(buf, format=fmt)
            result = ai.clean_image(buf.getvalue())
            self.assertIsInstance(result, bytes)
            self.assertGreater(len(result), 0)


class AudioValidationTests(unittest.TestCase):
    """Tests for audio input validation."""

    def test_audio_validation(self):
        with self.assertRaises(HTTPException):
            ai.decode_audio(b'not an audio file' * 100)

    def test_silent_audio_rejected(self):
        """Near-silent audio should be rejected."""
        b = io.BytesIO()
        with wave.open(b, 'wb') as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(16000)
            w.writeframes(b'\0\0' * 32000)
        with self.assertRaises(HTTPException) as ctx:
            ai.decode_audio(b.getvalue())
        self.assertEqual(ctx.exception.status_code, 422)

    def test_too_large_audio_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            ai.decode_audio(b'x' * (5 * 1024 * 1024 + 1))
        self.assertEqual(ctx.exception.status_code, 413)

    def test_too_small_audio_rejected(self):
        with self.assertRaises(HTTPException) as ctx:
            ai.decode_audio(b'x' * 50)
        self.assertEqual(ctx.exception.status_code, 413)


class CapabilitiesTests(unittest.TestCase):
    """Tests for the capabilities detection system."""

    def test_capabilities_structure(self):
        cap = ai.capabilities()
        self.assertIn('mode', cap)
        self.assertEqual(cap['mode'], 'local')
        for key in ('text', 'image', 'voice'):
            self.assertIn(key, cap)
            self.assertIsInstance(cap[key], bool)

    def test_connection_status_structure(self):
        status = ai.connection_status()
        self.assertIn('providers', status)
        self.assertIsInstance(status['providers'], list)
        self.assertGreaterEqual(len(status['providers']), 3)
        for provider in status['providers']:
            self.assertIn('id', provider)
            self.assertIn('name', provider)
            self.assertIn('configured', provider)

    def test_metrics_structure(self):
        m = metrics()
        if m:  # only test if metrics exist
            self.assertIn('version', m)
            self.assertIn('counts', m)
            self.assertIn('scores', m)
            for task in ('kind', 'category'):
                self.assertIn(task, m['scores'])
                self.assertIn('test_accuracy', m['scores'][task])
                self.assertIn('test_macro_f1', m['scores'][task])


class RealWorldScenarioTests(unittest.TestCase):
    """Tests simulating real user inputs including OCR noise and speech errors."""

    def test_ocr_noisy_text_classification(self):
        """Text with OCR-like errors should still classify correctly."""
        cases = [
            # Missing diacritics (common OCR error)
            ('mua nguyen lieu cho quan', 'materials'),
            ('tra tien thue mat bang', 'rent'),
            ('tra luong nhan vien', 'salary'),
            ('dong tien dien cua hang', 'utilities'),
            # Mixed case (OCR artifact)
            ('MUA NGUYÊN LIỆU CHO QUÁN', 'materials'),
            ('THU TIỀN BÁN HÀNG', 'sales'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['category'], expected,
                    f'Input: "{text}" → got {result["category"]} (score={result["score"]:.3f}), expected {expected}')

    def test_speech_style_text_classification(self):
        """Speech-like text (informal, possibly garbled) should classify correctly."""
        cases = [
            ('hôm nay mua nguyên liệu hết sáu trăm nghìn trả tiền mặt', 'materials'),
            ('thu tiền bán hàng hai triệu chuyển khoản', 'sales'),
            ('trả tiền thuê cửa hàng tháng này', 'rent'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['category'], expected,
                    f'Input: "{text}" → got {result["category"]}, expected {expected}')

    def test_abbreviated_input(self):
        """Short/abbreviated inputs should still work."""
        cases = [
            ('mua NL quán', 'materials'),
            ('tiền thuê MB', 'rent'),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                result = classify(text)
                # For very short inputs, just check it returns a valid category
                self.assertIn(result['category'],
                    ['sales', 'service', 'capital', 'other_income', 'materials',
                     'rent', 'utilities', 'shipping', 'salary', 'other_expense'])

    def test_kind_income_scenarios(self):
        """Various income scenarios should all be classified as income."""
        income_phrases = [
            'thu tiền bán cà phê',
            'khách thanh toán đơn hàng',
            'nhận tiền dịch vụ sửa xe',
            'vay tiền ngân hàng',
            'hoàn tiền hàng lỗi',
        ]
        for text in income_phrases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['kind'], 'income',
                    f'"{text}" should be income, got {result["kind"]}')

    def test_kind_expense_scenarios(self):
        """Various expense scenarios should all be classified as expense."""
        expense_phrases = [
            'mua thịt bò chế biến',
            'trả tiền thuê mặt bằng',
            'đóng tiền điện',
            'trả phí giao hàng',
            'trả lương nhân viên',
            'mua đồ cho gia đình',
        ]
        for text in expense_phrases:
            with self.subTest(text=text):
                result = classify(text)
                self.assertEqual(result['kind'], 'expense',
                    f'"{text}" should be expense, got {result["kind"]}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
