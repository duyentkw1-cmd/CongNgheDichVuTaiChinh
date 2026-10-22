"""Reproducible SYNTHETIC educational data. No real household records.

One semantic seed and all its variants belong to one split. Never split variants
randomly: this leaks almost identical sentences from train into evaluation.

v2: Greatly expanded augmentation — OCR‑noise, speech‑noise, casual Vietnamese,
abbreviations, synonyms, and more templates per seed.
"""
import csv
import json
import random
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ml.text import normalize

# 24 independently authored semantic seeds per category; last 8 held out.
SEEDS = {
 'sales': [
  'Thu tiền bán hàng tại quầy', 'Khách trả tiền mua cà phê của tiệm',
  'Bán bánh mì được tiền', 'Doanh thu bán đồ uống buổi sáng',
  'Nhận tiền bán cơm cho khách', 'Bán một thùng nước ngọt',
  'Khách thanh toán đơn hàng mua quần áo', 'Thu từ bán đồ gia dụng',
  'Tiền bán rau ngoài chợ', 'Bán mỹ phẩm nhận tiền mặt',
  'Thu tiền bán hàng qua mạng', 'Doanh thu bán sữa và bánh',
  'Khách chuyển tiền mua sản phẩm', 'Bán giày dép cho khách',
  'Thu tiền đơn hàng mang đi', 'Bán thịt trong buổi chiều',
  'Khách đã trả tiền mua chai nước', 'Cửa hàng bán gạo thu được tiền',
  'Tiền thu bán áo đồng phục', 'Doanh thu tại quầy trà sữa',
  'Nhận thanh toán hàng hóa đã bán', 'Bán hoa nhận tiền từ khách',
  'Thu doanh số bán cà phê cuối ngày', 'Tiệm bán sách cho khách thanh toán'],
 'service': [
  'Thu tiền dịch vụ sửa xe', 'Khách trả phí cắt tóc',
  'Nhận tiền giặt là quần áo', 'Thu phí sửa điện thoại cho khách',
  'Khách thanh toán tiền sửa máy tính', 'Thu từ dịch vụ giao hàng thuê',
  'Nhận tiền làm móng tay', 'Thu phí vệ sinh máy lạnh',
  'Tiền công may áo cho khách', 'Khách trả công sửa giày',
  'Thu phí chụp ảnh sản phẩm', 'Nhận tiền thiết kế biển hiệu cho khách',
  'Thu tiền rửa xe', 'Khách thanh toán dịch vụ in tài liệu',
  'Thu phí tư vấn lắp đặt thiết bị', 'Nhận tiền gia công theo đơn',
  'Thu phí sửa khóa cho khách', 'Tiền công bọc ghế khách vừa trả',
  'Thu từ dịch vụ gội đầu', 'Khách trả tiền sửa đồ điện',
  'Thu tiền công lắp camera', 'Nhận phí dịch vụ chăm sóc cây',
  'Khách thanh toán công thêu áo', 'Thu tiền làm dịch vụ bảo dưỡng xe'],
 'capital': [
  'Chủ tiệm bổ sung vốn vào quỹ', 'Nhận tiền vay ngân hàng',
  'Vay người thân để nhập hàng', 'Góp thêm vốn kinh doanh',
  'Nhận khoản vay từ bạn', 'Chuyển tiền tiết kiệm vào vốn cửa hàng',
  'Đối tác góp vốn mở tiệm', 'Nhận giải ngân khoản vay',
  'Chủ hộ nộp tiền vốn', 'Bổ sung vốn lưu động',
  'Mượn tiền anh trai để kinh doanh', 'Vốn góp của thành viên mới',
  'Nhận tiền vay hợp tác xã', 'Tăng vốn của cửa hàng',
  'Chủ quán đưa thêm tiền đầu tư', 'Vay vốn mua thiết bị',
  'Nhận vốn đầu tư từ gia đình', 'Ngân hàng chuyển tiền khoản vay kinh doanh',
  'Tiền mượn để duy trì quán', 'Bổ sung tiền chủ sở hữu vào quỹ',
  'Nhận vốn góp từ chị gái', 'Vay thêm tiền để mở rộng tiệm',
  'Nhận tiền mượn của bố mẹ làm vốn', 'Chủ cửa hàng góp thêm tiền'],
 'other_income': [
  'Ngân hàng trả lãi tiền gửi', 'Nhận tiền hoàn cọc thuê nhà',
  'Thu hồi khoản cho mượn trước đây', 'Nhà cung cấp hoàn tiền hàng lỗi',
  'Nhận tiền bồi thường hàng hỏng', 'Tiền thưởng từ nhà phân phối',
  'Thu bán phế liệu của cửa hàng', 'Nhận tiền hỗ trợ kinh doanh',
  'Đơn vị vận chuyển hoàn phí giao hàng', 'Thu tiền thanh lý kệ cũ',
  'Được hoàn tiền điện đóng thừa', 'Nhận lại tiền bảo đảm hợp đồng',
  'Khách bồi thường đồ làm vỡ', 'Thu lãi từ khoản tiền gửi',
  'Nhận khoản chiết khấu nhà cung cấp trả lại', 'Hoàn lại tiền đặt cọc thiết bị',
  'Thu thanh lý bàn ghế cũ', 'Nhận khoản bồi hoàn từ bảo hiểm',
  'Người quen trả lại khoản nợ cho tiệm', 'Được nhận trợ cấp kinh doanh',
  'Thu tiền lãi ngân hàng tháng này', 'Hoàn cọc mặt bằng về quỹ',
  'Nhà bán hàng trả lại khoản thanh toán thừa', 'Nhận tiền bán bao bì phế liệu'],
 'materials': [
  'Mua cà phê và sữa để pha bán', 'Nhập hàng quần áo từ xưởng',
  'Mua nguyên liệu cho quán', 'Thanh toán tiền nhập rau thịt',
  'Mua bột mì làm bánh', 'Nhập thùng nước ngọt để bán',
  'Chi tiền mua gạo cho tiệm cơm', 'Trả tiền nhà cung cấp nguyên liệu',
  'Mua thịt bò chế biến món ăn', 'Nhập lô mỹ phẩm về cửa hàng',
  'Mua trái cây để pha nước', 'Thanh toán lô hàng nhập kho',
  'Mua đường và đá cho quán nước', 'Nhập giày dép bán tại chợ',
  'Mua hộp đựng đồ ăn bán cho khách', 'Chi tiền mua hạt cà phê',
  'Nhập sữa tươi về pha chế', 'Mua gạo và dầu ăn cho bếp quán',
  'Thanh toán hàng hóa nhập từ đại lý', 'Chi mua trân châu làm trà sữa',
  'Mua hoa tươi để bán', 'Nhập sách về tiệm',
  'Trả tiền nguyên liệu bánh ngọt', 'Mua trà và siro bổ sung kho'],
 'rent': [
  'Trả tiền thuê mặt bằng', 'Thanh toán tiền thuê cửa hàng',
  'Chi thuê nhà để kinh doanh', 'Đóng tiền thuê quầy chợ',
  'Trả tiền thuê kho chứa hàng', 'Thanh toán tiền thuê ki ốt',
  'Chi phí mặt bằng tháng này', 'Chuyển tiền thuê gian hàng',
  'Nộp tiền thuê địa điểm bán hàng', 'Trả chủ nhà tiền thuê quán',
  'Thanh toán thuê xưởng sản xuất', 'Tiền thuê sạp bán rau',
  'Chi thuê phòng làm tiệm tóc', 'Trả tiền thuê chỗ bán cà phê',
  'Thuê nhà kho cho cửa hàng', 'Thanh toán hợp đồng thuê mặt bằng',
  'Chi tiền thuê chỗ kinh doanh', 'Đóng phí thuê quán ăn',
  'Trả chủ sạp tiền thuê tháng', 'Thanh toán thuê khu bán hàng',
  'Chuyển khoản tiền thuê tiệm', 'Nộp tiền thuê vị trí mở quầy',
  'Trả phí thuê kho cất hàng', 'Thanh toán mặt bằng cho chủ nhà'],
 'utilities': [
  'Đóng tiền điện cửa hàng', 'Trả tiền nước sinh hoạt của quán',
  'Thanh toán cước internet', 'Chi tiền mạng wifi của tiệm',
  'Đóng hóa đơn điện tháng này', 'Thanh toán tiền nước máy',
  'Nạp cước điện thoại phục vụ bán hàng', 'Trả phí mạng cáp quang',
  'Chi tiền điện cho máy lạnh cửa hàng', 'Thanh toán điện nước mặt bằng',
  'Trả cước đường truyền internet', 'Tiền nước dùng rửa ly trong quán',
  'Thanh toán cước viễn thông cửa hàng', 'Đóng tiền điện sản xuất',
  'Trả phí wifi hàng tháng', 'Chi hóa đơn nước kinh doanh',
  'Chuyển tiền điện cho điện lực', 'Thanh toán mạng internet tại quán',
  'Trả tiền sử dụng nước của tiệm', 'Đóng cước điện thoại cửa hàng',
  'Chi phí điện thắp sáng quầy', 'Thanh toán hóa đơn cấp nước',
  'Trả phí thuê bao mạng cho tiệm', 'Nộp tiền điện nước quán ăn'],
 'shipping': [
  'Trả phí giao hàng cho khách', 'Chi tiền vận chuyển hàng nhập',
  'Thanh toán cước gửi bưu kiện', 'Trả tiền ship đơn hàng',
  'Chi phí thuê xe chở hàng', 'Thanh toán phí chuyển phát nhanh',
  'Trả tiền giao đơn cho shipper', 'Chi cước bưu điện gửi hàng',
  'Thuê xe tải chở nguyên liệu', 'Trả phí vận chuyển từ kho về tiệm',
  'Thanh toán công giao hàng', 'Chi tiền gửi hàng liên tỉnh',
  'Trả cước xe giao sản phẩm', 'Thanh toán phí chở hàng cho khách',
  'Chi phí giao đồ ăn', 'Trả phí chuyển hàng cho đơn vị vận tải',
  'Chi tiền thuê người giao đơn', 'Thanh toán cước chuyển hàng đường bộ',
  'Trả phí ship cho cửa hàng', 'Chi tiền chở hàng ra bến xe',
  'Thanh toán tiền vận tải lô hàng', 'Trả bưu phí gửi đơn đi tỉnh',
  'Chi giao hàng tận nơi cho khách', 'Trả phí tài xế giao lô sản phẩm'],
 'salary': [
  'Trả lương nhân viên', 'Thanh toán tiền công phụ quán',
  'Chi lương người bán hàng', 'Ứng lương cho nhân viên',
  'Trả tiền công theo ca', 'Chi thưởng nhân viên cuối tháng',
  'Thanh toán lương thợ chính', 'Trả công nhân viên đóng gói',
  'Chi phụ cấp người làm thuê', 'Trả tiền tăng ca cho nhân viên',
  'Thanh toán lương phục vụ', 'Chi tiền công nhân viên thu ngân',
  'Trả lương người nấu bếp', 'Trả công người trông cửa hàng',
  'Chi tiền thưởng cho thợ', 'Thanh toán công nhật cho nhân viên',
  'Trả lương bạn phụ bán hàng', 'Chi tiền công nhân viên làm thêm',
  'Thanh toán lương tháng của thợ phụ', 'Trả thưởng người phục vụ quán',
  'Chi lương nhân viên pha chế', 'Thanh toán tiền công lao động thuê',
  'Trả phụ cấp ca tối cho nhân viên', 'Chi tiền lương thủ kho'],
 'other_expense': [
  'Mua kệ trưng bày cho cửa hàng', 'Trả phí sửa máy pha cà phê của tiệm',
  'Chi tiền quảng cáo trên mạng', 'Thanh toán phí phần mềm bán hàng',
  'Mua máy in hóa đơn', 'Trả phí vệ sinh cửa hàng',
  'Chi tiền bảo dưỡng tủ lạnh của quán', 'Mua bàn ghế cho tiệm',
  'Đóng thuế kinh doanh', 'Trả lãi vay ngân hàng',
  'Chi sửa bảng hiệu cửa hàng', 'Thanh toán phí ngân hàng',
  'Mua máy quét mã vạch', 'Trả tiền sửa mái che quán',
  'Chi mua dụng cụ vệ sinh', 'Thanh toán phí bảo hiểm kinh doanh',
  'Mua cân điện tử cho quầy', 'Chi sửa chữa thiết bị của quán',
  'Trả phí quảng bá cửa hàng', 'Chi tiền mua tủ trưng bày',
  'Thanh toán phí dịch vụ kế toán', 'Trả tiền sửa máy tính của tiệm',
  'Mua camera giám sát cửa hàng', 'Chi phí đăng ký kinh doanh'],
}
INCOME = {'sales', 'service', 'capital', 'other_income'}

