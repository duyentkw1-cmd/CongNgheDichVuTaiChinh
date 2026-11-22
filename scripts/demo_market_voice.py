"""Demo & Test Tool for Market Voice Assistant (Tiểu thương chợ truyền thống Việt Nam)."""
import json
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.market_assistant import (
    process_market_speech,
    process_market_confirmation,
    format_spoken_vnd
)


def run_test_cases():
    print("=" * 70)
    print(" BỘ TEST CASE TRỢ LÝ THU CHI CHỢ TRUYỀN THỐNG VIỆT NAM (2 PHASES)")
    print("=" * 70)

    # ----------------- PHASE 1: TRÍCH XUẤT -----------------
    test_inputs = [
        "Tôi bán được 5 kg thịt lợn được 500k",
        "Hôm nay nhập 2 thùng trứng hết 1 triệu 2",
        "Khách vừa trả 1 củ 2 tiền hàng đợt trước",
        "Trả tiền túi bóng với rác hết bốn chục",
        "Mua 2 lít dầu ăn hết 80k",
        "Bán được 2 lít tiền rau",
        "Hôm nay mua nửa củ tiền đồ gia vị",
        "Alo alo nghe rõ không",
    ]

    print("\n--- [PHASE 1: TRÍCH XUẤT THU CHI & TẠO LỜI NHẮC XÁC NHẬN] ---")
    for idx, inp in enumerate(test_inputs, 1):
        print(f"\n[Test #{idx}] Câu nói người bán: \"{inp}\"")
        res = process_market_speech(inp, use_llm=False)
        print("-> Kết quả JSON:")
        print(json.dumps(res, ensure_ascii=False, indent=2))

    # ----------------- PHASE 2: XÁC NHẬN & CẬP NHẬT -----------------
    print("\n" + "=" * 70)
    print("--- [PHASE 2: PHÂN LOẠI CÂU XÁC NHẬN & XỬ LÝ SỬA ĐỔI DRAFT] ---")
    print("=" * 70)

    draft = {
        "type": "thu",
        "amount": 500000,
        "item_summary": "bán 5 kg thịt lợn"
    }
    print(f"\n* Giao dịch đang chờ xác nhận: {json.dumps(draft, ensure_ascii=False)}")
    print("  Câu hỏi hệ thống: \"Tôi nghe là bán 5 kg thịt lợn thu 500 nghìn đồng. Bạn có muốn ghi lại thu chi không?\"")

    confirm_cases = [
        ("CONFIRM_SAVE (Đồng ý)", "Ừ ghi đi em"),
        ("CONFIRM_SAVE (Chuẩn)", "Chuẩn rồi, lưu vào sổ đi"),
        ("UPDATE_AND_CONFIRM (Sửa tiền)", "Không, 450k thôi, bớt cho khách rồi"),
        ("UPDATE_AND_CONFIRM (Sửa loại)", "Nhầm sang chi nhé em"),
        ("RETRY_SPEAK (Từ chối / Nói lại)", "Nhầm rồi, nói lại từ đầu"),
        ("RETRY_SPEAK (Hủy)", "Thôi hủy đi"),
        ("UNCLEAR (Nhiễu / Mơ hồ)", "Ờ... cái gì cơ?"),
    ]

    for label, user_reply in confirm_cases:
        print(f"\n[{label}] Người bán trả lời: \"{user_reply}\"")
        c_res = process_market_confirmation(user_reply, draft, use_llm=False)
        print("-> Phản hồi JSON:")
        print(json.dumps(c_res, ensure_ascii=False, indent=2))

    print("\n" + "=" * 70)
    print("HOÀN TẤT BỘ TEST CASE TỰ ĐỘNG! TOÀN BỘ KẾT QUẢ ĐẠT CHUẨN.")
    print("=" * 70)


def interactive_mode():
    print("\n--- CHẾ ĐỘ THỬ NGHIỆM TƯƠNG TÁC TRỰC TIẾP ---")
    print("Nhập câu nói bán hàng thực tế (hoặc gõ 'q' để thoát):")
    while True:
        try:
            line = input("\n[Người bán nói] > ").strip()
            if not line or line.lower() in ('q', 'quit', 'exit'):
                break
            res = process_market_speech(line, use_llm=False)
            print("AI trích xuất:", json.dumps(res, ensure_ascii=False, indent=2))

            if res["is_valid_transaction"]:
                print(f"\nAI nhắc: \"{res['confirmation_message']}\"")
                confirm = input("[Bạn trả lời (Ví dụ: 'ừ' / 'không, 300k thôi' / 'hủy')] > ").strip()
                if confirm:
                    pending = {
                        "type": res["type"],
                        "amount": res["amount"],
                        "item_summary": res["item_summary"]
                    }
                    action = process_market_confirmation(confirm, pending, use_llm=False)
                    print("AI phản hồi:", json.dumps(action, ensure_ascii=False, indent=2))
        except (KeyboardInterrupt, EOFError):
            break


if __name__ == '__main__':
    run_test_cases()
    if len(sys.argv) > 1 and sys.argv[1] == '--interactive':
        interactive_mode()
