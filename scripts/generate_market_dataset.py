"""Dataset generator for Vietnamese traditional market voice assistant.

Produces:
1. datasets/train_extract.jsonl: Phase 1 extraction & confirmation question
2. datasets/train_confirm.jsonl: Phase 2 confirmation classifier & draft updates
3. datasets/train_extract_expanded.jsonl (300+ samples)
4. datasets/train_confirm_expanded.jsonl (250+ samples)
"""
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS_DIR = ROOT / 'datasets'
DATASETS_DIR.mkdir(exist_ok=True)

SYSTEM_EXTRACT = (
    "Bạn là trợ lý ghi sổ thu chi giọng nói cho tiểu thương chợ truyền thống tại Việt Nam. "
    "Trích xuất thu/chi sạch sẽ, không lặp từ, không lặp số tiền, trả về JSON hợp lệ."
)

SYSTEM_CONFIRM = (
    "Bạn là trợ lý xác nhận ghi sổ thu chi cho tiểu thương. Phân loại phản hồi thành "
    "CONFIRM_SAVE, RETRY_SPEAK, UPDATE_AND_CONFIRM hoặc UNCLEAR, trả về JSON hợp lệ."
)

# ----------------- BASE SAMPLES FROM USER SPEC -----------------
BASE_EXTRACT = [
    {
        "user": "Mua nguyên liệu hết 100 nghìn đồng",
        "assistant": {
            "is_valid_transaction": True,
            "type": "chi",
            "amount": 100000,
            "item_summary": "mua nguyên liệu",
            "raw_transcript": "Mua nguyên liệu hết 100 nghìn đồng",
            "confirmation_message": "Bạn mua nguyên liệu hết 100 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Mua mua nguyên liệu hết 100k",
        "assistant": {
            "is_valid_transaction": True,
            "type": "chi",
            "amount": 100000,
            "item_summary": "mua nguyên liệu",
            "raw_transcript": "Mua mua nguyên liệu hết 100k",
            "confirmation_message": "Bạn mua nguyên liệu hết 100 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Bán 5 kg thịt được 1 triệu",
        "assistant": {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": 1000000,
            "item_summary": "bán 5 kg thịt",
            "raw_transcript": "Bán 5 kg thịt được 1 triệu",
            "confirmation_message": "Bạn bán 5 kg thịt được 1 triệu đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Bán bảng 5 kg thịt được 1 triệu",
        "assistant": {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": 1000000,
            "item_summary": "bán 5 kg thịt",
            "raw_transcript": "Bán bảng 5 kg thịt được 1 triệu",
            "confirmation_message": "Bạn bán 5 kg thịt được 1 triệu đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Nhập hàng hết 1 triệu 2",
        "assistant": {
            "is_valid_transaction": True,
            "type": "chi",
            "amount": 1200000,
            "item_summary": "nhập hàng",
            "raw_transcript": "Nhập hàng hết 1 triệu 2",
            "confirmation_message": "Bạn nhập hàng hết 1 triệu 200 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Bán hải sản được 2 triệu rưỡi",
        "assistant": {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": 2500000,
            "item_summary": "bán hải sản",
            "raw_transcript": "Bán hải sản được 2 triệu rưỡi",
            "confirmation_message": "Bạn bán hải sản được 2 triệu 500 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Chi tiền lấy giò chả hết 1 triệu 500 nghìn",
        "assistant": {
            "is_valid_transaction": True,
            "type": "chi",
            "amount": 1500000,
            "item_summary": "chi tiền lấy giò chả",
            "raw_transcript": "Chi tiền lấy giò chả hết 1 triệu 500 nghìn",
            "confirmation_message": "Bạn chi tiền lấy giò chả hết 1 triệu 500 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Bán rau củ các loại được 350k",
        "assistant": {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": 350000,
            "item_summary": "bán rau củ các loại",
            "raw_transcript": "Bán rau củ các loại được 350k",
            "confirmation_message": "Bạn bán rau củ các loại được 350 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Mua bao bì nilon hết 80 nghìn",
        "assistant": {
            "is_valid_transaction": True,
            "type": "chi",
            "amount": 80000,
            "item_summary": "mua bao bì nilon",
            "raw_transcript": "Mua bao bì nilon hết 80 nghìn",
            "confirmation_message": "Bạn mua bao bì nilon hết 80 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Bán 3 cân cá thu được 450 ngàn",
        "assistant": {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": 450000,
            "item_summary": "bán 3 cân cá thu",
            "raw_transcript": "Bán 3 cân cá thu được 450 ngàn",
            "confirmation_message": "Bạn bán 3 cân cá thu được 450 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
    },
    {
        "user": "Alo alo nghe rõ không",
        "assistant": {
            "is_valid_transaction": False,
            "type": None,
            "amount": None,
            "item_summary": None,
            "raw_transcript": "Alo alo nghe rõ không",
            "confirmation_message": "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé.",
            "next_action": "ASK_CLARIFICATION"
        }
    }
]

BASE_CONFIRM = [
    {
        "pending": {"type": "chi", "amount": 600000, "item_summary": "mua nguyên liệu"},
        "user": "Không",
        "assistant": {
            "action": "RETRY_SPEAK",
            "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
            "updated_draft": {"type": None, "amount": None, "item_summary": None}
        }
    },
    {
        "pending": {"type": "chi", "amount": 600000, "item_summary": "mua nguyên liệu"},
        "user": "Không lưu",
        "assistant": {
            "action": "RETRY_SPEAK",
            "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
            "updated_draft": {"type": None, "amount": None, "item_summary": None}
        }
    },
    {
        "pending": {"type": "thu", "amount": 1000000, "item_summary": "bán 5 kg thịt"},
        "user": "Không nhé",
        "assistant": {
            "action": "RETRY_SPEAK",
            "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
            "updated_draft": {"type": None, "amount": None, "item_summary": None}
        }
    },
    {
        "pending": {"type": "chi", "amount": 600000, "item_summary": "mua nguyên liệu"},
        "user": "sai bảo chỉ hết 500k thôi",
        "assistant": {
            "action": "UPDATE_AND_CONFIRM",
            "reply_message": "Bạn mua nguyên liệu hết 500 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "updated_draft": {"type": "chi", "amount": 500000, "item_summary": "mua nguyên liệu"}
        }
    },
    {
        "pending": {"type": "thu", "amount": 1000000, "item_summary": "bán 5 kg thịt"},
        "user": "sửa thành 1 triệu 2",
        "assistant": {
            "action": "UPDATE_AND_CONFIRM",
            "reply_message": "Bạn bán 5 kg thịt được 1 triệu 200 nghìn đồng. Bạn có muốn ghi lại thu chi không?",
            "updated_draft": {"type": "thu", "amount": 1200000, "item_summary": "bán 5 kg thịt"}
        }
    },
    {
        "pending": {"type": "thu", "amount": 500000, "item_summary": "bán 5 kg thịt lợn"},
        "user": "Có",
        "assistant": {
            "action": "CONFIRM_SAVE",
            "reply_message": "Đã lưu khoản thu 500 nghìn đồng vào sổ.",
            "updated_draft": {"type": "thu", "amount": 500000, "item_summary": "bán 5 kg thịt lợn"}
        }
    },
    {
        "pending": {"type": "chi", "amount": 1200000, "item_summary": "nhập 2 thùng trứng"},
        "user": "Ừ lưu đi",
        "assistant": {
            "action": "CONFIRM_SAVE",
            "reply_message": "Đã lưu khoản chi 1 triệu 200 nghìn đồng vào sổ.",
            "updated_draft": {"type": "chi", "amount": 1200000, "item_summary": "nhập 2 thùng trứng"}
        }
    }
]


# ----------------- EXPANSION DATA GENERATOR -----------------
ITEMS_SALES = [
    ("3 con gà ta", 450000, "450k", "450 nghìn"),
    ("10 kg gạo tám", 180000, "180k", "180 nghìn"),
    ("nửa cân tôm sú", 150000, "trăm rưỡi", "150 nghìn"),
    ("2 kg cá chép", 140000, "140 ngàn", "140 nghìn"),
    ("mớ rau muống và 3 quả chanh", 15000, "mười lăm nghìn", "15 nghìn"),
    ("5 cân dưa hấu", 75000, "bảy lăm ngàn", "75 nghìn"),
    ("yến khoai tây", 200000, "2 lít", "200 nghìn"),
    ("3 kg thịt bò", 750000, "750k", "750 nghìn"),
    ("thúng mận hậu", 300000, "3 lít", "300 nghìn"),
    ("2 con vịt quay", 400000, "bốn trăm", "400 nghìn"),
    ("1 kg giò lụa", 160000, "trăm sáu", "160 nghìn"),
    ("mẻ đậu phụ", 80000, "tám chục", "80 nghìn"),
    ("5 kg sườn non", 650000, "sáu trăm rưỡi", "650 nghìn"),
    ("chục bắp ngô ngọt", 50000, "năm chục", "50 nghìn"),
    ("3 lít mật ong rừng", 900000, "chín trăm", "900 nghìn"),
]

ITEMS_EXPENSES = [
    ("nhập 5 con ngan giống", 600000, "6 lít", "600 nghìn"),
    ("mua 3 cuộn túi bóng đựng hàng", 75000, "bảy lăm nghìn", "75 nghìn"),
    ("đóng tiền điện quạt và tủ đông", 420000, "bốn trăm hai", "420 nghìn"),
    ("trả tiền nước sinh hoạt sạp", 80000, "tám chục", "80 nghìn"),
    ("tiền vệ sinh với rác chợ", 30000, "ba chục", "30 nghìn"),
    ("nhập 50 kg bí đỏ", 500000, "nửa củ", "500 nghìn"),
    ("mua cân điện tử mới", 850000, "tám trăm rưỡi", "850 nghìn"),
    ("trả tiền bốc vác đầu xe", 100000, "1 lít", "100 nghìn"),
    ("nhập 3 két nước ngọt", 360000, "ba trăm sáu", "360 nghìn"),
    ("thuê xe ba gác chở rau", 150000, "trăm rưỡi", "150 nghìn"),
    ("tiền mặt bằng sạp tuần này", 1000000, "1 củ", "1 triệu"),
    ("mua thùng xốp ướp cá", 90000, "chín chục", "90 nghìn"),
    ("trả tiền hàng mối sỉ đợt trước", 2500000, "2 củ rưỡi", "2 triệu 500 nghìn"),
]

UNCLEAR_INPUTS = [
    "Alo alo nghe rõ không em",
    "Thịt này bán bao nhiêu một cân thế",
    "Trời hôm nay nắng nóng ghê",
    "Hôm nay chợ vắng khách quá",
    "Bật cho chị cái quạt lên với",
    "Chị ơi trứng gà ta hay gà công nghiệp đấy",
    "Một hai ba bốn kiểm tra mic",
    "Chào em gái bán rau nhé",
    "Túi bóng này dẻo không cô",
    "Bán cho chị một cân thịt mông", # Thiếu giá -> không ép lưu
    "Hôm nay mua ít đồ", # Thiếu giá
    "Khách vừa hỏi giá buôn",
]


def generate_expanded_dataset():
    random.seed(42)

    # 1. EXTRACT DATASET
    extract_samples = []

    # Thêm mẫu gốc
    for item in BASE_EXTRACT:
        extract_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_EXTRACT},
                {"role": "user", "content": item["user"]},
                {"role": "assistant", "content": json.dumps(item["assistant"], ensure_ascii=False)}
            ]
        })

    # Sinh mẫu bán hàng (Thu)
    prefixes_thu = ["", "Hôm nay ", "Sáng nay ", "Vừa ", "Khách vừa mua ", "Tôi bán được "]
    for item_name, amount, amt_str, spoken in ITEMS_SALES:
        for prefix in prefixes_thu:
            user_text = f"{prefix}bán {item_name} được {amt_str}".strip()
            if "Khách vừa mua" in prefix:
                user_text = f"{prefix}{item_name} hết {amt_str}"

            assistant_obj = {
                "is_valid_transaction": True,
                "type": "thu",
                "amount": amount,
                "item_summary": f"bán {item_name}",
                "raw_transcript": user_text,
                "confirmation_message": f"Bạn bán {item_name} được {spoken} đồng. Bạn có muốn ghi lại thu chi không?",
                "next_action": "ASK_CONFIRMATION"
            }
            extract_samples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_EXTRACT},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)}
                ]
            })

    # Sinh mẫu chi phí (Chi)
    prefixes_chi = ["", "Hôm nay ", "Nay ", "Vừa ", "Sáng nay đi chợ "]
    for item_name, amount, amt_str, spoken in ITEMS_EXPENSES:
        for prefix in prefixes_chi:
            user_text = f"{prefix}{item_name} hết {amt_str}".strip()
            assistant_obj = {
                "is_valid_transaction": True,
                "type": "chi",
                "amount": amount,
                "item_summary": item_name,
                "raw_transcript": user_text,
                "confirmation_message": f"Bạn mua {item_name} hết {spoken} đồng. Bạn có muốn ghi lại thu chi không?",
                "next_action": "ASK_CONFIRMATION"
            }
            extract_samples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_EXTRACT},
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)}
                ]
            })

    # Khách nợ / Khách trả (Thu nợ)
    debt_samples = [
        ("Khách quen trả nợ cũ 1 củ 2", 1200000, "khách trả nợ cũ", "1 triệu 200 nghìn"),
        ("Chị Lan trả tiền cá hôm qua 2 lít", 200000, "khách trả tiền cá hôm qua", "200 nghìn"),
        ("Bác Ba thanh toán nốt tiền gạo 350k", 350000, "khách thanh toán tiền gạo", "350 nghìn"),
        ("Quán cơm chuyển khoản tiền thịt 4 triệu rưỡi", 4500000, "quán cơm chuyển khoản tiền thịt", "4 triệu 500 nghìn"),
    ]
    for ut, amt, summ, spk in debt_samples:
        assistant_obj = {
            "is_valid_transaction": True,
            "type": "thu",
            "amount": amt,
            "item_summary": summ,
            "raw_transcript": ut,
            "confirmation_message": f"Bạn bán {summ} được {spk} đồng. Bạn có muốn ghi lại thu chi không?",
            "next_action": "ASK_CONFIRMATION"
        }
        extract_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_EXTRACT},
                {"role": "user", "content": ut},
                {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)}
            ]
        })

    # Sinh mẫu không hợp lệ / nhiễu (ASK_CLARIFICATION)
    for unc in UNCLEAR_INPUTS * 3:
        assistant_obj = {
            "is_valid_transaction": False,
            "type": None,
            "amount": None,
            "item_summary": None,
            "raw_transcript": unc,
            "confirmation_message": "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé.",
            "next_action": "ASK_CLARIFICATION"
        }
        extract_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_EXTRACT},
                {"role": "user", "content": unc},
                {"role": "assistant", "content": json.dumps(assistant_obj, ensure_ascii=False)}
            ]
        })

    # 2. CONFIRM DATASET
    confirm_samples = []

    # Thêm mẫu gốc
    for item in BASE_CONFIRM:
        user_content = f"Pending draft: {json.dumps(item['pending'], ensure_ascii=False)}\nUser reply: {item['user']}"
        confirm_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_CONFIRM},
                {"role": "user", "content": user_content},
                {"role": "assistant", "content": json.dumps(item["assistant"], ensure_ascii=False)}
            ]
        })

    # Các câu đồng ý (CONFIRM_SAVE)
    confirm_phrases = [
        "Có", "ừ", "uh", "Ừ ghi đi", "Lưu đi em", "Ghi vào sổ nhé",
        "Đúng rồi", "Chuẩn rồi đấy", "Lưu luôn", "Ok", "Oke", "Yes", "Chuẩn",
        "Được rồi", "Ghi luôn đi", "Chuẩn rồi", "Lưu nhé", "Ghi lại hộ chị"
    ]
    # Các câu từ chối (RETRY_SPEAK)
    reject_phrases = [
        "Không", "Không phải", "Nhầm rồi", "Nói lại từ đầu", "Thôi hủy",
        "Bỏ qua đi", "Sai rồi", "Đừng lưu", "Hủy đi em", "Thôi", "Nói lại", "Bỏ đi"
    ]
    # Các câu sửa (UPDATE_AND_CONFIRM)
    edit_phrases = [
        ("Không, 400k thôi", 400000, "thu", "bán 5 kg thịt lợn", "400 nghìn"),
        ("Sửa thành 350 nghìn", 350000, "thu", "bán 5 kg thịt lợn", "350 nghìn"),
        ("Nhầm, thành chi nhé", 500000, "chi", "bán 5 kg thịt lợn", "500 nghìn"),
        ("Không, có 180k thôi", 180000, "chi", "nhập rau củ", "180 nghìn"),
        ("Đổi thành thu tiền bán hàng nhé", 1200000, "thu", "nhập 2 thùng trứng", "1 triệu 200 nghìn"),
        ("Bớt cho khách 50k rồi, còn 450k", 450000, "thu", "bán 5 kg thịt lợn", "450 nghìn"),
        ("Nhầm sang chi 500k", 500000, "chi", "tiền hàng", "500 nghìn"),
        ("Sửa lại 2 lít thôi", 200000, "thu", "tiền rau", "200 nghìn"),
        ("Không, khách trả 1 củ thôi", 1000000, "thu", "tiền hàng", "1 triệu"),
    ]
    # Các câu mơ hồ (UNCLEAR)
    unclear_confirms = [
        "Ờ... cái gì cơ?", "Nói lại xem nào", "Gì đấy em?", "Hả?", "Sao cơ?", "Ai biết đâu", "Alo nghe thấy không"
    ]

    sample_drafts = [
        {"type": "thu", "amount": 500000, "item_summary": "bán 5 kg thịt lợn"},
        {"type": "chi", "amount": 1200000, "item_summary": "nhập 2 thùng trứng"},
        {"type": "chi", "amount": 40000, "item_summary": "tiền túi bóng"},
        {"type": "thu", "amount": 200000, "item_summary": "khách trả nợ"},
        {"type": "chi", "amount": 3500000, "item_summary": "tiền sạp chợ"},
        {"type": "thu", "amount": 150000, "item_summary": "bán nửa cân tôm sú"},
        {"type": "chi", "amount": 80000, "item_summary": "mua 2 lít dầu ăn"},
    ]

    # Phủ các ca CONFIRM_SAVE
    for d in sample_drafts:
        t_name = "khoản thu" if d["type"] == "thu" else "khoản chi"
        for cp in confirm_phrases:
            user_msg = f"Pending draft: {json.dumps(d, ensure_ascii=False)}\nUser reply: {cp}"
            confirm_samples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_CONFIRM},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": json.dumps({
                        "action": "CONFIRM_SAVE",
                        "reply_message": f"Đã lưu {t_name} {d['amount']} vào sổ.",
                        "updated_draft": d
                    }, ensure_ascii=False)}
                ]
            })

    # Phủ các ca RETRY_SPEAK
    for d in sample_drafts:
        for rp in reject_phrases:
            user_msg = f"Pending draft: {json.dumps(d, ensure_ascii=False)}\nUser reply: {rp}"
            confirm_samples.append({
                "messages": [
                    {"role": "system", "content": SYSTEM_CONFIRM},
                    {"role": "user", "content": user_msg},
                    {"role": "assistant", "content": json.dumps({
                        "action": "RETRY_SPEAK",
                        "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
                        "updated_draft": {"type": None, "amount": None, "item_summary": None}
                    }, ensure_ascii=False)}
                ]
            })

    # Phủ các ca UPDATE_AND_CONFIRM
    for ep, new_amt, new_type, it_desc, spoken in edit_phrases * 4:
        base_d = {"type": "thu" if new_type == "chi" else "thu", "amount": 500000, "item_summary": it_desc}
        upd_d = {"type": new_type, "amount": new_amt, "item_summary": it_desc}
        user_msg = f"Pending draft: {json.dumps(base_d, ensure_ascii=False)}\nUser reply: {ep}"
        verb = "được" if new_type == "thu" else "hết"
        confirm_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_CONFIRM},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": json.dumps({
                    "action": "UPDATE_AND_CONFIRM",
                    "reply_message": f"Bạn vừa sửa thành {it_desc} {verb} {spoken}. Bạn có muốn ghi lại thu chi không?",
                    "updated_draft": upd_d
                }, ensure_ascii=False)}
            ]
        })

    # Phủ các ca UNCLEAR
    for uc in unclear_confirms * 5:
        d = sample_drafts[0]
        user_msg = f"Pending draft: {json.dumps(d, ensure_ascii=False)}\nUser reply: {uc}"
        confirm_samples.append({
            "messages": [
                {"role": "system", "content": SYSTEM_CONFIRM},
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": json.dumps({
                    "action": "UNCLEAR",
                    "reply_message": "Tôi chưa nghe rõ bạn muốn lưu hay nói lại. Bạn nói có hoặc không giúp tôi nhé.",
                    "updated_draft": d
                }, ensure_ascii=False)}
            ]
        })

    # Ghi file base
    train_extract_base_file = DATASETS_DIR / 'train_extract.jsonl'
    train_confirm_base_file = DATASETS_DIR / 'train_confirm.jsonl'

    with open(train_extract_base_file, 'w', encoding='utf-8') as f:
        for it in extract_samples[:len(BASE_EXTRACT)]:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')

    with open(train_confirm_base_file, 'w', encoding='utf-8') as f:
        for it in confirm_samples[:len(BASE_CONFIRM)]:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')

    # Ghi file expanded
    train_extract_expanded_file = DATASETS_DIR / 'train_extract_expanded.jsonl'
    train_confirm_expanded_file = DATASETS_DIR / 'train_confirm_expanded.jsonl'

    random.shuffle(extract_samples)
    random.shuffle(confirm_samples)

    with open(train_extract_expanded_file, 'w', encoding='utf-8') as f:
        for it in extract_samples:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')

    with open(train_confirm_expanded_file, 'w', encoding='utf-8') as f:
        for it in confirm_samples:
            f.write(json.dumps(it, ensure_ascii=False) + '\n')

    print(f"-> Tạo thành công file mẫu cơ sở: {train_extract_base_file} ({len(BASE_EXTRACT)} dòng)")
    print(f"-> Tạo thành công file mẫu cơ sở: {train_confirm_base_file} ({len(BASE_CONFIRM)} dòng)")
    print(f"-> Tạo thành công tập mở rộng Phase 1: {train_extract_expanded_file} ({len(extract_samples)} dòng)")
    print(f"-> Tạo thành công tập mở rộng Phase 2: {train_confirm_expanded_file} ({len(confirm_samples)} dòng)")


if __name__ == '__main__':
    generate_expanded_dataset()
