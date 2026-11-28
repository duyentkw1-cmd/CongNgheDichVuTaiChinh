"""Market voice assistant module for Vietnamese traditional market vendors.

Handles:
1. Transaction extraction from merchant's spoken transcript (Phase 1)
2. Confirmation intent classification & draft updates (Phase 2)
3. TTS-friendly monetary verbalization
4. Fast rule-based matching with optional LLM (Gemini) enhancement
"""
import json
import logging
import os
import re
from typing import Any, Dict, Optional

import httpx

from .domain import fold
from .local_parse import money_candidates, normalize_stt_text

logger = logging.getLogger(__name__)

# System prompts as specified by user requirements
EXTRACTION_SYSTEM_PROMPT = """Bạn là trợ lý ghi sổ thu chi giọng nói cho tiểu thương chợ truyền thống tại Việt Nam.
Nhiệm vụ của bạn là đọc câu nói của người bán hàng, trích xuất thông tin thu/chi, làm sạch mô tả mặt hàng và tạo câu nhắc lại chính xác để người bán xác nhận.

### Quy tắc BẮT BUỘC (Vi phạm sẽ làm hỏng giao diện và giọng đọc):
1. TUYỆT ĐỐI KHÔNG LẶP TỪ HOẶC LẶP SỐ TIỀN:
   - Không bao giờ sinh các câu lặp kiểu: "được 1 triệu được 1 triệu đồng", "hết 100 nghìn hết 100 nghìn đồng", "mua ... mua ...".
   - `confirmation_message` chỉ được nhắc số tiền MỘT LẦN DUY NHẤT ở cuối mệnh đề.

2. Làm sạch `item_summary`:
   - `item_summary` CHỈ chứa: [hành động ngắn gọn: mua/bán/nhập/trả] + [số lượng & tên mặt hàng/khoản mục].
   - TUYỆT ĐỐI KHÔNG chứa số tiền, chữ "k", "nghìn", "ngàn", "triệu", "củ", "đồng", "đ", hoặc các từ chỉ giá/kết quả như "hết", "được", "giá", "tổng", "mất".
   - Sửa lỗi chính tả/đồng âm phổ biến từ STT trong ngữ cảnh chợ nếu rõ nghĩa (ví dụ: "bán bảng 5 kg thịt" -> "bán 5 kg thịt", "mua mua rau" -> "mua rau").

3. Quy đổi `amount` (số nguyên VNĐ) và `amount_text` (cách đọc tiếng Việt tự nhiên cho TTS):
   - "100k" / "100 nghìn" / "100 ngàn" / "một trăm" (ngữ cảnh tiền) -> `amount: 100000`, `amount_text: "100 nghìn đồng"`.
   - "1 triệu" / "một triệu" / "1 củ" -> `amount: 1000000`, `amount_text: "1 triệu đồng"`.
   - "1 triệu 2" / "1 triệu hai" / "1 triệu 200" -> `amount: 1200000`, `amount_text: "1 triệu 200 nghìn đồng"`.
   - "1 triệu rưỡi" -> `amount: 1500000`, `amount_text: "1 triệu 500 nghìn đồng"`.
   - "2 triệu rưỡi" -> `amount: 2500000`, `amount_text: "2 triệu 500 nghìn đồng"`.
   - Nếu không có số tiền rõ ràng -> `amount: null`, `amount_text: null`.

4. Mẫu `confirmation_message` chuẩn:
   - Nếu `is_valid_transaction: true` và `type: "thu"`:
     "Bạn [item_summary] được [amount_text]. Bạn có muốn ghi lại thu chi không?"
   - Nếu `is_valid_transaction: true` và `type: "chi"`:
     "Bạn [item_summary] hết [amount_text]. Bạn có muốn ghi lại thu chi không?"
   - Nếu `is_valid_transaction: false`:
     "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé."

### Định dạng đầu ra BẮT BUỘC (chỉ trả về JSON hợp lệ):
{
  "is_valid_transaction": true,
  "type": "thu",
  "amount": 1000000,
  "item_summary": "bán 5 kg thịt",
  "raw_transcript": "bán bảng 5 kg thịt được 1 triệu",
  "confirmation_message": "Bạn bán 5 kg thịt được 1 triệu đồng. Bạn có muốn ghi lại thu chi không?",
  "next_action": "ASK_CONFIRMATION"
}
"""

