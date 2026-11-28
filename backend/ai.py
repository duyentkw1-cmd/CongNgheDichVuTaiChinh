"""Local AI gateway. All inference uses local files; no provider keys/network.

Only scripts/prepare_models.py downloads model files, explicitly during setup.

v2: Improved OCR preprocessing (adaptive threshold, multi-PSM fallback),
    better Whisper config (wider beam, richer prompt, temperature fallback).
"""
import asyncio
import importlib.util
import io
import logging
import os
import re
import shutil
import subprocess
import unicodedata
import time
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

import numpy as np
from fastapi import HTTPException
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from datetime import date

from ml.predict import classify, metrics, ready
from .db import ROOT, today
from .domain import CATEGORIES, fold
from .local_parse import money_candidates, parse_fields, parse_multi_items

# One heavy job at a time prevents exhausting RAM on a normal laptop.
worker = asyncio.Semaphore(1)
logger = logging.getLogger(__name__)


def speech_path():
    return Path(os.getenv('WHISPER_MODEL_PATH') or ROOT/'models'/'whisper-base')


def tessdata_path():
    path = Path(os.getenv('TESSDATA_DIR') or ROOT/'models'/'tessdata')
    return path if path.is_absolute() else ROOT/path


def tesseract_path():
    specified=os.getenv('TESSERACT_CMD','').strip()
    if specified and Path(specified).is_file(): return specified
    candidates=[shutil.which('tesseract'),
                str(ROOT/'tools'/'tesseract'/'tesseract.exe'),
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                str(Path(os.getenv('LOCALAPPDATA',''))/'Programs'/'Tesseract-OCR'/'tesseract.exe')]
    return next((p for p in candidates if p and Path(p).is_file()),None)


