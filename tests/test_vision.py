import json
import unittest
from unittest.mock import patch, MagicMock
from backend import ai
from backend.domain import today


class TestVisionIntegration(unittest.TestCase):
    def test_category_mapping(self):
        self.assertEqual(ai._map_vision_category('Nguyên liệu / nhập hàng'), 'materials')
        self.assertEqual(ai._map_vision_category('Chi khác'), 'other_expense')
        self.assertEqual(ai._map_vision_category('Thuê mặt bằng'), 'rent')
        self.assertEqual(ai._map_vision_category('Điện, nước, Internet'), 'utilities')
        self.assertEqual(ai._map_vision_category('Vận chuyển'), 'shipping')
        self.assertEqual(ai._map_vision_category('Lương nhân viên'), 'salary')
        self.assertEqual(ai._map_vision_category('Tiền bán hàng', 'income'), 'sales')
        self.assertEqual(ai._map_vision_category('Dịch vụ', 'income'), 'service')

    def test_date_parsing(self):
        self.assertEqual(ai._parse_vision_date('2026-10-24'), '2026-10-24')
        self.assertEqual(ai._parse_vision_date('24/10/2026'), '2026-10-24')
        self.assertEqual(ai._parse_vision_date('24-10-2026'), '2026-10-24')
        self.assertEqual(ai._parse_vision_date('invalid'), str(today()))

    @patch('httpx.post')
    def test_gemini_vision_ocr_success(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': json.dumps([{
                            'type': 'Chi',
                            'date': '2026-10-24',
                            'description': 'Đậu tẩm hành, Nem phùng, Bia ca, Lẩu ếch nhỏ',
                            'amount': 523000,
                            'category': 'Chi khác',
                            'store_name': 'BIA PHƯƠNG TRANG'
                        }])
                    }]
                }
            }]
        }
        mock_post.return_value = mock_resp

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
            result = ai.gemini_vision_ocr(b'fake-image-bytes')
            self.assertIsNotNone(result)
            self.assertEqual(result['amount'], 523000)
            self.assertEqual(result['date'], '2026-10-24')
            self.assertEqual(result['category'], 'other_expense')
            self.assertEqual(result['kind'], 'expense')
            self.assertIn('BIA PHƯƠNG TRANG', result['description'])
            self.assertEqual(result['engine'], 'gemini_vision')

    @patch('httpx.post')
    def test_gemini_vision_multi_items(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            'candidates': [{
                'content': {
                    'parts': [{
                        'text': json.dumps([
                            {'type': 'Chi', 'date': '2026-10-24', 'description': 'Đậu tẩm hành', 'amount': 59000, 'category': 'Chi khác', 'store_name': 'BIA PHƯƠNG TRANG'},
                            {'type': 'Chi', 'date': '2026-10-24', 'description': 'Nem phùng', 'amount': 40000, 'category': 'Chi khác', 'store_name': 'BIA PHƯƠNG TRANG'},
                            {'type': 'Chi', 'date': '2026-10-24', 'description': 'Bia ca', 'amount': 75000, 'category': 'Chi khác', 'store_name': 'BIA PHƯƠNG TRANG'},
                            {'type': 'Chi', 'date': '2026-10-24', 'description': 'Lẩu ếch nhỏ', 'amount': 349000, 'category': 'Chi khác', 'store_name': 'BIA PHƯƠNG TRANG'}
                        ])
                    }]
                }
            }]
        }
        mock_post.return_value = mock_resp

        with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake-key'}):
            result = ai.gemini_vision_ocr(b'fake-image-bytes')
            self.assertIsNotNone(result)
            self.assertEqual(result['amount'], 523000)
            self.assertEqual(len(result['items']), 4)
            self.assertEqual(result['items'][0]['description'], 'Đậu tẩm hành')
            self.assertEqual(result['items'][0]['amount'], 59000)
            self.assertEqual(result['items'][3]['description'], 'Lẩu ếch nhỏ')
            self.assertEqual(result['items'][3]['amount'], 349000)


if __name__ == '__main__':
    unittest.main()