CONFIRMATION_SYSTEM_PROMPT = """Bạn là trợ lý xác nhận ghi sổ thu chi cho tiểu thương.
Người bán vừa nghe câu hỏi xác nhận cho giao dịch nháp (`pending_draft`): "Bạn có muốn ghi lại thu chi không?"
Hãy phân loại chính xác câu trả lời của người bán.

### Quy tắc phân loại BẮT BUỘC:
1. `RETRY_SPEAK` (Từ chối / không lưu / muốn nói lại):
   - BẮT BUỘC chọn `RETRY_SPEAK` khi người bán nói các từ/cụm từ từ chối hoặc yêu cầu nói lại, KỂ CẢ KHI CHỈ NÓI MỘT TỪ "Không":
     "không", "không lưu", "không ghi", "không đâu", "không phải", "sai rồi", "nhầm rồi", "nói lại", "nói lại từ đầu", "làm lại", "hủy", "thôi", "bỏ đi".
   - `reply_message`: "Vâng, bạn nói lại khoản thu chi từ đầu nhé."
   - `updated_draft`: `{"type": null, "amount": null, "item_summary": null}`.

2. `CONFIRM_SAVE` (Đồng ý lưu):
   - Khi người bán đồng ý: "có", "có lưu", "ừ", "uh", "đúng rồi", "chuẩn rồi", "lưu đi", "ghi đi", "ok", "oke", "vâng".
   - `reply_message`: "Đã lưu khoản [thu/chi] [amount_text] vào sổ."
   - Giữ nguyên `updated_draft`.

3. `UPDATE_AND_CONFIRM` (Sửa số tiền, mặt hàng hoặc loại thu/chi ngay lúc xác nhận):
   - Khi người bán sửa dữ liệu (ví dụ: "sai bảo chỉ hết 500k thôi", "không, 1 triệu thôi", "sửa thành 200 nghìn", "nhầm thành tiền chi nhé").
   - GHI ĐÈ giá trị mới vào `updated_draft` (ví dụ `amount` = `500000`), KHÔNG giữ giá trị cũ bị sửa và KHÔNG nối câu cũ với câu mới.
   - `reply_message` phải là câu hỏi xác nhận hoàn chỉnh mới (không lặp từ):
     + Nếu `type == "chi"`: "Bạn [item_summary] hết [amount_text]. Bạn có muốn ghi lại thu chi không?"
     + Nếu `type == "thu"`: "Bạn [item_summary] được [amount_text]. Bạn có muốn ghi lại thu chi không?"

4. `UNCLEAR` (Không rõ nghĩa / tiếng ồn):
   - Chỉ dùng khi câu nói hoàn toàn vô nghĩa hoặc nhiễu tiếng ồn không thể xác định đồng ý, từ chối hay sửa.
   - `reply_message`: "Tôi chưa nghe rõ. Bạn nói 'Có' để lưu, hoặc nói 'Không' để nói lại từ đầu nhé."
   - Giữ nguyên `updated_draft`.

### Định dạng đầu ra BẮT BUỘC (chỉ trả về JSON hợp lệ):
{
  "action": "RETRY_SPEAK",
  "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
  "updated_draft": {
    "type": null,
    "amount": null,
    "item_summary": null
  }
}
"""


def format_spoken_vnd(amount: Optional[int]) -> str:
    """Format an integer amount into natural spoken Vietnamese for Text-To-Speech (TTS).

    Avoids reading 'năm không không không không không đồng'.
    Examples:
      500000 -> '500 nghìn đồng'
      1200000 -> '1 triệu 200 nghìn đồng'
      40000 -> '40 nghìn đồng'
      15000000 -> '15 triệu đồng'
    """
    if amount is None or amount <= 0:
        return "0 đồng"

    ty = amount // 1_000_000_000
    rem_ty = amount % 1_000_000_000
    trieu = rem_ty // 1_000_000
    rem_trieu = rem_ty % 1_000_000
    nghin = rem_trieu // 1_000
    dong = rem_trieu % 1_000

    parts = []
    if ty > 0:
        parts.append(f"{ty} tỷ")
    if trieu > 0:
        if ty > 0 and trieu < 100:
            parts.append(f"{trieu:02d} triệu")
        else:
            parts.append(f"{trieu} triệu")
    if nghin > 0:
        if (ty > 0 or trieu > 0) and nghin < 100:
            parts.append(f"{nghin:02d} nghìn")
        else:
            parts.append(f"{nghin} nghìn")
    if dong > 0:
        parts.append(f"{dong} đồng")
    elif parts:
        parts[-1] += " đồng"

    return " ".join(parts)