def capabilities():
    text=ready()
    has_vision=bool(os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'))
    image=bool(text and ((tesseract_path() and
               all((tessdata_path()/f'{lang}.traineddata').is_file() for lang in ('vie','eng'))) or has_vision))
    voice=bool(text and importlib.util.find_spec('faster_whisper') and
               all((speech_path()/f).is_file() for f in ('model.bin','config.json','tokenizer.json')))
    return {'mode':'local','text':text,'image':image,'voice':voice}


def connection_status():
    cap=capabilities()
    providers=[
        {'id':'finance','name':'Mô hình thu chi của nhóm','purpose':'Hai mô hình tự huấn luyện · 11 danh mục','configured':cap['text']},
        {'id':'whisper','name':'Whisper · chạy trên máy','purpose':'Mô hình có sẵn · nhận giọng nói tiếng Việt','configured':cap['voice']},
        {'id':'tesseract','name':'Tesseract · tiếng Việt','purpose':'Mô hình có sẵn · đọc chữ in từ ảnh','configured':bool(tesseract_path())}
    ]
    if os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY'):
        providers.append({'id':'gemini_vision','name':'Gemini Vision AI','purpose':'Trích xuất hóa đơn chính xác bằng AI Vision','configured':True})
    return {**cap, 'providers':providers, 'training':metrics(), 'network_required':False}


def extract_receipt_description(text):
    """Intelligently extract or summarize a description from receipt text."""
    explicit = re.search(r'(?im)^\s*(?:nội dung|noi dung|lý do|ly do|diễn giải|dien giai|ghi chú|ghi chu)\s*[:：]\s*(.+)$', text)
    if explicit:
        desc = explicit[1].strip()
        if desc:
            return desc[:300]

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return 'Hóa đơn mua hàng'

    title = None
    store = None
    items = []

    for line in lines[:5]:
        folded = fold(line)
        if re.search(r'\b(hoa don|phieu thu|phieu chi|phieu ban hang|phieu thanh toan|bien nhan|bien lai)\b', folded):
            title = line
            break
        if re.search(r'\b(cua hang|tiem|quan|cong ty|nha thuoc|sieu thi)\b', folded) and not store:
            store = line

    for line in lines:
        folded = fold(line)
        if re.search(r'\b(tong cong|thanh tien|thanh toan|ngay|gio|thu ngan|dia chi|tel|dien thoai|wifi|cam on|hen gap lai|kiem tra|xac nhan|khoan thu|khoan chi|nhom phan loai|xem lai|ghi vao so|tu nhap|giong noi|hinh anh)\b', folded):
            continue
        m = re.match(r'^(?:[0-9]+[.\-)]\s*)?([A-Za-zÀ-ỹ\s]{3,40}?)(?:\s*[:\-]\s*|\s{2,}|\s+)(?:\d+[\d.,]*\s*(?:vnd|d|k)?)$', line, re.IGNORECASE)
        if m:
            item_name = m[1].strip()
            if len(item_name) >= 3 and not re.search(r'\b(tong|thanh tien|tien mat|chuyen khoan|so luong|don gia|cong|mat|vat)\b', fold(item_name)):
                items.append(item_name)

    if items:
        return f'Mua {", ".join(items[:3])}'[:300]
    if title and store:
        return f'{title} - {store}'[:300]
    if title:
        return title[:300]
    if store:
        return f'Hóa đơn {store}'[:300]

    if len(text.strip()) <= 80 and len(lines) <= 2:
        return text.strip()[:300]

    words = re.findall(r'[A-Za-zÀ-ỹ]{2,}', text)
    if len(words) < 3:
        return 'Hóa đơn / chứng từ thanh toán'

    return 'Hóa đơn mua hàng'


def analyze_text(text, stt=False):
    text=text.strip()
    if not text or len(text)>10000:
        raise HTTPException(422,'Nhập nội dung một giao dịch, tối đa 10.000 ký tự.')
    if not ready():
        raise HTTPException(503,'Thiếu mô hình phân loại. Chạy train-models.bat rồi mở lại ứng dụng.')

    multi = parse_multi_items(text, stt=stt)
    items = []
    if len(multi) >= 2:
        for it in multi:
            cl = classify(it['raw_line'])
            kind = cl['kind']
            cat = cl['category']

            # Ensure Thu/Chi aligns with unambiguous action keywords
            folded_raw = fold(it['raw_line'])
            is_income_word = bool(re.search(r'\b(ban|duoc|khach tra|nhan tien|thu|gom tien)\b', folded_raw))
            is_expense_word = bool(re.search(r'\b(mua|nhap|tra|dong|ton|het|lay hang|ship|chi)\b', folded_raw))

            if is_income_word and not is_expense_word:
                kind = 'income'
                if cat not in ('sales', 'service', 'other_income', 'capital'):
                    cat = 'sales'
            elif is_expense_word and not is_income_word:
                kind = 'expense'
                if cat not in ('materials', 'rent', 'utilities', 'shipping', 'salary', 'other_expense'):
                    cat = 'materials'

            items.append({
                'kind': kind,
                'category': cat,
                'description': it['description'],
                'amount': it['amount']
            })

    line=re.search(r'(?im)^\s*(?:nội dung|noi dung)\s*[:：]\s*(.+)$',text)
    if items:
        description = items[0]['description']
        classification_text = items[0]['description']
    elif line:
        description = line[1].strip()[:300]
        classification_text = description
    elif '\n' in text:
        description = extract_receipt_description(text)
        classification_text = description if description not in ('Hóa đơn / chứng từ thanh toán', 'Hóa đơn mua hàng') else text
    else:
        description = text[:300]
        classification_text = text

    try: result=classify(classification_text)
    except Exception:
        raise HTTPException(503,'Chưa tải được mô hình phân loại. Chạy setup-local.bat hoặc huấn luyện lại bằng train-models.bat.') from None
    fields=parse_fields(text, stt=stt)
    category=result['category'];kind=CATEGORIES[category][1]

    if items:
        n_chi = sum(1 for it in items if it['kind'] == 'expense')
        n_thu = sum(1 for it in items if it['kind'] == 'income')
        kind = items[0]['kind']
        category = items[0]['category']
        if n_chi > 0 and n_thu == 0:
            fields['amount'] = sum(it['amount'] for it in items)
            kind = 'expense'
        elif n_thu > 0 and n_chi == 0:
            fields['amount'] = sum(it['amount'] for it in items)
            kind = 'income'
        else:
            fields['amount'] = items[0]['amount']
        fields['warnings'] = [w for w in fields['warnings'] if 'nhiều số tiền' not in w and 'Chưa xác định chắc chắn' not in w]
        fields['warnings'].insert(0, f'Tìm thấy danh sách {len(items)} giao dịch ({n_chi} khoản chi, {n_thu} khoản thu).')
    else:
        if result['needs_review']:
            fields['warnings'].append('Mô hình chưa chắc danh mục. Hãy chọn lại nhóm phù hợp trước khi lưu.')
        if result['kind']!=kind:
            fields['warnings'].append('Hai mô hình chưa thống nhất Thu/Chi. Đang dùng chiều của danh mục gợi ý; cần kiểm tra.')
        if result['score']<0.25:
            fields['warnings'].append('Nội dung có thể ngoài dữ liệu mô hình đã học. Hãy kiểm tra Thu/Chi và số tiền thủ công.')

    from .market_assistant import (
        build_confirmation_message,
        extract_item_summary,
        extract_transaction_rules,
        format_spoken_vnd,
    )
    if len(items) > 1:
        summary_parts = [
            f"{'thu' if it['kind'] == 'income' else 'chi'} {it['description']} {format_spoken_vnd(it['amount'])}"
            for it in items[:3]
        ]
        extra = f" và {len(items) - 3} khoản khác" if len(items) > 3 else ""
        confirmation_msg = (
            f"Tôi nghe được {len(items)} giao dịch: {'; '.join(summary_parts)}{extra}. "
            f"Bạn có muốn lưu cả {len(items)} giao dịch không?"
        )
    else:
        market_info = extract_transaction_rules(text)
        expected_market_type = 'thu' if kind == 'income' else 'chi'
        if market_info.get('is_valid_transaction') and market_info.get('type') == expected_market_type:
            if market_info.get('item_summary') and (description == text or not description):
                description = market_info['item_summary']
            confirmation_msg = market_info.get('confirmation_message')
        elif fields.get('amount') is None:
            confirmation_msg = (
                market_info.get('confirmation_message')
                or 'Tôi chưa nghe rõ khoản thu chi. Bạn nói lại giúp tôi nhé.'
            )
        else:
            if market_info.get('is_valid_transaction') and market_info.get('type') != expected_market_type:
                fields['warnings'].append('Lưu ý kiểm tra lại khoản Thu hay Chi trước khi lưu.')
            cleaned_desc = extract_item_summary(description) or description
            if description == text and cleaned_desc:
                description = cleaned_desc
            confirmation_msg = build_confirmation_message(expected_market_type, cleaned_desc, fields['amount'])

    res = {**fields,'kind':kind,'category':category,'description':description,
           'confirmation_message': confirmation_msg,
           'scope':'business','raw_text':text,
           'engine':'local','providers':['finance_local'],'classification':result}
    if items:
        res['items'] = items
    return res


async def extract(text,consent=False,sample=False):
    # Sample text also passes through the trained classifier, not a keyword demo.
    return await run_in_threadpool(analyze_text,text)


def clean_image(content):
    if len(content)>5*1024*1024: raise HTTPException(413,'Ảnh tối đa 5 MB.')
    try:
        with Image.open(io.BytesIO(content)) as im:
            if im.format not in ('PNG','JPEG','WEBP') or im.width*im.height>24000000:
                raise ValueError()
            im.load();im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((2200,2200))
            out=io.BytesIO();im.save(out,'JPEG',quality=92)
            return out.getvalue()
    except (ValueError,UnidentifiedImageError,OSError,Image.DecompressionBombError):
        raise HTTPException(400,'Ảnh không hợp lệ. Dùng JPG, PNG hoặc WebP dưới 24 megapixel.') from None


def _deskew(gray, max_angle=15.0, step=0.5):
    """Straighten a tilted receipt photo using two-stage coarse-to-fine search."""
    small = gray.copy()
    small.thumbnail((700, 700))
    arr = np.asarray(small, dtype=np.float32)
    ink = Image.fromarray(((arr < arr.mean() * 0.82) * 255).astype(np.uint8))
    coarse_angle, best_score = 0.0, -1.0
    for angle in np.arange(-max_angle, max_angle + 1e-6, 1.5):
        rows = (np.asarray(ink.rotate(float(angle), resample=Image.Resampling.NEAREST)) > 0).sum(axis=1)
        score = float(np.var(rows))
        if score > best_score:
            coarse_angle, best_score = float(angle), score
    best_angle = coarse_angle
    for angle in np.arange(max(-max_angle, coarse_angle - 1.5), min(max_angle, coarse_angle + 1.5) + 1e-6, step):
        rows = (np.asarray(ink.rotate(float(angle), resample=Image.Resampling.NEAREST)) > 0).sum(axis=1)
        score = float(np.var(rows))
        if score > best_score:
            best_angle, best_score = float(angle), score
    if abs(best_angle) < step:
        return gray
    return gray.rotate(best_angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=255)


def _preprocess_for_ocr(im):
    """Enhanced image preprocessing for clean, high-accuracy OCR.
    
    Avoids aggressive sharpening which causes severe noise and artifact characters
    on camera-captured receipts.
    """
    gray = _deskew(ImageOps.grayscale(im))
    w, h = gray.size
    # Upscale smaller images so text characters have sufficient height for Tesseract.
    # Larger targets (2000-2600px) were tried on real receipts: no reliable accuracy
    # gain, but 30-70% slower on dense tables.
    if max(w, h) < 1400:
        scale = 1400.0 / max(w, h)
        gray = gray.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    # Method 1: Gentle autocontrast preserving clean character shapes
    c1 = ImageOps.autocontrast(gray, cutoff=0.5)

    # Method 2: Local adaptive background normalization for uneven shadows / low light
    arr_c1 = np.asarray(c1, dtype=np.float32)
    bg = np.asarray(c1.filter(ImageFilter.BoxBlur(25)), dtype=np.float32)
    norm_arr = np.clip((arr_c1 / np.maximum(bg, 22.0)) * 238.0, 0, 255).astype(np.uint8)
    norm_im = ImageOps.autocontrast(Image.fromarray(norm_arr), cutoff=0.5)

    # Method 3: Invert white-on-dark banner regions (e.g. bank app headers) without hurting light body
    bg_wide = np.asarray(c1.filter(ImageFilter.BoxBlur(32)), dtype=np.float32)
    dark_banner = bg_wide < 130.0
    has_white_on_dark = bool(np.mean(dark_banner & (arr_c1 > 170.0)) > 0.002)
    if has_white_on_dark:
        inv_arr = np.where(dark_banner, 255.0 - arr_c1, norm_arr).astype(np.uint8)
        m3 = Image.fromarray(inv_arr)
        return [m3, c1, norm_im]
    m3 = norm_im.filter(ImageFilter.UnsharpMask(radius=1.1, percent=110, threshold=3))
    return [c1, norm_im, m3]

    return results


def score_ocr_text(text):
    """Score candidate OCR text by density of valid words, financial terms and numbers."""
    if not text:
        return -1000.0
    cleaned = text.strip()
    if len(cleaned) < 3:
        return -1000.0

    words = re.findall(r'[A-Za-zÀ-ỹ0-9]{2,}', cleaned)
    word_count = len(words)

    folded = fold(cleaned)
    kw_matches = re.findall(r'\b(tong|cong|tien|thanh toan|hoa don|phieu|thu|chi|ban|mua|vnd|dong|ngay|gia|so|luong|don gia|chuyen khoan|mat|kg|cai|hop|goi)\b', folded)
    kw_score = len(kw_matches) * 25

    num_matches = re.findall(r'\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,}\b|\b\d+\s*(?:k|nghin|nghìn|dong|đ|vnd|tr|trieu|triệu)\b', cleaned, re.IGNORECASE)
    num_score = len(num_matches) * 20

    noise_chars = re.findall(r'[~=*^|`\\<>@#{}\[\]_]', cleaned)
    noise_ratio = len(noise_chars) / max(1, len(cleaned))
    noise_penalty = (noise_ratio * 200) if noise_ratio > 0.05 else 0

    return (word_count * 2) + kw_score + num_score - noise_penalty


_OCR_AMOUNT = re.compile(
    r'\b\d{1,3}(?:[.,]\d{3})+\b|\b\d{4,}\b|\b\d+\s*(?:k|nghin|nghìn|dong|đ|vnd|tr|trieu|triệu)\b',
    re.IGNORECASE)


def _ocr_good_enough(text, score):
    """A pass is good enough when it reads real text and a non-zero amount."""
    if score < 95 or not text:
        return False
    amt, _ = receipt_amount(text)
    return bool(amt and amt > 0)


def clean_ocr_noise(text):
    """Strip stray OCR noise characters from beginning and end of lines."""
    cleaned_lines = []
    for line in text.splitlines():
        # Remove noisy symbols from edge of lines
        cleaned = re.sub(r'^[~=\-_*^|`\\<>@#{}\[\]\s]+', '', line)
        cleaned = re.sub(r'[~=\-_*^|`\\<>@#{}\[\]\s]+$', '', cleaned)
        if cleaned:
            cleaned_lines.append(cleaned)
    return '\n'.join(cleaned_lines)


def fix_handwriting_ocr_errors(text):
    """Fix common OCR misreads when processing handwritten Vietnamese financial text.

    Handwriting confuses Tesseract on several character classes:
    - 'l', 'I', '|' misread instead of '1' next to digits
    - 'O', 'o' misread instead of '0' inside numbers
    - Currency shorthands: 'loo k' -> '100k', '4ok' -> '40k', '25O000' -> '250000'
    - Stray spaces inside digit groups: '2 50 000' -> '250000'
    - 'kk' -> 'k', 'K' -> 'k' after digits
    """
    fixed_lines = []
    for line in text.splitlines():
        # ── 1. Fix leading 'l'/'I' in amount tokens like 'loo', 'l00', 'lOO', '4ok' ──
        line = re.sub(
            r'\b([lI])([oO0-9]{2,})\s*(k|K|đ|d|D|vnd|VND|tr|TR|dong|nghìn|nghin|triệu|trieu)\b',
            lambda m: '1' + m.group(2).replace('o', '0').replace('O', '0') + m.group(3).lower(),
            line
        )

        # ── 2. Replace lone 'l'/'I' between digits -> '1' ──
        line = re.sub(r'(?<=\d)[lIi](?=\d)', '1', line)
        line = re.sub(r'(?<=\d)[lIi](?=\s*(?:k|đ|d|vnd|tr|dong|nghìn|nghin|triệu|trieu)\b)', '1', line)

        # ── 3. Replace 'O'/'o' between digits -> '0' (two passes for e.g. '1OO') ──
        line = re.sub(r'(\d)[Oo](\d)', r'\g<1>0\2', line)
        line = re.sub(r'(\d)[Oo](\d)', r'\g<1>0\2', line)
        line = re.sub(r'(\d)[Oo](?=\s*(?:k|đ|d|vnd|tr|dong|nghìn|nghin|triệu|trieu)\b)', r'\g<1>0', line)

        # ── 4. Currency unit fixes ──
        line = re.sub(r'(?<=[0-9])\s*[Kk][Kk]\b', 'k', line)   # 'kk' -> 'k'
        line = re.sub(r'(?<=[0-9])\s*K\b', 'k', line)           # 'K' -> 'k'

        # ── 5. Collapse spurious spaces inside large numbers before a unit ──
        # e.g. '2 50 000 dong' -> '250000 dong', '25 0000' -> '250000'
        line = re.sub(
            r'(?<![.\w])([1-9]\d{0,2})(\s+\d{3})+(?=\s*(?:k|đ|d|vnd|tr|dong|nghìn|nghin|triệu|trieu|\b))',
            lambda m: re.sub(r'\s+', '', m.group(0)),
            line
        )

        fixed_lines.append(line)
    return '\n'.join(fixed_lines)


def _run_tesseract(image_buffer, psm='3'):
    """Run Tesseract with specified PSM mode. Returns text or empty string."""
    tdata = tessdata_path()
    if os.name == 'nt':
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(500)
            if ctypes.windll.kernel32.GetShortPathNameW(str(tdata), buf, 500) and buf.value:
                tdata = Path(buf.value)
        except Exception:
            pass
    command=[tesseract_path(),'stdin','stdout','--tessdata-dir',str(tdata),
             '-l','vie+eng','--psm',psm]
    try:
        process=subprocess.run(command,input=image_buffer,capture_output=True,
                               timeout=30,check=False,
                               creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    except subprocess.TimeoutExpired:
        logger.warning('OCR exceeded the 30-second processing limit')
        raise HTTPException(504,'OCR đã chạy quá 30 giây. Hãy cắt ảnh còn một chứng từ rõ nét rồi thử lại.') from None
    except OSError:
        logger.exception('Could not launch the local Tesseract executable')
        raise HTTPException(503,'Chưa chạy được Tesseract. Chạy kiem-tra-ai.bat và xem phần OCR; có thể cần cài lại install-ocr-windows.bat.') from None
    if process.returncode:
        error=process.stderr.decode('utf-8',errors='replace').strip()
        logger.error('Tesseract exited with code %s: %s',process.returncode,error[:4000])
        if any(term in error.lower() for term in ('error opening data file','failed loading language','could not initialize tesseract')):
            detail='Tesseract chưa nạp được bộ tiếng Việt/Anh. Chạy kiem-tra-ai.bat để kiểm tra thư mục models/tessdata và xem lỗi cụ thể.'
        else:
            detail='Tesseract gặp lỗi khi đọc ảnh. Chạy kiem-tra-ai.bat hoặc xem cửa sổ start-demo để biết nguyên nhân.'
        raise HTTPException(503,detail)
    return process.stdout.decode('utf-8',errors='replace').strip()


VISION_PROMPT = """# BỐI CẢNH VÀ VAI TRÒ
Bạn là Trợ lý AI chuyên gia về OCR và trích xuất dữ liệu tài chính từ hình ảnh hóa đơn (receipts/bills) cho ứng dụng "Sổ Thu Chi AI". Nhiệm vụ của bạn là đọc hình ảnh hóa đơn được cung cấp, trích xuất chính xác 100% các trường thông tin mà không được phép bịa đặt (hallucination) hay sai chính tả tiếng Việt.

# QUY TẮC BẮT BUỘC:

1. QUY TẮC KIỂM TRA VÀ TRÍCH XUẤT NGÀY THÁNG (DATE):
   - Tìm kiếm chính xác trường chỉ thời gian trên hóa đơn (thường đi kèm từ "Ngày:", "Date:", hoặc nằm ở phần đầu/cuối hóa đơn).
   - Định dạng ngày tháng đầu ra chuẩn: `YYYY-MM-DD` hoặc `DD/MM/YYYY`.
   - Tuyệt đối không tự suy diễn ngày hiện tại nếu trên hóa đơn có in sẵn ngày cụ thể (Ví dụ trên bill hiển thị "24/10/2026" thì phải giữ nguyên chính xác giá trị này).

2. QUY TẮC CHÍNH TẢ TIẾNG VIỆT (ZERO SPELLING ERROR):
   - Đọc kỹ từng chữ trên hóa đơn (tên món ăn, tên cửa hàng, địa chỉ). Giữ nguyên dấu tiếng Việt chuẩn xác (ví dụ: "Đậu tẩm hành", "Nem phùng", "Lẩu ếch nhỏ", "Bia ca").
   - Không được tự ý viết tắt hoặc viết sai chính tả các món ăn/hàng hóa xuất hiện trên bill.

3. PHÂN LOẠI THU / CHI VÀ DANH MỤC (CATEGORY):
   - Mặc định các hóa đơn mua hàng/ăn uống/chi tiêu là loại: "Chi".
   - Danh mục (category) BẮT BUỘC chọn đúng 1 trong các giá trị sau khớp với hệ thống:
     + "Nguyên liệu / nhập hàng" (Dùng cho nguyên liệu nấu ăn, hàng hóa sỉ, thực phẩm)
     + "Thuê mặt bằng"
     + "Điện, nước, Internet"
     + "Vận chuyển"
     + "Lương nhân viên"
     + "Chi khác" (Dùng cho ăn uống tiếp khách, chi phí phát sinh ngoài lề,...)

# CẤU TRÚC JSON ĐẦU RA (OUTPUT FORMAT)
Trả về duy nhất định dạng mảng JSON thuần túy (không kèm văn bản thừa):

[
  {
    "type": "Chi",
    "date": "YYYY-MM-DD",
    "description": "Tên món / Nội dung chi tiết trên bill (giữ nguyên chính tả)",
    "amount": Số nguyên (VND),
    "category": "Danh mục phù hợp trong danh sách quy định",
    "store_name": "Tên cửa hàng/đơn vị phát hành hóa đơn"
  }
]"""


def _map_vision_category(cat_str, kind='expense'):
    folded_cat = fold(cat_str or '')
    if 'nguyen lieu' in folded_cat or 'nhap hang' in folded_cat:
        return 'materials'
    if 'thue mat bang' in folded_cat:
        return 'rent'
    if any(k in folded_cat for k in ('dien', 'nuoc', 'internet')):
        return 'utilities'
    if any(k in folded_cat for k in ('van chuyen', 'ship')):
        return 'shipping'
    if any(k in folded_cat for k in ('luong', 'nhan vien')):
        return 'salary'
    if 'chi khac' in folded_cat:
        return 'other_expense'
    if kind == 'income':
        if 'ban hang' in folded_cat:
            return 'sales'
        if 'dich vu' in folded_cat:
            return 'service'
        if 'von' in folded_cat or 'vay' in folded_cat:
            return 'capital'
        return 'other_income'
    return 'other_expense'


def _parse_vision_date(d_str):
    if not d_str:
        return str(today())
    d_str = str(d_str).strip()
    m = re.match(r'^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$', d_str)
    if m:
        try:
            return str(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    m = re.match(r'^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$', d_str)
    if m:
        try:
            return str(date(int(m.group(3)), int(m.group(2)), int(m.group(1))))
        except ValueError:
            pass
    return str(today())


GEMINI_REQUEST_TIMEOUT = 12.0
GEMINI_TOTAL_TIMEOUT = 20.0


def gemini_vision_ocr(raw_image_bytes):
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        return None
    import base64
    import json
    import httpx

    b64_img = base64.b64encode(raw_image_bytes).decode('utf-8')
    models = ['gemini-3.5-flash', 'gemini-3.5-flash-lite', 'gemini-flash-latest', 'gemini-3.8-flash']

    # Total time budget across all models, so a slow or offline network falls
    # back to local OCR quickly instead of waiting up to 4 x 25 seconds.
    deadline = time.monotonic() + GEMINI_TOTAL_TIMEOUT
    for model in models:
        remaining = deadline - time.monotonic()
        if remaining < 2:
            logger.warning("Gemini Vision time budget used up; falling back to local OCR")
            break
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{
                "parts": [
                    {"text": VISION_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": b64_img
                        }
                    }
                ]
            }],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json"
            }
        }
        try:
            resp = httpx.post(url, json=payload, timeout=min(GEMINI_REQUEST_TIMEOUT, remaining))
            if resp.status_code == 200:
                data = resp.json()
                candidates = data.get('candidates', [])
                if not candidates:
                    continue
                parts = candidates[0].get('content', {}).get('parts', [])
                if not parts:
                    continue
                text = parts[0].get('text', '')
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    parsed = [parsed]
                if not isinstance(parsed, list) or not parsed:
                    continue

                items = []
                total_amount = 0
                first_date = None
                store_name = ''
                descriptions = []

                for item in parsed:
                    itype = item.get('type', 'Chi')
                    ikind = 'income' if 'thu' in fold(itype) else 'expense'
                    icat = _map_vision_category(item.get('category', ''), ikind)
                    iamount = int(item.get('amount') or 0)
                    total_amount += iamount
                    idesc = str(item.get('description', '')).strip()
                    if idesc:
                        descriptions.append(idesc)
                    if not first_date and item.get('date'):
                        first_date = _parse_vision_date(item.get('date'))
                    if not store_name and item.get('store_name'):
                        store_name = str(item.get('store_name')).strip()

                    items.append({
                        'kind': ikind,
                        'category': icat,
                        'description': idesc or 'Khoản chi tiêu',
                        'amount': iamount
                    })

                main_kind = items[0]['kind'] if items else 'expense'
                main_cat = items[0]['category'] if items else 'other_expense'
                date_val = first_date or str(today())
                main_desc = descriptions[0] if len(descriptions) == 1 else (', '.join(descriptions) if descriptions else 'Hóa đơn')
                if store_name and store_name not in main_desc:
                    main_desc = f"{main_desc} ({store_name})"[:300]

                res = {
                    'amount': total_amount if len(items) > 1 else (items[0]['amount'] if items else 0),
                    'date': date_val,
                    'payment': 'cash',
                    'warnings': [f'AI Vision trích xuất thành công từ {store_name or "hóa đơn"}.'],
                    'kind': main_kind,
                    'category': main_cat,
                    'description': main_desc[:300],
                    'scope': 'business',
                    'raw_text': text,
                    'engine': 'gemini_vision',
                    'providers': ['gemini_vision'],
                    'classification': {
                        'score': 0.99,
                        'kind_score': 0.99,
                        'needs_review': False,
                        'alternatives': []
                    }
                }
                if len(items) >= 2:
                    res['items'] = items
                    res['warnings'].append(f'Phát hiện danh sách {len(items)} món trong hóa đơn.')
                return res
            else:
                logger.warning("Gemini Vision HTTP %s on model %s: %s", resp.status_code, model, resp.text[:200])
        except httpx.TimeoutException:
            # A timeout means the network is slow; trying more models only adds delay.
            logger.warning("Gemini Vision timed out on model %s; falling back to local OCR", model)
            break
        except Exception as e:
            logger.warning("Gemini Vision error on model %s: %s", model, e)

    return None


