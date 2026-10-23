"""Money/date parsing by explicit rules; classification is done separately by ML.

This deliberately abstains on ambiguous amounts; it never adds receipt line
items to a total or invents a missing amount. Not a general accounting parser.
"""
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from .domain import fold
from .db import today

DIGITS={'khong':0,'mot':1,'hai':2,'ba':3,'bon':4,'tu':4,'nam':5,'lam':5,'sau':6,'bay':7,'tam':8,'chin':9}
# 'cham' added as phonetic alias for 'tram' (trăm) common in STT output
WORDS='(?:khong|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin|muoi|tram|cham|linh|le|chuc)'


def word_number(text):
    value=0;current=0
    for token in text.split():
        if token in DIGITS: current=DIGITS[token]
        elif token in ('tram','cham'): value+=(current or 1)*100;current=0
        elif token in ('muoi','chuc'): value+=(current or 1)*10;current=0
        elif token not in ('linh','le'): raise ValueError('Unknown number')
    return value+current


def decimal_number(text):
    if re.fullmatch(r'\d{1,3}(?:[.,]\d{3})+',text):
        return Decimal(text.replace('.','').replace(',',''))
    return Decimal(text.replace(',','.'))


def normalize_stt_text(s):
    """Normalize common Speech-To-Text (Whisper) misrecognitions for Vietnamese financial text.

    Called on the *folded* (no-diacritics, lowercase) string before money parsing.
    Only used for voice (stt=True) transcription results, not manual text or OCR.

    Common STT errors fixed:
      cham  -> tram  (chăm/cham misheard as trăm)
      nhin  -> nghin (nhìn misheard as nghìn)
      ruoi after tram/cham without unit -> ...nam muoi nghin (rưỡi = half)
      Slang: cu/chai = 1M, lit/xi/lop = 100k, canh = 1k
    """
    # ── 1. "cham" (STT alias of "tram"/trăm = 100) ──
    s = re.sub(r'\b(khong|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin|\d+)\s+cham\b', r'\1 tram', s)

    # ── 2. "nhin" (STT alias of "nghin"/nghìn = 1000) ──
    s = re.sub(r'\b(khong|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin|muoi|tram|\d+)\s+nhin\b', r'\1 nghin', s)
    s = re.sub(r'(\d+)\s+nhin\b', r'\1 nghin', s)

    # ── 3. "tram ruoi" without an explicit nghin/k → add "nam muoi nghin" (50k suffix) ──
    # "sau tram ruoi" → "sau tram nam muoi nghin" (650k)
    s = re.sub(
        r'\b(\d+|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin)\s+tram\s+ruoi\b(?!\s*(?:nghin|ngan|k\b|dong|vnd|trieu|tr))',
        r'\1 tram nam muoi nghin',
        s
    )

    # ── 4. Slang currency units ──
    # cu / chai = 1,000,000
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:cu|chai)\s+(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\b', r'\1 trieu \2 tram nghin', s)
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:cu|chai)\s+ruoi\b', r'\1 trieu nam tram nghin', s)
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:cu|chai)\b', r'\1 trieu', s)
    # lit / xi / lop = 100,000
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:lit|xi|lop)\s+ruoi\b', r'\1 tram nam muoi nghin', s)
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+(?:lit|xi|lop)\b', r'\1 tram nghin', s)
    s = re.sub(r'\b(?:lit|xi|lop)\s+ruoi\b', 'mot tram nam muoi nghin', s)
    s = re.sub(r'\b(?:lit|xi|lop)\b', 'mot tram nghin', s)
    # canh = 1,000
    s = re.sub(r'\b(\d+|mot|hai|ba|bon|tu|nam|sau|bay|tam|chin)\s+canh\b', r'\1 nghin', s)

    # ── 5. "tram" standalone without nghin/dong in marketplace context (e.g. nam tram = 500k) ──
    s = re.sub(rf'\b(\d+|mot|hai|ba|bon|tu|nam|lam|sau|bay|tam|chin)\s+tram\b(?!\s*(?:nghin|ngan|k\b|dong|vnd|trieu|tr|ruoi|\d|{WORDS}))', r'\1 tram nghin', s)

    return s