def parse_market_amount(text: str) -> Optional[int]:
    """Parse monetary expressions common in Vietnamese traditional markets."""
    raw = text.strip()
    folded = fold(raw)

    # 1. Liquid measure distinction: e.g. "2 lit dau an", "2 lit nuoc mam"
    liquid_keywords = r'(dau|nuoc mam|sua|xang|mat ong|ruou|nuoc)'
    is_liquid_measure = bool(re.search(rf'\b(?:\d+|mot|hai|ba|bon|nam)\s+lit\s+{liquid_keywords}\b', folded))

    # 2. Slang unit: cu/chai (1M) -> convert to tr notation for money_candidates
    w2d = {
        'mot': '1', 'hai': '2', 'ba': '3', 'bon': '4', 'tu': '4',
        'nam': '5', 'sau': '6', 'bay': '7', 'tam': '8', 'chin': '9'
    }
    num_token = r'(?:mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|\d+)'

    def cu_repl(m):
        d1 = w2d.get(m.group(1), m.group(1))
        d2 = w2d.get(m.group(2), m.group(2))
        return f'{d1}tr{d2}'

    # "1 cu 2", "mot cu hai", "1 chai 2" -> "1tr2"
    folded = re.sub(rf'\b({num_token})\s*(?:cu|chai)\s*({num_token})\b', cu_repl, folded)
    # "1 trieu 2", "mot trieu hai" -> "1tr2"
    folded = re.sub(rf'\b({num_token})\s*(?:trieu)\s*({num_token})\b', cu_repl, folded)

    # "1 cu", "mot cu" -> "1 trieu"
    folded = re.sub(rf'\b({num_token})\s+(?:cu|chai)\b', lambda m: f"{w2d.get(m.group(1), m.group(1))} trieu", folded)
    folded = re.sub(r'\bnua\s+(?:cu|chai|trieu)\b', '500k', folded)

    # 3. Slang unit: lit/xi/lop (100k) if NOT a liquid measure
    if not is_liquid_measure:
        # "2 lit" -> "200k"
        folded = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:lit|xi|lop)\s+ruoi\b', r'\1 tram nam muoi nghin', folded)
        folded = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:lit|xi|lop)\b', r'\1 tram nghin', folded)
        folded = re.sub(r'\b(?:lit|xi|lop)\s+ruoi\b', 'mot tram nam muoi nghin', folded)
        folded = re.sub(r'\b(?:lit|xi|lop)\b', 'mot tram nghin', folded)

    # 4. "chuc" -> "hai chuc" = 20k, "bon chuc" = 40k
    chuc_map = {
        'mot': 10000, 'hai': 20000, 'ba': 30000, 'bon': 40000, 'tu': 40000,
        'nam': 50000, 'sau': 60000, 'bay': 70000, 'tam': 80000, 'chin': 90000
    }
    m_chuc = re.search(r'\b(mot|hai|ba|bon|tu|nam|sau|bay|tam|chin|\d+)\s+chuc\b', folded)
    if m_chuc:
        word = m_chuc.group(1)
        if word in chuc_map:
            val = chuc_map[word]
            folded = re.sub(r'\b' + word + r'\s+chuc\b', f'{val} dong', folded)
        elif word.isdigit():
            val = int(word) * 10000
            folded = re.sub(r'\b' + word + r'\s+chuc\b', f'{val} dong', folded)

    # Normalize STT common misspellings
    normalized = normalize_stt_text(folded)

    # Parse candidates using engine
    candidates = money_candidates(normalized, bare=True)
    if candidates:
        return candidates[-1]

    return None