# ── Augmentation helpers ───────────────────────────────────────────────

# Common OCR errors for Vietnamese text
OCR_NOISE_MAP = {
    'ă': ['a', 'ắ', 'ằ'], 'â': ['a', 'ầ', 'ấ'], 'đ': ['d', 'ð'],
    'ê': ['e', 'ế', 'ề'], 'ô': ['o', 'ổ', 'ố'], 'ơ': ['o', 'oi'],
    'ư': ['u', 'ừ'], 'ị': ['i'], 'ọ': ['o'], 'ụ': ['u'],
    'ả': ['a'], 'ẻ': ['e'], 'ỉ': ['i'], 'ỏ': ['o'], 'ủ': ['u'],
    'à': ['a'], 'è': ['e'], 'ì': ['i'], 'ò': ['o'], 'ù': ['u'],
    'á': ['a'], 'é': ['e'], 'í': ['i'], 'ó': ['o'], 'ú': ['u'],
    'ã': ['a'], 'õ': ['o'], 'ũ': ['u'], 'ẽ': ['e'], 'ĩ': ['i'],
    'ạ': ['a'], 'ặ': ['a'], 'ậ': ['a'], 'ắ': ['a'], 'ằ': ['a'],
}

# Common speech recognition errors — updated with real Whisper STT misrecognitions
SPEECH_NOISE_MAP = {
    'tiền': ['tiên', 'tiến'],
    'nghìn': ['ngàn', 'nghìng', 'nhin', 'nn'],
    'triệu': ['triều', 'trieu', 'chieu'],
    'trăm': ['chăm', 'cham', 'tram'],
    'bán': ['bàn', 'ban'],
    'mua': ['mùa', 'múa'],
    'thuê': ['thue', 'thuế'],
    'lương': ['luong', 'lướng'],
    'hàng': ['hang', 'hàn'],
    'nhập': ['nhap', 'nhặp'],
    'trả': ['tra', 'trà'],
    'phí': ['phi', 'phì'],
    'tiệm': ['tiêm', 'tiem'],
    'quán': ['quan', 'quàn'],
    'vốn': ['von', 'vôn'],
    'nghìn đồng': ['nhin dong', 'nhan dong', 'nđ'],
    'rưỡi': ['rưi', 'rượi'],
    'chính': ['chinh'],
    'khoản': ['khoan'],
    'chuyển khoản': ['chuyen khoan', 'chuyen'],
    'tiền mặt': ['tien mat', 'mat'],
}