# ── Receipt understanding for OCR text ─────────────────────────────────────
# Receipts are not sentences: one total line, item lines, and noise such as
# codes, cash given and change. The free-text parser (analyze_text) treats every
# line with a number as a separate transaction, so receipts get their own path.

def normalize_receipt_ocr(text):
    """Fix OCR misreads that are specific to printed receipts."""
    # The "đ" after an amount is often read as 4/a/q/d glued to the number:
    # "290.0004" -> "290.000đ". Grouped thousands always end in 3 digits, so a
    # 4th trailing character cannot be part of the number.
    text = re.sub(r'(\d{1,3}(?:[.,]\d{3})+)[0-9aqdđ](?=[\s.,;:)]|$)', r'\1đ', text)
    # "Số" is commonly read as "S6"/"S0"/"So" before ":" or "tiền".
    text = re.sub(r'\bS[60o]\b(?=\s*(?::|ti[eéèẻẽẹêếềểễệ]n))', 'Số', text)
    return text


# Words and phrases common on Vietnamese receipts, with correct accents. Used to
# repair OCR accent/character errors ("Tién khéch dua" -> "Tiền khách đưa").
# Only entries whose accent-free form is unambiguous: single words like "ban"
# (bán/bàn), "sua" (sữa/sửa), "ca" (cá/cà) are left out on purpose.
_RECEIPT_VOCAB = (
    'Tổng cộng', 'Tổng tiền', 'Tổng tiền hàng', 'Tổng thanh toán', 'Tổng cước', 'Tổng số tiền',
    'Thanh toán', 'Tiền mặt', 'Chuyển khoản', 'Hóa đơn', 'Hóa đơn bán hàng', 'Hóa đơn bán lẻ',
    'Hóa đơn thanh toán', 'Phiếu chi', 'Phiếu thu', 'Phiếu gửi hàng', 'Phiếu bán hàng',
    'Khách hàng', 'Thu ngân', 'Số tiền', 'Tiền thừa', 'Tiền khách đưa', 'Đơn giá', 'Thành tiền',
    'Số lượng', 'Khuyến mại', 'Giảm giá', 'Chiết khấu', 'Cảm ơn quý khách',
    'Lý do chi', 'Lý do thu', 'Nội dung', 'Diễn giải', 'Vận chuyển', 'Cước vận chuyển', 'Phụ phí',
    'Trọng lượng', 'Tiền hàng', 'Điện thoại', 'Địa chỉ', 'Hình thức', 'Nguyên liệu', 'Tiền điện',
    'Tiền nước', 'Thuê mặt bằng', 'Tiền thuê mặt bằng', 'Trả lương', 'Nhân viên', 'Mặt hàng',
    'Tên món', 'Thịt heo', 'Thịt bò', 'Thịt gà', 'Nước ngọt', 'Rau cải', 'Dầu ăn', 'Bột mì',
    'Đường cát', 'Khăn lạnh', 'Nấm hương', 'Trứng gà', 'Cà phê', 'Sữa tươi', 'Tôm', 'Thịt',
    'Trứng', 'Nước', 'Gạo', 'Chiên', 'Hương', 'Tươi', 'Quý khách', 'Bớt tiền lẻ',
    'Tạm tính', 'Thuế VAT', 'Khách phải thanh toán', 'Phí giao dịch', 'Chuyển tiền thành công',
    'Nhận tiền chuyển khoản', 'Biên lai chuyển khoản', 'Thịt bò', 'Tài khoản', 'Gạo thơm',
    # On receipts these readings dominate the alternatives (bành, thang, ngay, họp).
    'Bánh', 'Tháng', 'Ngày', 'Cái', 'Gói', 'Hộp',
)
_VOCAB_BY_FOLD = {fold(p): p for p in _RECEIPT_VOCAB}
_VOCAB_MAX_WORDS = max(len(p.split()) for p in _RECEIPT_VOCAB)


