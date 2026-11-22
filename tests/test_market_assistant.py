"""Tests for market voice assistant (tiểu thương chợ truyền thống) & endpoints."""
import unittest

from backend.main import MarketConfirmInput, MarketExtractInput, market_confirm, market_extract
from backend.market_assistant import (
    extract_transaction_rules,
    format_spoken_vnd,
    handle_confirmation_rules,
    parse_market_amount,
    process_market_confirmation,
    process_market_speech,
)


class TestMarketAssistant(unittest.TestCase):

    def test_spoken_vnd(self):
        self.assertEqual(format_spoken_vnd(500000), "500 nghìn đồng")
        self.assertEqual(format_spoken_vnd(1200000), "1 triệu 200 nghìn đồng")
        self.assertEqual(format_spoken_vnd(40000), "40 nghìn đồng")
        self.assertEqual(format_spoken_vnd(1000000), "1 triệu đồng")
        self.assertEqual(format_spoken_vnd(15000000), "15 triệu đồng")

    def test_market_amounts_and_slang(self):
        # 500k
        self.assertEqual(parse_market_amount("500k"), 500000)
        # 1 củ 2 = 1.200.000
        self.assertEqual(parse_market_amount("1 củ 2"), 1200000)
        self.assertEqual(parse_market_amount("một củ hai"), 1200000)
        # nửa củ = 500.000
        self.assertEqual(parse_market_amount("nửa củ"), 500000)
        # năm trăm rưỡi = 550.000
        self.assertEqual(parse_market_amount("năm trăm rưỡi"), 550000)
        # 2 lít = 200.000
        self.assertEqual(parse_market_amount("bán được 2 lít"), 200000)
        # 2 lít dầu ăn hết 80k -> 80.000 (không nhầm 2 lít dầu ăn là tiền 200k)
        self.assertEqual(parse_market_amount("mua 2 lít dầu ăn hết 80k"), 80000)
        # bốn chục = 40.000
        self.assertEqual(parse_market_amount("bốn chục"), 40000)
        # hai chục = 20.000
        self.assertEqual(parse_market_amount("hai chục"), 20000)
        # 1 triệu 2 = 1.200.000
        self.assertEqual(parse_market_amount("1 triệu 2"), 1200000)

    def test_phase1_extractions(self):
        # 1. Bán thịt lợn
        res1 = extract_transaction_rules("Tôi bán được 5 kg thịt lợn được 500k")
        self.assertTrue(res1["is_valid_transaction"])
        self.assertEqual(res1["type"], "thu")
        self.assertEqual(res1["amount"], 500000)
        self.assertIn("5 kg thịt lợn", res1["item_summary"])
        # item_summary must NOT contain monetary amounts
        self.assertNotIn("500", res1["item_summary"])
        self.assertNotIn("k", res1["item_summary"].lower().split()[-1:])
        self.assertEqual(res1["next_action"], "ASK_CONFIRMATION")
        self.assertIn("500 nghìn", res1["confirmation_message"])
        # New template: "Bạn bán..." not "Tôi nghe là..."
        self.assertTrue(res1["confirmation_message"].startswith("Bạn bán"))

        # 2. Nhập trứng
        res2 = extract_transaction_rules("Hôm nay nhập 2 thùng trứng hết 1 triệu 2")
        self.assertTrue(res2["is_valid_transaction"])
        self.assertEqual(res2["type"], "chi")
        self.assertEqual(res2["amount"], 1200000)
        self.assertIn("2 thùng trứng", res2["item_summary"])
        self.assertEqual(res2["next_action"], "ASK_CONFIRMATION")
        self.assertIn("1 triệu 200 nghìn", res2["confirmation_message"])
        # Avoid repeat: "Bạn nhập 2 thùng trứng..." not "Bạn mua nhập 2 thùng trứng..."
        self.assertTrue(res2["confirmation_message"].startswith("Bạn nhập"))

        # 3. Tiền sạp / rác
        res3 = extract_transaction_rules("Trả tiền túi bóng với rác hết bốn chục")
        self.assertTrue(res3["is_valid_transaction"])
        self.assertEqual(res3["type"], "chi")
        self.assertEqual(res3["amount"], 40000)
        self.assertIn("túi bóng", res3["item_summary"])
        self.assertEqual(res3["next_action"], "ASK_CONFIRMATION")
        self.assertIn("40 nghìn", res3["confirmation_message"])

        # 4. Khách trả tiền
        res4 = extract_transaction_rules("Khách vừa trả 1 củ 2 tiền hàng đợt trước")
        self.assertTrue(res4["is_valid_transaction"])
        self.assertEqual(res4["type"], "thu")
        self.assertEqual(res4["amount"], 1200000)
        self.assertEqual(res4["next_action"], "ASK_CONFIRMATION")

        # 5. Câu nhiễu / không rõ
        res5 = extract_transaction_rules("Alo alo nghe rõ không")
        self.assertFalse(res5["is_valid_transaction"])
        self.assertIsNone(res5["type"])
        self.assertIsNone(res5["amount"])
        self.assertEqual(res5["next_action"], "ASK_CLARIFICATION")

        # 6. Mua nguyên liệu 600.000 - item_summary must NOT contain "600.000"
        res6 = extract_transaction_rules("Mua nguyên liệu hết 600k")
        self.assertTrue(res6["is_valid_transaction"])
        self.assertEqual(res6["type"], "chi")
        self.assertEqual(res6["amount"], 600000)
        if res6["item_summary"]:
            self.assertNotIn("600", res6["item_summary"])
        self.assertTrue(res6["confirmation_message"].startswith("Bạn mua"))

        # 7. Sửa lỗi nói lặp từ & nhiễu từ STT: "bán bảng 5 kg thịt được 1 triệu"
        res7 = extract_transaction_rules("bán bảng 5 kg thịt được 1 triệu")
        self.assertTrue(res7["is_valid_transaction"])
        self.assertEqual(res7["type"], "thu")
        self.assertEqual(res7["amount"], 1000000)
        self.assertEqual(res7["item_summary"], "bán 5 kg thịt")
        self.assertEqual(res7["confirmation_message"], "Bạn bán 5 kg thịt được 1 triệu đồng. Bạn có muốn ghi lại thu chi không?")

        # 8. Sửa lỗi lặp "mua mua": "mua mua 5 kilôgam thịt hết đ 100 nghìn"
        res8 = extract_transaction_rules("mua mua 5 kilôgam thịt hết đ 100 nghìn")
        self.assertTrue(res8["is_valid_transaction"])
        self.assertEqual(res8["type"], "chi")
        self.assertEqual(res8["amount"], 100000)
        self.assertEqual(res8["item_summary"], "mua 5 kilôgam thịt")
        self.assertEqual(res8["confirmation_message"], "Bạn mua 5 kilôgam thịt hết 100 nghìn đồng. Bạn có muốn ghi lại thu chi không?")

    def test_phase2_confirmation_actions(self):
        draft = {
            "type": "thu",
            "amount": 500000,
            "item_summary": "bán 5 kg thịt lợn"
        }

        # 1. CONFIRM_SAVE
        for phrase in ["ừ", "có", "uh", "đúng rồi", "lưu đi", "ghi đi", "ok", "chuẩn"]:
            res = handle_confirmation_rules(phrase, draft)
            self.assertEqual(res["action"], "CONFIRM_SAVE", f"Failed for {phrase}")
            self.assertIn("Đã lưu", res["reply_message"])
            self.assertEqual(res["updated_draft"]["amount"], 500000)

        # 2. RETRY_SPEAK
        for phrase in ["không", "không phải", "nhầm rồi", "nói lại", "thôi", "hủy"]:
            res = handle_confirmation_rules(phrase, draft)
            self.assertEqual(res["action"], "RETRY_SPEAK", f"Failed for {phrase}")
            # RETRY_SPEAK must clear the draft
            self.assertIsNotNone(res["updated_draft"])
            self.assertIsNone(res["updated_draft"]["type"])
            self.assertIsNone(res["updated_draft"]["amount"])
            self.assertIsNone(res["updated_draft"]["item_summary"])

        # 3. UPDATE_AND_CONFIRM (sửa tiền)
        res_update = handle_confirmation_rules("không, 450k thôi", draft)
        self.assertEqual(res_update["action"], "UPDATE_AND_CONFIRM")
        self.assertEqual(res_update["updated_draft"]["amount"], 450000)
        self.assertIn("450 nghìn", res_update["reply_message"])

        # Sửa loại giao dịch sang chi
        res_type_update = handle_confirmation_rules("nhầm thành chi nhé", draft)
        self.assertEqual(res_type_update["action"], "UPDATE_AND_CONFIRM")
        self.assertEqual(res_type_update["updated_draft"]["type"], "chi")

        # 4. UNCLEAR
        res_unclear = handle_confirmation_rules("ờ... gì cơ", draft)
        self.assertEqual(res_unclear["action"], "UNCLEAR")

    def test_api_handlers(self):
        # 1. Test market_extract
        req1 = MarketExtractInput(transcript="Tôi bán được 5 kg thịt lợn được 500k", use_llm=False)
        res1 = market_extract(req1)
        self.assertTrue(res1["is_valid_transaction"])
        self.assertEqual(res1["type"], "thu")
        self.assertEqual(res1["amount"], 500000)
        self.assertEqual(res1["next_action"], "ASK_CONFIRMATION")

        # 2. Test market_confirm with CONFIRM_SAVE
        pending = {
            "type": res1["type"],
            "amount": res1["amount"],
            "item_summary": res1["item_summary"]
        }
        req2 = MarketConfirmInput(
            confirmation_transcript="Ừ lưu đi",
            pending_draft=pending,
            use_llm=False
        )
        res2 = market_confirm(req2)
        self.assertEqual(res2["action"], "CONFIRM_SAVE")
        self.assertIn("Đã lưu", res2["reply_message"])

        # 3. Test market_confirm with UPDATE_AND_CONFIRM
        req3 = MarketConfirmInput(
            confirmation_transcript="Không, 450k thôi",
            pending_draft=pending,
            use_llm=False
        )
        res3 = market_confirm(req3)
        self.assertEqual(res3["action"], "UPDATE_AND_CONFIRM")
        self.assertEqual(res3["updated_draft"]["amount"], 450000)


if __name__ == "__main__":
    unittest.main()