def build_confirmation_message(tx_type: Optional[str], item_summary: Optional[str], amount: Optional[int]) -> str:
    """Build a natural, non-repetitive Vietnamese confirmation prompt for TTS."""
    if not tx_type or not amount:
        return "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé."

    amount_str = format_spoken_vnd(amount)
    raw_desc = (item_summary or ("thu tiền" if tx_type == "thu" else "mua hàng")).strip()
    if raw_desc:
        raw_desc = raw_desc[0].lower() + raw_desc[1:]
    folded_desc = fold(raw_desc)

    if re.match(r'^khach\b', folded_desc):
        subject_desc = raw_desc[0].upper() + raw_desc[1:]
        verb = "được" if tx_type == "thu" else "hết"
        return f"{subject_desc} {verb} {amount_str}. Bạn có muốn ghi lại thu chi không?"

    if re.match(r'^(mua|ban|nhap|tra|chi|thu)\b', folded_desc):
        verb = "được" if tx_type == "thu" else "hết"
        return f"Bạn {raw_desc} {verb} {amount_str}. Bạn có muốn ghi lại thu chi không?"

    if tx_type == "thu":
        return f"Bạn bán {raw_desc} được {amount_str}. Bạn có muốn ghi lại thu chi không?"
    return f"Bạn mua {raw_desc} hết {amount_str}. Bạn có muốn ghi lại thu chi không?"


def extract_item_summary(raw_transcript: str) -> Optional[str]:
    """Extract a concise item description from the transcript, preserving item & units.

    RULE: item_summary must NEVER contain monetary amounts, currency units,
    or price-related words like 'hết', 'được', 'giá'.
    """
    text = raw_transcript.strip()
    folded_full = fold(text)
    liquid_keywords = r'(dau|nuoc mam|sua|xang|mat ong|ruou|nuoc)'
    is_liquid_measure = bool(re.search(rf'\b(?:\d+|mot|hai|ba|bon|nam)\s+lit\s+{liquid_keywords}\b', folded_full))

    # 1. Remove conversational prefixes
    clean = re.sub(r'^(?:tôi|anh|chị|em|cô|bác|vừa|hôm nay|nay|sáng nay|chiều nay)\s+', '', text, flags=re.I).strip()

    # 1.1 Sửa lỗi STT nói lắp lặp từ đầu câu: "mua mua rau" -> "mua rau", "bán bán 5kg" -> "bán 5kg"
    clean = re.sub(r'(?i)\b(mua|bán|nhập|trả|chi|thu)\s+\1\b', r'\1', clean)
    # Sửa lỗi STT lẫn từ đệm / rác chợ: "bán bảng 5 kg" -> "bán 5 kg", "mua vào" -> "mua"
    clean = re.sub(r'(?i)\b(bán|ban)\s+(?:bảng|bang|con|cái|chiếc)\s+(\d+)', r'\1 \2', clean)
    clean = re.sub(r'(?i)\b(bán|ban)\s+bảng\b', r'\1', clean)
    clean = re.sub(r'(?i)\b(bán|ban|thu)\s+(?:được|duoc)\b', r'\1', clean)

    vn_num = r'(?:một|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin|muoi|\d+)'

    # 2. Strip complex compound currency words first
    clean = re.sub(rf'(?i)\b{vn_num}\s*(?:củ|cu|chai|triệu|trieu)\s*(?:rưỡi|ruoi|{vn_num})\b', '', clean)
    clean = re.sub(rf'(?i)\b{vn_num}\s*(?:trăm|tram)\s*(?:rưỡi|ruoi)\b', '', clean)
    clean = re.sub(r'(?i)\b(?:nửa\s+(?:củ|cu|triệu|trieu))\b', '', clean)
    clean = re.sub(rf'(?i)\b{vn_num}\s+(?:chục|chuc)\b', '', clean)
    if not is_liquid_measure:
        clean = re.sub(rf'(?i)\b(?:{vn_num}\s+)?(?:lít|lit|xị|xi|lốp|lop)(?:\s+(?:rưỡi|ruoi))?\b', '', clean)

    # 3. Strip bare decimal-formatted numbers: 600.000, 1.200.000, 600,000
    clean = re.sub(r'\b\d{1,3}(?:[.,]\d{3})+\b', '', clean)

    # 4. Strip bare large numbers (4+ digits like 600000, 1200000)
    clean = re.sub(r'\b\d{4,}\b', '', clean)

    # 5. Strip trailing amount cue: [được|hết|mất|giá|thu|chi] <amount>$
    clean = re.sub(
        r'(?i)\s+(?:được|hết|mất|thu|chi|giá)?\s*(?:\d+[\d.,]*\s*(?:\bk\b|vnd|đồng|dong|đ|nghìn|nghin|ngàn|ngan|triệu|trieu|tr|củ|cu|chai|lít|lit|chục|chuc|trăm|tram)|\b\d+k\b)\s*$',
        '',
        clean
    )

    # 6. Remove any remaining isolated price words (number + currency unit)
    clean = re.sub(
        r'(?i)\b(?:\d+[\d.,]*\s*(?:\bk\b|vnd|đồng|dong|đ|nghìn|nghin|ngàn|ngan|triệu|trieu|tr|củ|cu|chai|chục|chuc))\b',
        '',
        clean
    )

    # 7. Remove Vietnamese spoken money words: "sáu trăm nghìn", "một triệu hai trăm nghìn đồng"
    clean = re.sub(
        rf'(?i)(?:{vn_num}\s+)*(?:trăm|tram)\s+(?:{vn_num}\s+)*(?:nghìn|nghin|ngàn|ngan|triệu|trieu)(?:\s+đồng|\s+dong)?',
        '',
        clean
    )
    clean = re.sub(
        rf'(?i)(?:{vn_num}\s+)+(?:nghìn|nghin|ngàn|ngan|triệu|trieu)(?:\s+đồng|\s+dong)?',
        '',
        clean
    )
    clean = re.sub(rf'(?i)\b{vn_num}\s*(?:triệu|trieu|củ|cu)\b', '', clean)

    # 8. Clean isolated stray currency characters, price cues before punctuation, and dangling punctuation
    clean = re.sub(r'(?i)\b(?:đ|vnd|dong|đồng)\b', '', clean)
    clean = re.sub(r'(?i)\s*\b(?:với giá|mất hết|được|hết|mất|giá|tổng)\b\s*(?=[,.;]|$)', '', clean)
    clean = re.sub(r'\s*([,.;])\s*', r'\1 ', clean)
    clean = re.sub(r'\s{2,}', ' ', clean).strip(' ,.;:-')
    clean = re.sub(r'\s+(?:được|hết|mất|giá|thu|chi|với giá|tổng|mất hết)$', '', clean, flags=re.I).strip(' ,.;:-')
    clean = re.sub(r'^(?:được|hết|mất)\s+', '', clean, flags=re.I).strip(' ,.;:-')

    if len(clean) >= 3 and not re.fullmatch(r'^[0-9\s.,kđ]+$', clean):
        return clean

    return None