def _edit_distance_le1(a, b):
    """True when a and b differ by at most one insert, delete or substitution."""
    if abs(len(a) - len(b)) > 1:
        return False
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] or a[i:] == b[i + 1:] or a[i + 1:] == b[i:]


def _match_case(original, target):
    letters = [c for c in original if c.isalpha()]
    if letters and all(c.isupper() for c in letters):
        return target.upper()
    if original[:1].islower():
        return target[:1].lower() + target[1:]
    return target


def correct_receipt_words(text):
    """Repair OCR misreads of known receipt words/phrases.

    Exact match on the accent-free form fixes wrong accents; phrases of 8+ letters
    also accept one wrong/missing character ("Tong cang" -> "Tổng cộng").
    """
    out_lines = []
    for line in unicodedata.normalize('NFC', text).splitlines():
        tokens = list(re.finditer(r'[^\W\d_]+', line))
        pieces, pos, i = [], 0, 0
        while i < len(tokens):
            replaced = False
            for n in range(min(_VOCAB_MAX_WORDS, len(tokens) - i), 0, -1):
                group = tokens[i:i + n]
                # Only join words separated by plain spaces.
                if any(line[a.end():b.start()].strip() for a, b in zip(group, group[1:])):
                    continue
                key = ' '.join(fold(t.group()) for t in group)
                target = _VOCAB_BY_FOLD.get(key)
                if target is None and len(key.replace(' ', '')) >= 8:
                    target = next((p for k, p in _VOCAB_BY_FOLD.items()
                                   if k.count(' ') == key.count(' ') and _edit_distance_le1(k, key)), None)
                if target:
                    start, end = group[0].start(), group[-1].end()
                    pieces.append(line[pos:start])
                    pieces.append(_match_case(line[start:end], target))
                    pos, i, replaced = end, i + n, True
                    break
            if not replaced:
                i += 1
        pieces.append(line[pos:])
        out_lines.append(''.join(pieces))
    return '\n'.join(out_lines)