def money_candidates(text, bare=False):
    # Compact Vietnamese notation: 1tr5 means 1.5 million; 2tr200 means 2.2 million.
    text=re.sub(r'\b(\d+)\s*tr(\d{1,3})\b',lambda m:f'{int(m[1])*1000000+int(m[2].ljust(3,"0"))*1000} dong',text)
    number=rf'(?:\d+(?:[.,]\d+)*|{WORDS}(?:\s+{WORDS})*)'
    pattern=rf'(?<![\w/-])(?P<num>{number})\s*(?P<unit>trieu|nghin|ngan|vnd|dong|tr|k|d)\b(?:\s*(?P<half>ruoi))?'
    matches=list(re.finditer(pattern,text))
    values=[];last_end=-1
    for m in matches:
        num=m['num'].strip();unit=m['unit']
        try:
            factor=1000000 if unit in ('trieu','tr') else 1000 if unit in ('nghin','ngan','k') else 1
            n=decimal_number(num) if num[0].isdigit() else Decimal(word_number(num))
            val=n*factor+(factor//2 if m['half'] else 0)
            if val!=val.to_integral_value(): continue
            val=int(val)
        except (ValueError,InvalidOperation): continue
        # Combine adjacent descending denominations, e.g. hai trieu ba tram nghin.
        if values and not text[last_end:m.start()].strip() and values[-1][1]>factor:
            values[-1]=(values[-1][0]+val,factor)
        else: values.append((val,factor))
        last_end=m.end()
    if values: return [v[0] for v in values]
    if bare:
        found=re.findall(r'(?<![\w/.-])(\d{1,3}(?:[.,]\d{3})+|\d{4,12})(?![\w/.-])',text)
        return [int(decimal_number(v)) for v in found if decimal_number(v)==decimal_number(v).to_integral_value()]
    return []



def split_transaction_clauses(text):
    """Split compound speech or multiline text into individual transaction clauses.

    Splits by:
    1. Line breaks (\\n)
    2. Conjunctions and punctuation (dấu phẩy, chấm phẩy, 'với', 'và', 'rồi', 'xong'...)
    3. Action cue transitions when an action keyword (mua, bán, trả, đóng, ship...)
       immediately follows a previous amount/currency word.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return []

    delim = re.compile(
        r'(?<!\d)[,;]+(?!\d)|\s+(?:với|voi|và|va|rồi|roi|xong|đồng thời|dong thoi|tiếp theo|tiep theo)\s+',
        re.IGNORECASE
    )
    cue_pattern = re.compile(
        r'(\b\d+[\d.,]*(?:k|dong|đ|d|vnd|nghin|ngan|trieu|tr|tram|cu|chai|lit|xi|lop)?)\s+'
        r'(?=(?:mua|bán|ban|nhập|nhap|trả|tra|đóng|dong|chi|thu|lấy|lay|khách|khach|ship|tiền\s+)\b)',
        re.IGNORECASE
    )

    segments = []
    for line in lines:
        line_split = cue_pattern.sub(r'\1\n', line)
        for sub_line in line_split.splitlines():
            parts = delim.split(sub_line)
            for part in parts:
                part = part.strip()
                if part:
                    segments.append(part)
    return segments


def parse_multi_items(text, stt=True):
    """Parse multiline or compound transaction sentences into individual items.

    Returns [] immediately when the text looks like a receipt with a running
    total line (tong cong / thanh toan / so tien ...) so that parse_fields
    can pick up the TONG CONG total instead of treating each line-item
    individually.
    """
    folded_all = fold(text)
    if re.search(
        r'\b(tong\s*(cong|tien|gia\s*tri|so|hang)|thanh\s*toan|tong\s*cong'
        r'|so\s*tien\s*thanh\s*toan|khach\s*phai\s*tra|can\s*thanh\s*toan)\b',
        folded_all
    ):
        return []

    clauses = split_transaction_clauses(text)
    if len(clauses) < 2:
        return []

    items = []
    for line in clauses:
        folded = fold(line)
        if re.search(r'\b(kiem tra|xac nhan|xem lai|giao dich|so thu chi|hoa don|phieu thu|phieu chi|cam on|hen gap lai|tong cong|thanh toan)\b', folded):
            continue
        line_clean = re.sub(r'(\w)\s*[-\u2013\u2014:]\s*(\d)', r'\1 : \2', line)
        folded_clean = fold(line_clean)
        folded_norm = normalize_stt_text(folded_clean)
        cands = money_candidates(folded_norm, bare=True)
        if not cands:
            m = re.search(r'(\d+[\d.,]*)\s*(?:k|dong|\u0111|d|vnd|nghin|ngan|trieu|tr)\b', line, re.I)
            if m:
                cands = money_candidates(fold(m.group(0)), bare=True)
        # Small bare number after item: e.g. "rau cải 20" -> 20.000
        if not cands:
            m_bare = re.search(r'(?:^|[^\d.,])(\d{1,3})\s*$', line.strip())
            if m_bare:
                val = int(m_bare.group(1))
                if 1 <= val <= 500:
                    cands = [val * 1000]

        if cands and 0 < cands[0] <= 1000000000000:
            amt = cands[0]
            desc = re.sub(
                r'[-\u2013\u2014:]?\s*(?:hết|het|được|duoc|mất|mat|khoảng|khoang|tam|tầm|là|la)?\s*\d+[\d.,]*\s*(?:k|dong|\u0111|d|vnd|nghin|ngan|trieu|tr|tram|cu|chai|lit)?\s*$',
                '', line, flags=re.I
            ).strip()
            desc = re.sub(r'^[0-9]+[.)\-]\s*|^[-*\u2022]\s*', '', desc).strip()
            if not desc:
                desc = line
            desc = desc[:1].upper() + desc[1:]
            items.append({
                'raw_line': line,
                'description': desc[:300],
                'amount': amt
            })
    return items if len(items) >= 2 else []


def parse_fields(text, stt=False):
    """Parse amount, date and payment method from a transaction text string.

    Args:
        text: The transaction text (raw or folded).
        stt:  Set True when text comes from speech-to-text transcription.
              Enables extra normalization for STT misrecognition errors.
    """
    s=fold(text);warnings=[]

    # === STT normalization: fix common Whisper misrecognitions before parsing ===
    if stt:
        s = normalize_stt_text(s)

    # === Date extraction BEFORE any substitution so '2026-10-15' is never mangled ===
    day=today()
    explicit=re.search(r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b',s)
    other=re.search(r'\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b',s)
    try:
        if explicit: day=date(*map(int,explicit.groups()))
        elif other: day=date(int(other[3] or day.year),int(other[2]),int(other[1]))
        elif 'hom kia' in s: day-=timedelta(days=2)
        elif 'hom qua' in s: day-=timedelta(days=1)
        elif 'ngay mai' in s: day+=timedelta(days=1)
        elif not re.search(r'hom nay|bay gio',s): warnings.append('Thiếu ngày giao dịch; đang gợi ý ngày hôm nay.')
    except ValueError: warnings.append('Ngày đọc được không hợp lệ; hãy chọn lại ngày giao dịch.')
    if day>today(): warnings.append('Ngày đang ở tương lai; hãy sửa ngày trước khi lưu.')

    # === Check for true negative amounts on ORIGINAL s (before hyphen substitution) ===
    # A true negative sign is directly attached to digits with no space between hyphen and number,
    # or uses 'am'/'tru' keywords.  A separator like 'thit bo - 200k' has spaces on both sides.
    has_negative = bool(re.search(r'(?:^|[(,;\s])-\d|\b(am|tru)\s+\d', s))

    # === Hyphen-as-delimiter substitution ===
    # Requires a non-digit letter ([^\W\d_]) before the hyphen AND at least one space
    # on each side, so ISO dates ('2026-10-15') and directly-attached negatives ('-200000')
    # are left untouched.
    s=re.sub(r'([^\W\d_])\s+[-\u2013\u2014]\s+(\d)', r'\1 : \2', s)

    if re.search(r'\b(usd|eur|cny|yen|dollar|do la|nhan dan te)\b|[$\u20ac\u00a5]',s):
        amount=None;warnings.append('Phát hiện ngoại tệ. Bản demo chỉ ghi VND; hãy tự kiểm tra và nhập số tiền.')
    elif has_negative:
        amount=None;warnings.append('Có số tiền âm. Hãy chọn Thu/Chi và nhập số tiền dương.')
    else:
        totals=[]
        for line in s.splitlines():
            total=re.search(r'(?:tong\s+(?:cong|tien|thanh\s+toan|phai\s+tra)|thanh\s+tien|cong\s+tien(?:\s+hang)?|thanh\s+toan|so\s+tien(?:\s+thanh\s+toan)?|khach\s+phai\s+tra|can\s+thanh\s+toan|phai\s+thanh\s+toan)\s*[:=]?\s*(.*)',line)
            if total:
                cands = money_candidates(total[1],bare=True)
                if not cands:
                    cands = money_candidates(line,bare=True)
                totals.extend(cands)
        if totals:
            amount = totals[-1] if 0 < totals[-1] <= 1000000000000 else None
            values = totals
        else:
            values=money_candidates(s)
            if not values:
                # Unmarked values only after an explicit money cue, never phone/order numbers.
                cue=re.search(r'(?:so tien|het|gia|thanh tien)\s*[:=]?\s*(\d[\d.,]*)\b',s)
                values=money_candidates(cue[1],bare=True) if cue else []
            amount=values[0] if len(values)==1 and 0<values[0]<=1000000000000 else None
            if len(values)>1: warnings.append('Có nhiều số tiền. Chưa tự chọn tổng; hãy kiểm tra và nhập một khoản thu/chi.')
        if amount is None: warnings.append('Chưa xác định chắc chắn số tiền VND. Vui lòng bổ sung trước khi lưu.')
    payment='transfer' if re.search(r'chuyen khoan|quet qr|\bck\b',s) else 'cash'
    if not re.search(r'chuyen khoan|quet qr|\bck\b|tien mat',s):
        warnings.append('Chưa rõ cách thanh toán; đang gợi ý tiền mặt.')
    return {'amount':amount,'date':day.isoformat(),'payment':payment,'warnings':warnings}