def extract_transaction_rules(transcript: str) -> Dict[str, Any]:
    """Fast, local rule-based extractor for Phase 1.

    Zero latency, runs offline.
    """
    transcript = transcript.strip()
    folded = fold(transcript)

    # Non-transaction greetings / noise
    unclear_cues = ['alo', 'test', 'thu mic', 'nghe ro khong', 'nghe thay khong', 'xin chao', 'chao ban', 'hello', 'hi']
    has_noise = any(re.search(rf'\b{c}\b', folded) for c in unclear_cues)
    has_finance_keyword = bool(re.search(r'\b(ban|mua|nhap|tra|thu|chi|dong|nop|lay|tien)\b', folded))

    if (has_noise and not has_finance_keyword) or len(folded) < 4:
        return {
            "is_valid_transaction": False,
            "type": None,
            "amount": None,
            "item_summary": None,
            "raw_transcript": transcript,
            "confirmation_message": "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé.",
            "next_action": "ASK_CLARIFICATION"
        }

    # Determine transaction type (thu / chi)
    is_khach_tra = bool(re.search(
        r'\bkhach\s+(?:\w+\s+)?(tra|dua|gui|chuyen|thanh toan|lay|mua)\b',
        folded
    ))

    income_cue = is_khach_tra or bool(re.search(
        r'\b(ban|ban duoc|thu|thu no|nhan tien|tien ve|ban le|ban si|thu tien)\b',
        folded
    ))
    expense_cue = bool(re.search(
        r'\b(mua|nhap|tra|tra tien|tra no|nop|chi|tien sap|tien dien|tien nuoc|tui bong|tien rac|rac|bao bi|hoan tien|ship|lay hang|ton|mat het|het)\b',
        folded
    ))

    is_outgoing_refund = bool(re.search(
        r'\b(hoan tien|hoan lai|boi thuong|den bu|tra no|tra lai)\b',
        folded
    )) and not bool(re.search(
        r'\b(duoc hoan|nha cung cap|ncc|dai ly|hang|bao hiem|san)\b',
        folded
    ))

    if is_outgoing_refund:
        tx_type = "chi"
    elif is_khach_tra:
        tx_type = "thu"
    elif income_cue and not expense_cue:
        tx_type = "thu"
    elif expense_cue and not income_cue:
        tx_type = "chi"
    elif income_cue and expense_cue:
        if re.search(r'\b(ban|khach)\b', folded):
            tx_type = "thu"
        else:
            tx_type = "chi"
    else:
        tx_type = None

    amount = parse_market_amount(transcript)
    item_summary = extract_item_summary(transcript)

    if not tx_type or not amount:
        return {
            "is_valid_transaction": False,
            "type": tx_type,
            "amount": amount,
            "item_summary": item_summary,
            "raw_transcript": transcript,
            "confirmation_message": "Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé.",
            "next_action": "ASK_CLARIFICATION"
        }

    msg = build_confirmation_message(tx_type, item_summary, amount)

    return {
        "is_valid_transaction": True,
        "type": tx_type,
        "amount": amount,
        "item_summary": item_summary or transcript,
        "raw_transcript": transcript,
        "confirmation_message": msg,
        "next_action": "ASK_CONFIRMATION"
    }