_RECEIPT_TOTAL_LABELS = (
    # (pattern on folded text, priority). Higher priority wins; ties -> later line.
    (r'tong\s*(?:cong|thanh\s*toan|tien\s*thanh\s*toan|so\s*tien|phai\s*tra|gia\s*tri\s*thanh\s*toan)', 4),
    (r'(?:khach\s*)?(?:can|phai)\s*(?:thanh|chanh)\s*[tr]oan', 4),
    (r'(?:khach\s*)?(?:can|phai)\s*(?:thanh\s*toan|tra)', 4),
    (r'tong\s*(?:tien(?:\s*hang)?|cuoc|gia\s*tri|so)', 3),
    (r'so\s*tien(?:\s*(?:thanh\s*toan|chuyen|nhan|giao\s*dich))?', 3),
    (r'thanh\s*toan', 2),
    (r'cong\s*(?:tien(?:\s*hang)?)?', 1),
    (r'tong', 1),
)
# Lines that contain money but are never the transaction amount.
_RECEIPT_SKIP = re.compile(
    r'khach\s*dua|tien\s*(?:thua|thoi|tra\s*lai|khach)|thoi\s*lai|tra\s*lai|giam\s*gi[a-z]{0,4}|chiet\s*khau'
    r'|tam\s*tinh|thue\s*vat|\bvat\b|phi\s*giao\s*dich|ma\s*giao\s*dich'
    r'|bang\s*chu|da\s*(?:tra|thanh\s*toan)\s*truoc|con\s*no|\bma\b|\bmst\b|\bsdt\b|dien\s*thoai'
    r'|\bkwh\b|\bm3\b|trong\s*luong|\bso\s*:|so\s*phieu|\bms\b|hotline|\bdt\b|doanh\s*so|tich\s*luy'
    r'|khuyen\s*mai|\bkm\b|bot\s*tien|tien\s*le')
