"""Receipt parsing on OCR text taken from real photos (text only, no images)."""
import unittest

from tests import _isolation  # noqa: F401
from backend import ai


class ReceiptAmountTests(unittest.TestCase):
    def test_phone_number_is_not_the_amount(self):
        # OCR lost the "T" of "Tổng" and the header has a phone number.
        text = ('PHAN MEM BAN HANG\nMs Nhị: 0936456103 - 0971926241\nHOA ĐƠN BAN HANG\n'
                'Ngày: 3/11/2018 Số phiếu: 18000015\nBanh da nem 1 chiếc 4,000 4,000\n'
                'Me thái 2 Gói 80,000 160,000\nBộ cốc 3 Cái 60,000 180,000\n“ổng : 360,000 te')
        self.assertEqual(ai.receipt_amount(text)[0], 360000)
        r = ai.analyze_receipt(text)
        self.assertEqual(r['amount'], 360000)
        self.assertEqual(r['date'], '2018-11-03')
        self.assertEqual(r['kind'], 'expense')

    def test_invoice_number_ignored_in_fallback(self):
        text = 'HOÁ ĐƠN BÁN HÀNG\n230232362\nÁo sơ mi 500.000 1 20.000 480.000\nQuần tây 500.000 1 30.000 470.000'
        self.assertEqual(ai.receipt_amount(text), (500000, False))

    def test_restaurant_total_beats_promotion_and_change_lines(self):
        text = ('HOA DON THANH TOAN\nNgày: 26/06/2026 (10:27 SA - 09:02 CH)\nBàn: 01\n'
                'Tiền hàng 16.160.100\nKhuyến mại 8.080.050\nTổng thanh toán 8.031.570\n'
                'Chuyển khoản 8.000.000\nBớt tiền lẻ cho khách 31.570')
        r = ai.analyze_receipt(text)
        self.assertEqual(r['amount'], 8031570)
        self.assertEqual(r['date'], '2026-06-26')
        self.assertEqual(r['payment'], 'transfer')
        self.assertNotIn('Bàn', r['description'])

    def test_glued_dong_sign_and_shipping_total(self):
        text = ('PHIEU GUI HANG\nNgày: 23/11/2026\nCước vận chuyển 56.000\nPhụ phí 15.000\n'
                'Tổng cước 71.0004\nTiền khách đưa 100.0004\nTiền thừa 29.0004')
        text = ai.normalize_receipt_ocr(text)
        r = ai.analyze_receipt(text)
        self.assertEqual(r['amount'], 71000)
        self.assertEqual(r['category'], 'shipping')

    def test_reason_line_with_wrong_accent(self):
        text = 'PHIẾU CHI\nSố: PC424\nLý do chị: Trả lương nhân viên tháng 8\n15/02/2026\nSố tiền 7.700.000 VND'
        r = ai.analyze_receipt(text)
        self.assertEqual(r['amount'], 7700000)
        self.assertEqual(r['category'], 'salary')
        self.assertEqual(r['description'], 'Trả lương nhân viên tháng 8')

    def test_dictionary_repairs_accents_and_one_char_errors(self):
        c = ai.correct_receipt_words
        self.assertEqual(c('Tién khéch dua 800.000đ'), 'Tiền khách đưa 800.000đ')
        self.assertEqual(c('HOA DON BAN HANG'), 'HÓA ĐƠN BÁN HÀNG')
        self.assertEqual(c('Tong cang 290.000'), 'Tổng cộng 290.000')
        self.assertEqual(c('Tra luong nhan vién thang 7'), 'Trả lương nhân viên tháng 7')

    def test_dictionary_leaves_ambiguous_words(self):
        c = ai.correct_receipt_words
        self.assertEqual(c('Bàn: 01'), 'Bàn: 01')          # bàn (table) vs bán (sell)
        self.assertEqual(c('Sửa xe 50.000'), 'Sửa xe 50.000')  # sửa vs sữa
        self.assertEqual(c('Cà chua 20.000'), 'Cà chua 20.000')

    def test_spelled_out_date(self):
        r = ai.analyze_receipt('HÓA ĐƠN BÁN LẺ\nNgày 08 tháng 08 năm 2026\nDầu ăn 73.000\nThanh toán 73.000')
        self.assertEqual(r['date'], '2026-08-08')


    def test_bank_transfer_and_discount_receipt(self):
        bank = (
            'Chuyển tiền thành công\n-500.000 VND\nTrạng thái\nThành công\n'
            'Thời gian\n14:22 - 18/11/2026\nMã giao dịch\nFT26325901842\n'
            'Nội dung\nĐóng tiền điện tháng 11\nPhí giao dịch\n0 VND'
        )
        rb = ai.analyze_receipt(bank)
        self.assertEqual(rb['amount'], 500000)
        self.assertEqual(rb['date'], '2026-11-18')
        self.assertEqual(rb['category'], 'utilities')
        self.assertEqual(rb['description'], 'Đóng tiền điện tháng 11')

        disc = (
            'TẠP HÓA MINH AN\nNgày: 10/11/2026\nGạo thơm (2 x 120.000) 240.000đ\n'
            'Tạm tính 240.000đ\nGiảm giá -30.000đ\nThuế VAT 21.000đ\n'
            'Khách phải thanh toán 231.000đ\nTiền khách đưa 500.000đ\nTiền thừa 269.000đ'
        )
        rd = ai.analyze_receipt(disc)
        self.assertEqual(rd['amount'], 231000)
        self.assertEqual(rd['date'], '2026-11-10')


if __name__ == '__main__':
    unittest.main()