def handle_confirmation_rules(confirmation_transcript: str, pending_draft: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Fast, local rule-based confirmation classifier for Phase 2."""
    text = confirmation_transcript.strip()
    clean_punct = re.sub(r'[^\w\s]', '', text.lower()).strip()
    clean_folded = fold(clean_punct)
    draft = dict(pending_draft or {})

    # Check for question/unclear expressions first
    if re.search(r'\b(gi co|sao co|cai gi|ha|sao|the nao|khong ro|o\b)', clean_folded):
        return {
            "action": "UNCLEAR",
            "reply_message": "Tôi chưa nghe rõ bạn đồng ý lưu hay muốn sửa. Bạn nói 'Lưu' hoặc nói lại giúp tôi nhé.",
            "updated_draft": draft
        }

    # 1. UPDATE_AND_CONFIRM: Rejection or change with new amount or changed type
    has_new_amount = parse_market_amount(text) is not None
    m_type_change = re.search(
        r'\b(?:doi|chuyen|sua|sang|thanh|la|nham(?:\s+thanh|\s+sang)?|khoan)\s+(?:khoan\s+)?(chi|thu)\b',
        clean_folded
    )
    has_type_change = bool(m_type_change)

    if has_new_amount or has_type_change:
        new_amount = parse_market_amount(text) or draft.get('amount')
        new_type = draft.get('type')
        if m_type_change:
            new_type = m_type_change.group(1)

        updated = {
            "type": new_type,
            "amount": new_amount,
            "item_summary": draft.get('item_summary') or "giao dịch"
        }
        amount_spoken = format_spoken_vnd(new_amount)
        action_word = "thu" if new_type == "thu" else "chi"
        return {
            "action": "UPDATE_AND_CONFIRM",
            "reply_message": f"Tôi cập nhật lại là {updated['item_summary']} {action_word} {amount_spoken}. Bạn có muốn ghi lại không?",
            "updated_draft": updated
        }

    # 2. CONFIRM_SAVE: Clear agreement
    confirm_tokens = {
        'có', 'co', 'ừ', 'u', 'uh', 'vâng', 'vang', 'dạ', 'da', 'dạ có', 'da co', 'dạ vâng', 'da vang',
        'đúng rồi', 'dung roi', 'đúng', 'dung',
        'lưu đi', 'luu di', 'lưu', 'luu', 'ghi đi', 'ghi di', 'ghi', 'ghi vao',
        'ok', 'oke', 'okay', 'chuẩn', 'chuan', 'chuẩn rồi', 'chuan roi',
        'được', 'duoc', 'được rồi', 'duoc roi', 'chính xác', 'chinh xac',
        'yes', 'lưu luôn', 'luu luon', 'ghi luôn', 'ghi luon', 'đồng ý', 'dong y'
    }

    is_confirmed = (
        clean_folded in confirm_tokens
        or clean_punct in confirm_tokens
        or any(clean_folded.startswith(c + ' ') for c in confirm_tokens)
    )

    if is_confirmed and not any(w in clean_folded for w in ['khong', 'thoi', 'huy', 'nham', 'sai']):
        amt = draft.get('amount')
        amt_str = format_spoken_vnd(amt) if amt else ""
        item_name = draft.get('item_summary') or ""
        t_type = "khoản thu" if draft.get('type') == 'thu' else "khoản chi"
        reply = f"Đã lưu {t_type} {item_name} {amt_str} vào sổ.".replace("  ", " ").strip()
        return {
            "action": "CONFIRM_SAVE",
            "reply_message": reply,
            "updated_draft": draft
        }

    # 3. RETRY_SPEAK: Clear cancellation or retry request without new data
    retry_tokens = {
        'không', 'khong', 'không phải', 'khong phai', 'không đúng', 'khong dung',
        'chưa đúng', 'chua dung', 'nhầm rồi', 'nham roi',
        'nhầm', 'nham', 'sai rồi', 'sai roi', 'sai', 'nói lại', 'noi lai',
        'làm lại', 'lam lai', 'thôi', 'thoi', 'hủy', 'huy', 'bỏ đi', 'bo di', 'bỏ qua', 'bo qua',
        'không lưu', 'khong luu', 'đừng lưu', 'dung luu', 'từ từ', 'tu tu',
        'không nhé', 'khong nhe', 'không đâu', 'khong dau', 'không ghi', 'khong ghi'
    }

    is_retry = (
        clean_folded in retry_tokens
        or clean_punct in retry_tokens
        or any(clean_folded.startswith(r + ' ') for r in retry_tokens)
        or clean_folded == 'không'
        or clean_folded == 'khong'
        or clean_folded.startswith('khong ')
        or clean_folded.startswith('không ')
    )

    if is_retry:
        return {
            "action": "RETRY_SPEAK",
            "reply_message": "Vâng, bạn nói lại khoản thu chi từ đầu nhé.",
            "updated_draft": {"type": None, "amount": None, "item_summary": None}
        }

    # 4. UNCLEAR
    return {
        "action": "UNCLEAR",
        "reply_message": "Tôi chưa nghe rõ bạn đồng ý lưu hay muốn sửa. Bạn nói 'Lưu' hoặc nói lại giúp tôi nhé.",
        "updated_draft": draft
    }


def call_gemini_api(system_prompt: str, user_prompt: str) -> Optional[Dict[str, Any]]:
    """Optional LLM enhancement via Gemini API if key is available and network accessible."""
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return None

    models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest', 'gemini-3.8-flash']
    payload = {
        "contents": [{
            "parts": [
                {"text": f"{system_prompt}\n\n{user_prompt}"}
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        try:
            with httpx.Client(timeout=4.0) as client:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_text = data['candidates'][0]['content']['parts'][0]['text'].strip()
                    clean = re.sub(r'^```(?:json)?\s*', '', raw_text, flags=re.MULTILINE)
                    clean = re.sub(r'```$', '', clean, flags=re.MULTILINE).strip()
                    return json.loads(clean)
        except Exception as e:
            logger.debug("Gemini call error on model %s: %s", model, e)
            continue

    return None


def process_market_speech(transcript: str, use_llm: bool = True) -> Dict[str, Any]:
    """Process merchant's spoken input for Phase 1."""
    if use_llm:
        user_input = f'### Dữ liệu đầu vào hiện tại:\nInput: "{transcript}"'
        llm_res = call_gemini_api(EXTRACTION_SYSTEM_PROMPT, user_input)
        if llm_res and isinstance(llm_res, dict) and "is_valid_transaction" in llm_res:
            return llm_res

    return extract_transaction_rules(transcript)


def process_market_confirmation(confirmation_transcript: str, pending_draft: Optional[Dict[str, Any]] = None, use_llm: bool = True) -> Dict[str, Any]:
    """Process merchant's confirmation response for Phase 2."""
    rule_res = handle_confirmation_rules(confirmation_transcript, pending_draft)
    if rule_res["action"] in ("CONFIRM_SAVE", "RETRY_SPEAK"):
        return rule_res

    if use_llm and rule_res["action"] == "UNCLEAR":
        user_input = (
            f"### Giao dịch đang chờ xác nhận:\n{json.dumps(pending_draft or {}, ensure_ascii=False)}\n\n"
            f'### Câu trả lời của người bán:\n"{confirmation_transcript}"'
        )
        llm_res = call_gemini_api(CONFIRMATION_SYSTEM_PROMPT, user_input)
        if llm_res and isinstance(llm_res, dict) and "action" in llm_res:
            return llm_res

    return rule_res