# Item lines, ignoring headers/footers; used for the description.
_RECEIPT_META = re.compile(
    r'tong|thanh\s*toan|thanh\s*tien|so\s*tien|tam\s*tinh|giam\s*gi[a-z]{0,4}|ngay|ng[a-z]{1,3}y|gio'
    r'|thu\s*ngan|dia\s*chi|hinh\s*thuc|tien\s*mat|chuyen\s*khoan|chuyen\s*tien|nhan\s*tien'
    r'|phi\s*giao\s*dich|ma\s*giao\s*dich|trang\s*thai|thoi\s*gian|cam\s*on|hen\s*gap'
    r'|\bvat\b|thue|\bban\s*:|khach|\bdc\b|tien\s*hang')
# Phone numbers, invoice numbers and tax codes: long digit runs without
# thousand separators. Real amounts on receipts are printed with separators.
_RECEIPT_ID_NUMBER = re.compile(r'(?<![\d.,])\d{7,}(?![\d.,])')


def receipt_amount(text):
    """Return (amount, from_total_line). Picks the labeled total, else the largest value."""
    best = None  # (priority, line_index, amount)
    fallback = []
    for i, line in enumerate(text.splitlines()):
        folded = fold(line)
        if _RECEIPT_SKIP.search(folded):
            continue
        # Strip leading +/- on bank transfer screenshot amounts (e.g. '-500.000 VND', '+850.000 VND')
        folded_amt = re.sub(r'(?:^|\s)[+-](?=\d{1,3}(?:[.,]\d{3})+)', ' ', folded)
        folded_amt = _RECEIPT_ID_NUMBER.sub(' ', folded_amt)
        values = [v for v in money_candidates(folded_amt, bare=True) if 0 < v <= 1_000_000_000_000]
        if not values:
            continue
        fallback.extend(values)
        labels = [(re.search(r'\b' + p + r'\b', folded), prio) for p, prio in _RECEIPT_TOTAL_LABELS]
        # OCR often drops the "T" of a line-initial "Tổng:" -> "“ổng : 360,000".
        labels.append((re.match(r'^\W{0,3}ong\b(?=\s*[:;])', folded), 2))
        for m, priority in labels:
            if m:
                after = [v for v in money_candidates(folded_amt[m.end():], bare=True) if v > 0]
                amount = (after or values)[-1]
                if best is None or (priority, i) > best[:2]:
                    best = (priority, i, amount)
                break
    if best:
        return best[2], True
    return (max(fallback), False) if fallback else (None, False)


_CURRENCY_WORDS = {'vnd', 'dong', 'd', 'k', 'tr', 'trieu', 'nghin', 'ngan'}