def _strip_diacritics(text):
    """Remove Vietnamese diacritics but keep đ→d."""
    text = text.replace('đ', 'd').replace('Đ', 'D')
    return ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )


def _ocr_noise(text, rng, intensity=0.15):
    """Simulate OCR misreads: drop diacritics, swap chars."""
    chars = list(text.lower())
    for i, ch in enumerate(chars):
        if ch in OCR_NOISE_MAP and rng.random() < intensity:
            chars[i] = rng.choice(OCR_NOISE_MAP[ch])
    return ''.join(chars)


def _speech_noise(text, rng, intensity=0.3):
    """Simulate Whisper misrecognitions."""
    result = text
    for word, replacements in SPEECH_NOISE_MAP.items():
        if word in result.lower() and rng.random() < intensity:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            result = pattern.sub(rng.choice(replacements), result, count=1)
    return result


def _word_dropout(text, rng, rate=0.1):
    """Randomly drop words to simulate truncated input."""
    words = text.split()
    if len(words) <= 3:
        return text
    return ' '.join(w for w in words if rng.random() > rate)


def _shuffle_words(text, rng, max_swaps=2):
    """Slightly reorder words."""
    words = text.split()
    if len(words) <= 3:
        return text
    for _ in range(min(max_swaps, len(words) // 3)):
        i = rng.randint(0, len(words) - 2)
        words[i], words[i + 1] = words[i + 1], words[i]
    return ' '.join(words)


# STT-style templates simulating how Whisper transcribes spoken Vietnamese
# These reflect natural speech patterns and common STT output forms
STT_TEMPLATES = [
    # Whisper mishears tram/nghin
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//100000} cham {(a%100000)//1000} nhin' if a >= 100000 else f'{_strip_diacritics(s.lower())} {a//1000} nhin',
    # Slang: cu = 1M, xi = 100k
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000000} cu' if a >= 1000000 else f'{_strip_diacritics(s.lower())} {a//100000} xi',
    # Casual "ruoi" = half
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000000} trieu ruoi tien mat' if 1000000 <= a < 2000000 else f'{_strip_diacritics(s.lower())} {a//1000} nghin tien mat',
    # No-diacritics voice output
    lambda s, a: f'hom nay {_strip_diacritics(s.lower())} het {a//1000} nghin dong',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000} nghin tien mat',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a//1000} ngan chuyen khoan',
    lambda s, a: f'{_strip_diacritics(s.lower())} {a} dong tien mat',
    # Extremely casual voice note
    lambda s, a: f'{_strip_diacritics(s.lower())} het {a//1000}k roi',
    lambda s, a: f'ghi {_strip_diacritics(s.lower())} {a//1000}k nhe',
    lambda s, a: f'{_strip_diacritics(s.lower())} tieu {a//1000}k',
    # Mix diacritics + casual number
    lambda s, a: f'{s.lower()} hết {a//1000}k tiền mặt',
    lambda s, a: f'{s.lower()} tổng cộng {a//1000} nghìn',
    # Common spoken pattern: verb + item + amount
    lambda s, a: f'chi {a//1000}k cho {_strip_diacritics(s.lower())}',
    lambda s, a: f'thu {a//1000}k tu {_strip_diacritics(s.lower())}',
]

# Additional paraphrase templates for more diversity
EXTRA_TEMPLATES = [
    # Casual Vietnamese
    lambda s, a: f'{s.lower()}, tổng {a} đ',
    lambda s, a: f'ghi nhé: {s.lower()} - {a} đồng',
    lambda s, a: f'{s}. Số tiền: {a:,} VND'.replace(',', '.'),
    # Question-like
    lambda s, a: f'Ghi cho tôi khoản {s.lower()} {a} VND được không',
    # Receipt-like
    lambda s, a: f'Nội dung: {s}\nSố tiền: {a:,} VND\nNgày: hôm nay'.replace(',', '.'),
    # Short command
    lambda s, a: f'{s.lower()} {a//1000}k',
    lambda s, a: f'{s.lower()} - {a//1000}k',
    lambda s, a: f'{s.lower()} - {a} dong',
    lambda s, a: f'{s.lower()} - {a//1000} nghin',
    lambda s, a: f'{s.lower()} - {a//1000} ngàn',
    lambda s, a: f'{s.lower()} : {a//1000}k',
    # With date prefix
    lambda s, a: f'Sáng nay {s.lower()} hết {a:,} đồng'.replace(',', '.'),
    lambda s, a: f'Chiều nay {s.lower()}, chi {a:,} đ'.replace(',', '.'),
    # With payment method embedded
    lambda s, a: f'{s}, {a:,} đồng, thanh toán bằng tiền mặt'.replace(',', '.'),
    lambda s, a: f'{s}, {a:,} VND, chuyển khoản qua ngân hàng'.replace(',', '.'),
    # Informal
    lambda s, a: f'{s.lower()} tốn {a//1000} nghìn',
    lambda s, a: f'Tốn {a//1000000} triệu cho {s.lower()}' if a >= 1000000 else f'Tốn {a//1000}k cho {s.lower()}',
    # With context
    lambda s, a: f'Hôm nay đi {s.lower()}, hết {a:,} đồng, ghi vào sổ'.replace(',', '.'),
    lambda s, a: f'Xong rồi, {s.lower()} {a:,} đ'.replace(',', '.'),
]


def build():
    out = ROOT / 'datasets'
    out.mkdir(exist_ok=True)
    rows = []
    rng = random.Random(20261021)
    for category, seeds in SEEDS.items():
        assert len(seeds) == 24, category
        for i, seed in enumerate(seeds):
            split = 'train' if i < 16 else 'validation' if i < 20 else 'test'
            group = f'{category}-{i:02}'
            amount = rng.choice([85000, 150000, 350000, 650000, 1200000, 2500000])
            # ── Core variants (backward compatible) ──
            variants = [
                f'{seed} {amount:,} đồng'.replace(',', '.'),
                f'Hôm nay {seed.lower()}, số tiền {amount} VND, chuyển khoản.',
                f'Hôm qua {seed.lower()} hết {amount // 1000} nghìn, trả tiền mặt.',
                f'Ghi giúp tôi: {seed.lower()}, {amount // 1000}k.',
                f'{seed.upper()}. Tổng cộng: {amount} đồng.',
                f'{normalize(seed)} {amount} dong',
                f'{seed.lower()} - {amount // 1000}k',
                f'{seed.lower()} - {amount} dong',
            ]
            # ── Extended augmentation variants (only for train split) ──
            if split == 'train':
                # Extra paraphrase templates
                for template_fn in EXTRA_TEMPLATES:
                    variants.append(template_fn(seed, amount))
                # STT-style variants: simulate Whisper transcription output
                for template_fn in STT_TEMPLATES:
                    try:
                        variants.append(template_fn(seed, amount))
                    except Exception:
                        pass
                # OCR noise variants
                variants.append(_ocr_noise(f'{seed} {amount:,} đồng'.replace(',', '.'), rng, 0.15))
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), rng, 0.25))
                # Speech noise variants
                variants.append(_speech_noise(f'{seed.lower()} {amount // 1000} nghìn', rng, 0.3))
                variants.append(_speech_noise(f'hôm nay {seed.lower()} {amount} đồng', rng, 0.4))
                # Stripped diacritics (simulating no-accent Vietnamese / STT output)
                variants.append(f'{_strip_diacritics(seed)} {amount} dong')
                variants.append(f'{_strip_diacritics(seed.lower())} het {amount // 1000} nghin')
                variants.append(f'{_strip_diacritics(seed.lower())} {amount // 1000} ngan tien mat')
                variants.append(f'{_strip_diacritics(seed.lower())} {amount // 1000} nhin dong')
                # Word dropout
                variants.append(_word_dropout(f'Hôm nay {seed.lower()} hết {amount:,} đồng chuyển khoản'.replace(',', '.'), rng))
                # Word shuffle (mild)
                variants.append(_shuffle_words(f'{seed} hết {amount // 1000} nghìn tiền mặt', rng))
            elif split == 'validation':
                # Fewer augmentations for validation — still unseen patterns
                variants.append(f'ghi nhé: {seed.lower()} {amount:,} đồng'.replace(',', '.'))
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), rng, 0.15))
                variants.append(f'{_strip_diacritics(seed.lower())} {amount} dong')
                variants.append(f'Hôm qua {seed.lower()} tốn {amount // 1000}k')
            else:  # test
                # Test also gets a few more variants for better eval
                variants.append(f'{seed.lower()}, tổng {amount} đ')
                variants.append(_ocr_noise(f'{seed} {amount:,} VND'.replace(',', '.'), rng, 0.2))
                variants.append(_speech_noise(f'{seed.lower()} {amount // 1000} nghìn đồng', rng, 0.3))
                variants.append(f'{_strip_diacritics(seed)} {amount} dong')

            for j, text in enumerate(variants):
                rows.append({'id': f'{group}-{j}', 'text': text,
                             'kind': 'income' if category in INCOME else 'expense',
                             'category': category, 'group_id': group, 'split': split,
                             'origin': 'synthetic_authored_template_v2'})
    fields = list(rows[0])
    for split in ('train', 'validation', 'test'):
        with (out / f'{split}.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(row for row in rows if row['split'] == split)
    meta = {'origin': 'Synthetic educational data, authored seed families + deterministic variants + augmentation v2',
            'seed': 20261021, 'total': len(rows), 'categories': len(SEEDS),
            'split_counts': {s: sum(r['split'] == s for r in rows) for s in ('train', 'validation', 'test')},
            'group_policy': 'A semantic seed and all variants stay in exactly one split. Evaluation is synthetic, not real-world accuracy.',
            'augmentation': 'OCR noise, speech noise, diacritic stripping, word dropout, word shuffle, casual templates'}
    (out / 'metadata.json').write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(meta, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