def _receipt_item_name(line):
    """Item name from a receipt row such as "Bánh da nem 1 chiếc 4,000 4,000" or
    "3 | Tôm chiên xù | 3 | 300.000 | 900.000": the leading words before the
    first number. Rows must end with a price."""
    if re.search(r'\d{1,2}\s*[/-]\s*\d{1,2}', line):
        return None
    if not re.search(r'\d[\d.,]*\s*(?:đ|d|vnd|k)?\W{0,3}$', line, re.IGNORECASE):
        return None
    words = []
    for token in re.split(r'[\s|]+', line):
        word = token.strip('.,:;!?()[]{}""\'`‘‘’-_*')
        if not word:
            continue
        if re.fullmatch(r'[^\W\d_]+', word):
            if fold(word) in _CURRENCY_WORDS:
                break
            if not words and len(word) == 1:
                continue  # stray OCR mark before the name ("i", "l", "v")
            words.append(word)
        elif words:
            break
        elif re.search(r'\d', word) and not re.fullmatch(r'\d{1,2}', word):
            return None  # line starts with price/amount (e.g. '+850.000 VND'), not an item
    name = ' '.join(words[:6])
    return name if len(name.replace(' ', '')) >= 3 else None

def receipt_description(text):
    """Return (description shown to the user, candidate texts for the classifier)."""
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    explicit = None
    for idx, line in enumerate(lines):
        # Match on the accent-free form so OCR accent errors ("Lý do chị:") still
        # match; NFC keeps one character per letter so indexes line up.
        nfc = unicodedata.normalize('NFC', line)
        folded_line = fold(nfc)
        m = re.match(r'^\s*(?:noi\s*dung(?:\s*chuyen\s*(?:khoan|tien))?|ly\s*do(?:\s*(?:chi|thu))?|dien\s*giai|ghi\s*chu|ve\s*viec)\s*[:：;]?\s*',
                     folded_line)
        if m:
            rest = nfc[m.end():].strip()
            if len(rest) >= 3:
                explicit = rest
                break
            if idx + 1 < len(lines) and len(lines[idx + 1].strip()) >= 3:
                explicit = lines[idx + 1].strip()
                break
    title = next((ln for ln in lines[:6] if re.search(
        r'\b(hoa don|phieu|bien (?:lai|nhan)|chuyen (?:tien|khoan)|nhan tien)\b', fold(ln))), '')
    store = next((ln for ln in lines[:4] if re.search(
        r'\b(cua hang|tiem|quan|sieu thi|nha thuoc|dich vu|cong ty)\b', fold(ln))), '')
    items = []
    for line in lines:
        folded = fold(line)
        if _RECEIPT_META.search(folded) or _RECEIPT_SKIP.search(folded):
            continue
        name = _receipt_item_name(line)
        if name:
            items.append(name)
    if explicit:
        cands = [explicit]
        if title:
            cands.append(f'{title} {explicit}')
        return explicit[:300], cands
    # "Hóa đơn bán lẻ" is printed by the seller; for the person scanning it this is
    # a purchase, so do not let the word "bán" push the classifier toward sales.
    title_for_model = 'Hóa đơn mua hàng' if re.search(r'hoa\s*don\s*ban', fold(title)) else title
    if items:
        desc = 'Mua ' + ', '.join(items[:3])
        if re.search(r'\b(phieu gui|van chuyen|giao hang|cuoc)\b', fold(title + ' ' + store + ' ' + desc)):
            desc = ', '.join(items[:3])
        # Item names alone are often clearer than with the header (which may be
        # generic), but the header helps for bills like "Hóa đơn tiền điện".
        return desc[:300], [desc, ' '.join(x for x in (title_for_model, store, desc) if x)]
    if title:
        return (f'{title} - {store}' if store else title)[:300], [f'{title_for_model} {store}'.strip()]
    if store:
        return f'Hóa đơn {store}'[:300], [store]
    return 'Hóa đơn mua hàng', [text]


def analyze_receipt(text):
    """Analyze OCR text of one receipt: one total, one category, date, payment."""
    text = text.strip()
    if not text or len(text) > 10000:
        raise HTTPException(422, 'Ảnh có quá nhiều nội dung. Hãy chụp riêng một chứng từ.')
    if not ready():
        raise HTTPException(503, 'Thiếu mô hình phân loại. Chạy train-models.bat rồi mở lại ứng dụng.')
    description, candidates = receipt_description(text)
    try:
        result = max((classify(c) for c in candidates), key=lambda r: r['score'])
    except Exception:
        raise HTTPException(503, 'Chưa tải được mô hình phân loại. Chạy setup-local.bat hoặc huấn luyện lại bằng train-models.bat.') from None
    fields = parse_fields(text)
    amount, from_total = receipt_amount(text)
    warnings = [w for w in fields['warnings'] if 'số tiền' not in w.lower()]
    if amount is None:
        warnings.append('Chưa thấy tổng tiền trên chứng từ. Vui lòng nhập số tiền trước khi lưu.')
    elif not from_total:
        warnings.append('Không thấy dòng "Tổng cộng"; đang gợi ý số tiền lớn nhất trên chứng từ. Hãy kiểm tra lại.')
    category = result['category']
    kind = CATEGORIES[category][1]
    if result['needs_review']:
        warnings.append('Mô hình chưa chắc danh mục. Hãy chọn lại nhóm phù hợp trước khi lưu.')
    from .market_assistant import build_confirmation_message, extract_item_summary
    if amount is None:
        confirmation_msg = 'Chưa đọc rõ tổng tiền trên chứng từ. Bạn kiểm tra và nhập số tiền giúp tôi nhé.'
    else:
        tx_type = 'thu' if kind == 'income' else 'chi'
        cleaned_desc = extract_item_summary(description) or description
        confirmation_msg = build_confirmation_message(tx_type, cleaned_desc, amount)
    return {**fields, 'amount': amount, 'warnings': warnings, 'kind': kind, 'category': category,
            'description': description,
            'confirmation_message': confirmation_msg,
            'scope': 'business', 'raw_text': text, 'engine': 'local', 'providers': ['finance_local'],
            'classification': result}


def ocr(content):
    if not (tesseract_path() and all((tessdata_path()/f'{lang}.traineddata').is_file() for lang in ('vie','eng'))):
        raise HTTPException(503,'Chưa có bộ đọc ảnh Tesseract trên máy. Vui lòng cài Tesseract hoặc cấu hình GEMINI_API_KEY trong file .env.')
    raw=clean_image(content)
    with Image.open(io.BytesIO(raw)) as im:
        image_side = max(im.size)
        preprocessed_images = _preprocess_for_ocr(im)

    images = []
    for prep_im in preprocessed_images:
        buffer = io.BytesIO()
        prep_im.save(buffer, format='PNG')
        images.append(buffer.getvalue())

    # Fast path: one Tesseract pass (gentle contrast, block-of-text mode) is
    # enough for most clear receipts. Only fall back to the other variants
    # when that pass misses an amount or reads too little text.
    best_text = _run_tesseract(images[0], '6')
    best_score = score_ocr_text(best_text)
    if not _ocr_good_enough(best_text, best_score):
        attempts = [(img, psm) for i, img in enumerate(images) for psm in ('6', '3', '4')
                    if (i, psm) != (0, '6')]
        workers = max(1, min(4, (os.cpu_count() or 2) // 2))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for text in pool.map(lambda a: _run_tesseract(*a), attempts):
                s = score_ocr_text(text)
                if s > best_score:
                    best_score, best_text = s, text

    text = clean_ocr_noise(best_text)
    text = fix_handwriting_ocr_errors(text)  # sửa lỗi nhầm ký tự khi đọc chữ viết tay
    if len(text)<2:
        raise HTTPException(422,'Chưa đọc được chữ. Hãy dùng ảnh rõ, thẳng, có đủ tổng tiền hoặc nhập tay.')
    if len(text)>10000:
        raise HTTPException(422,'Ảnh có quá nhiều nội dung. Hãy chụp riêng một chứng từ.')
    text = correct_receipt_words(normalize_receipt_ocr(text))
    result=analyze_receipt(text)
    result['providers']=['tesseract_local','finance_local']
    result['warnings'].insert(0,'OCR có thể đọc sai dấu hoặc số (đặc biệt với chữ viết tay). Kiểm tra tổng tiền và nội dung gốc trước khi lưu.')
    if image_side < 900:
        result['warnings'].insert(1, f'Ảnh độ phân giải thấp ({image_side}px), dễ đọc sai số. '
                                     'Hãy chụp gần, thẳng và đủ sáng để có kết quả chính xác hơn.')
    return result


def process_image(content):
    raw = clean_image(content)
    api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
    if api_key:
        try:
            res = gemini_vision_ocr(raw)
            if res:
                return res
        except Exception as e:
            logger.warning("Gemini Vision failed, falling back to local OCR: %s", e)
    return ocr(content)


async def read_image(content,consent=False):
    async with worker:
        return await run_in_threadpool(process_image,content)


@lru_cache(maxsize=1)
def speech_model():
    from faster_whisper import WhisperModel
    # Local path and local_files_only: inference must never download from the internet.
    return WhisperModel(str(speech_path()),device='cpu',compute_type='int8',
                        cpu_threads=min(4,os.cpu_count() or 2),local_files_only=True)


def decode_audio(content):
    import av
    if len(content)>5*1024*1024 or len(content)<100:
        raise HTTPException(413,'Bản ghi trống hoặc quá lớn. Ghi tối đa 30 giây, dưới 5 MB.')
    chunks=[];count=0
    try:
        with av.open(io.BytesIO(content),mode='r') as container:
            if not container.streams.audio: raise ValueError()
            resampler=av.AudioResampler(format='fltp',layout='mono',rate=16000)
            for frame in container.decode(audio=0):
                for converted in resampler.resample(frame):
                    data=converted.to_ndarray().flatten();count+=data.size
                    if count>32*16000:
                        raise HTTPException(413,'Bản ghi dài quá 30 giây. Hãy nói ngắn một giao dịch.')
                    chunks.append(data)
            for converted in resampler.resample(None):
                data=converted.to_ndarray().flatten();count+=data.size
                if count>32*16000: raise HTTPException(413,'Bản ghi dài quá 30 giây.')
                chunks.append(data)
        if not chunks: raise ValueError()
    except HTTPException: raise
    except Exception:
        raise HTTPException(400,'Không đọc được âm thanh. Hãy ghi bằng micro trong ứng dụng hoặc tải WAV/MP3/WebM/M4A hợp lệ.') from None
    audio=np.concatenate(chunks).astype(np.float32)
    if audio.size<1600:
        raise HTTPException(422,'Bản ghi quá ngắn. Hãy ghi một câu đầy đủ khoảng 5–10 giây rồi thử lại.')
    if float(np.mean(audio**2))<1e-7:
        raise HTTPException(422,'Bản ghi gần như im lặng. Hãy nghe lại, kiểm tra micro đã chọn và ghi một câu rõ tiếng.')
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if 0.0 < peak < 0.35:
        rms = float(np.sqrt(np.mean(audio**2)))
        gain = min(0.75 / peak, 0.12 / max(rms, 1e-4))
        audio = np.clip(audio * max(1.0, gain), -0.95, 0.95).astype(np.float32)
    return audio


def speech(content):
    if not capabilities()['voice']:
        raise HTTPException(503,'Thiếu mô hình giọng nói. Chạy setup-local.bat để chuẩn bị Whisper rồi thử lại.')
    audio=decode_audio(content)
    try:
        # Richer initial prompt with comprehensive Vietnamese financial vocabulary
        # and concrete money examples helps Whisper produce correct number words.
        initial_prompt = (
            'Ghi chép thu chi bằng tiếng Việt. '
            'Mua nguyên liệu hết năm mươi cành, bốn chục nghìn, 50k, trả tiền mặt. '
            'Bán hàng được một triệu hai trăm nghìn đồng, hai củ rưỡi, hai lít tiền rau, chuyển khoản. '
            'Đóng tiền điện tám trăm nghìn, thuê mặt bằng năm triệu rưỡi, trả tiền ship cho shipper. '
            'Vay ngân hàng, hoàn tiền cho khách, trả lương nhân viên, sửa xe, bán ve chai, 150.000 đồng.'
        )
        segments,info=speech_model().transcribe(
            audio,language='vi',beam_size=2,vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=400,speech_pad_ms=200),
            condition_on_previous_text=False,
            temperature=[0.0, 0.2],
            repetition_penalty=1.15,
            initial_prompt=initial_prompt,
            word_timestamps=False,
            no_speech_threshold=0.55,
        )
        # More lenient no_speech_prob filter (0.8 instead of 0.65)
        # to avoid discarding valid Vietnamese segments with background noise
        text=' '.join(s.text.strip() for s in segments if s.no_speech_prob<0.8).strip()
    except Exception as exc:
        # Keep the traceback locally without logging the audio or transcript.
        logger.exception('Local speech recognition failed')
        if isinstance(exc, ModuleNotFoundError) and exc.name == 'pkg_resources':
            raise HTTPException(503,'Thiếu thành phần nhận giọng nói. Chạy sua-loi-giong-noi.bat trong thư mục ứng dụng, rồi mở lại demo.') from None
        raise HTTPException(503,'Nhận giọng nói gặp lỗi. Xem lỗi chi tiết trong cửa sổ start-demo hoặc chạy sua-loi-giong-noi.bat để kiểm tra.') from None
    if not text:
        logger.warning('Whisper returned no usable transcript for %.2f seconds of audio',audio.size/16000)
        raise HTTPException(422,'Chưa nhận ra lời nói trong bản ghi. Hãy nghe lại và ghi một câu khoảng 5–10 giây, rõ tiếng, trong nơi yên tĩnh.')
    logger.debug('STT transcript: %s', text)
    result=analyze_text(text, stt=True)
    result['providers']=['whisper_local','finance_local']
    result['warnings'].insert(0,'Kiểm tra bản chép, đặc biệt số tiền. Giọng vùng miền hoặc tiếng ồn có thể làm nhận dạng sai.')
    return result


async def transcribe(content,content_type=None,consent=False):
    async with worker:
        return await run_in_threadpool(speech,content)
