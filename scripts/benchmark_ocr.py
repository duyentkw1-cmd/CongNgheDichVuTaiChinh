"""Benchmark speed and accuracy of the local receipt OCR pipeline.

Generates synthetic Vietnamese receipts with known answers (amount, date,
category), degrades them like phone photos (tilt, blur, noise, shadow, JPEG),
then runs backend.ai.ocr on each and reports accuracy and time per level.

Usage:
    python scripts/benchmark_ocr.py              # 12 receipts x 3 levels
    python scripts/benchmark_ocr.py -n 24        # more receipts
    python scripts/benchmark_ocr.py --save out/  # also write the images
    python scripts/benchmark_ocr.py --verbose    # print every wrong field

Synthetic data only: numbers show relative before/after progress, not
real-world accuracy on customers' receipts.
"""
import argparse
import io
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

import numpy as np  # noqa: E402
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

FONT = ROOT / 'backend' / 'assets' / 'DejaVuSans.ttf'
FONT_BOLD = ROOT / 'backend' / 'assets' / 'DejaVuSans-Bold.ttf'

STORES = ['AN PHÁT', 'HƯNG THỊNH', 'MINH CHÂU', 'PHÚC LỘC', 'HOÀNG GIA', 'THANH BÌNH', 'BẢO NGỌC', 'TÂN TIẾN']


def fmt_money(v, style):
    s = f'{v:,}'
    if style == 0:
        return s.replace(',', '.')
    if style == 1:
        return s.replace(',', '.') + 'đ'
    if style == 2:
        return s.replace(',', '.') + ' VND'
    return s  # 1,250,000


def fmt_date(d, style, rng):
    if style == 0:
        return f'Ngày: {d:%d/%m/%Y}'
    if style == 1:
        return f'{d:%d/%m/%Y} {rng.randint(7, 21):02d}:{rng.randint(0, 59):02d}'
    return f'Ngày {d.day:02d} tháng {d.month:02d} năm {d.year}'


def materials(rng):
    goods = [('Rau cải', 15000, 40000), ('Thịt heo', 120000, 380000), ('Đường cát', 25000, 60000),
             ('Bột mì', 30000, 90000), ('Trứng gà', 35000, 70000), ('Dầu ăn', 45000, 120000),
             ('Cà phê hạt', 200000, 500000), ('Sữa tươi', 60000, 220000), ('Gạo', 150000, 400000)]
    picks = rng.sample(goods, rng.randint(2, 4))
    items = [(n, rng.randrange(lo, hi, 1000)) for n, lo, hi in picks]
    total = sum(v for _, v in items)
    store = rng.choice(STORES)
    lines = [('title', store), ('sub', 'Cửa hàng thực phẩm'), ('head', 'HÓA ĐƠN BÁN LẺ')]
    return 'materials', total, store, lines, items, rng.choice(['TỔNG CỘNG', 'Tổng tiền', 'Thanh toán'])


def utilities(rng):
    kind = rng.choice(['điện', 'nước', 'internet'])
    total = rng.randrange(150000, 1800000, 500)
    lines = [('title', f'HÓA ĐƠN TIỀN {kind.upper()}'), ('sub', f'Kỳ thanh toán: tháng {rng.randint(1, 12)}'),
             ('row', ('Mã khách hàng', f'PE{rng.randint(10**8, 10**9)}'))]
    if kind == 'điện':
        lines.append(('row', ('Điện năng tiêu thụ', f'{rng.randint(80, 600)} kWh')))
    elif kind == 'nước':
        lines.append(('row', ('Lượng nước tiêu thụ', f'{rng.randint(5, 40)} m3')))
    return 'utilities', total, None, lines, [], 'Tổng tiền thanh toán'


def rent(rng):
    total = rng.choice([3000000, 4500000, 5000000, 6000000, 7500000, 8000000])
    lines = [('title', 'PHIẾU CHI'), ('sub', f'Số: PC{rng.randint(100, 999)}'),
             ('text', f'Lý do chi: Tiền thuê mặt bằng tháng {rng.randint(1, 12)}')]
    return 'rent', total, None, lines, [], 'Số tiền'


def shipping(rng):
    fee = rng.randrange(20000, 90000, 1000)
    extra = rng.choice([0, 5000, 10000, 15000])
    items = [('Cước vận chuyển', fee)] + ([('Phụ phí', extra)] if extra else [])
    lines = [('title', 'PHIẾU GỬI HÀNG'), ('sub', 'Dịch vụ giao hàng nhanh'),
             ('row', ('Mã vận đơn', f'VD{rng.randint(10**7, 10**8)}')),
             ('row', ('Trọng lượng', f'{rng.randint(1, 15)} kg'))]
    return 'shipping', fee + extra, None, lines, items, 'Tổng cước'


def salary(rng):
    total = rng.randrange(4000000, 12000000, 100000)
    lines = [('title', 'PHIẾU CHI'), ('sub', f'Số: PC{rng.randint(100, 999)}'),
             ('text', f'Lý do chi: Trả lương nhân viên tháng {rng.randint(1, 12)}')]
    return 'salary', total, None, lines, [], 'Số tiền'


def sales(rng):
    dishes = [('Cơm sườn', 35000), ('Phở bò', 45000), ('Bún chả', 40000), ('Trà đá', 5000), ('Cà phê sữa', 25000)]
    picks = rng.sample(dishes, rng.randint(2, 4))
    items = []
    for n, p in picks:
        q = rng.randint(1, 6)
        items.append((f'{n} x{q}', p * q))
    total = sum(v for _, v in items)
    store = rng.choice(STORES)
    lines = [('title', f'QUÁN {store}'), ('head', 'PHIẾU THU TIỀN'),
             ('text', 'Nội dung: Thu tiền bán hàng')]
    return 'sales', total, store, lines, items, 'TỔNG CỘNG'


TEMPLATES = [materials, utilities, rent, shipping, salary, sales]


def make_receipt(rng, idx):
    category, total, _store, lines, items, total_label = TEMPLATES[idx % len(TEMPLATES)](rng)
    d = date(2026, rng.randint(1, 11), rng.randint(1, 28))
    money_style = rng.randint(0, 3)
    date_style = rng.randint(0, 2)
    paid_cash = rng.random() < 0.5

    W = 820
    base = rng.randint(24, 30)
    f = ImageFont.truetype(str(FONT), base)
    fb = ImageFont.truetype(str(FONT_BOLD), base)
    ft = ImageFont.truetype(str(FONT_BOLD), base + 12)
    img = Image.new('RGB', (W, 1400), 'white')
    dr = ImageDraw.Draw(img)
    y = 50
    pad = 60

    def center(text, font, color=(30, 30, 30)):
        nonlocal y
        w = dr.textlength(text, font=font)
        dr.text(((W - w) / 2, y), text, font=font, fill=color)
        y += int(font.size * 1.7)

    def row(left, right, font=f):
        nonlocal y
        dr.text((pad, y), left, font=font, fill=(40, 40, 40))
        w = dr.textlength(right, font=font)
        dr.text((W - pad - w, y), right, font=font, fill=(40, 40, 40))
        y += int(font.size * 1.9)

    def rule():
        nonlocal y
        dr.line((pad, y, W - pad, y), fill=(170, 170, 170), width=2)
        y += 25

    for kind, val in lines:
        if kind == 'title':
            center(val, ft)
        elif kind == 'sub':
            center(val, f, (90, 90, 90))
        elif kind == 'head':
            y += 10
            center(val, fb)
        elif kind == 'text':
            dr.text((pad, y), val, font=f, fill=(40, 40, 40))
            y += int(base * 1.9)
        elif kind == 'row':
            row(*val)
    dr.text((pad, y), fmt_date(d, date_style, rng), font=f, fill=(40, 40, 40))
    y += int(base * 1.9)
    rule()
    for name, v in items:
        row(name, fmt_money(v, money_style))
    if items:
        rule()
    row(total_label, fmt_money(total, money_style), fb)
    if paid_cash and rng.random() < 0.6:
        given = ((total // 100000) + 1) * 100000 + rng.choice([0, 100000, 400000])
        row('Tiền khách đưa', fmt_money(given, money_style))
        row('Tiền thừa', fmt_money(given - total, money_style))
    dr.text((pad, y), 'Hình thức: ' + ('Tiền mặt' if paid_cash else 'Chuyển khoản'), font=f, fill=(60, 60, 60))
    y += int(base * 2.4)
    center('Cảm ơn quý khách!', f, (110, 110, 110))
    img = img.crop((0, 0, W, y + 30))
    truth = {'amount': total, 'date': d.isoformat(), 'category': category}
    return img, truth


def degrade(img, level, rng):
    """level 0 = clean scan, 1 = typical phone photo, 2 = hard phone photo."""
    if level == 0:
        return img
    angle = rng.uniform(1.5, 3.5) * rng.choice([-1, 1]) if level == 1 else rng.uniform(4, 7) * rng.choice([-1, 1])
    bg = (rng.randint(90, 150),) * 3
    margin = 80
    canvas = Image.new('RGB', (img.width + 2 * margin, img.height + 2 * margin), bg)
    canvas.paste(img, (margin, margin))
    img = canvas.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=bg)
    arr = np.asarray(img).astype(np.float32)
    h, w = arr.shape[:2]
    # Uneven lighting: darker toward one corner.
    gx = np.linspace(0, 1, w)[None, :]
    gy = np.linspace(0, 1, h)[:, None]
    strength = 0.25 if level == 1 else 0.45
    shade = 1 - strength * (gx * rng.random() + gy * rng.random()) / 2
    arr *= shade[..., None]
    if level == 2:
        arr = arr * 0.75 + 40  # low contrast
    arr += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 6 if level == 1 else 12, arr.shape)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    img = img.filter(ImageFilter.GaussianBlur(0.8 if level == 1 else 1.4))
    if level == 2:
        img = img.resize((int(img.width * 0.7), int(img.height * 0.7)), Image.Resampling.BILINEAR)
    else:
        # Phone camera resolution is higher than the receipt render.
        img = img.resize((int(img.width * 1.6), int(img.height * 1.6)), Image.Resampling.BICUBIC)
    out = io.BytesIO()
    img.save(out, 'JPEG', quality=70 if level == 1 else 55)
    return Image.open(io.BytesIO(out.getvalue())).convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-n', type=int, default=12, help='number of receipts')
    ap.add_argument('--seed', type=int, default=2026)
    ap.add_argument('--save', type=Path)
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    for env in ('GEMINI_API_KEY', 'GOOGLE_API_KEY'):
        os.environ.pop(env, None)
    from backend import ai

    rng = random.Random(args.seed)
    receipts = [make_receipt(rng, i) for i in range(args.n)]
    ai.ocr(_png(receipts[0][0]))  # warm-up: load models once so timings are fair

    levels = ['Rõ nét', 'Chụp ĐT', 'Chụp khó']
    stats = {lv: {'amount': 0, 'date': 0, 'category': 0, 'all': 0, 'time': 0.0, 'n': 0} for lv in levels}
    for i, (img, truth) in enumerate(receipts):
        for li, lv in enumerate(levels):
            photo = degrade(img, li, random.Random(args.seed * 100 + i * 10 + li))
            data = _jpeg(photo)
            if args.save:
                args.save.mkdir(parents=True, exist_ok=True)
                photo.save(args.save / f'r{i:02d}_L{li}.jpg', quality=90)
            t = time.perf_counter()
            try:
                res = ai.ocr(data)
            except Exception as e:  # unreadable image counts as all-wrong
                res = {'amount': None, 'date': None, 'category': None, 'raw_text': f'ERROR {e}'}
            dt = time.perf_counter() - t
            s = stats[lv]
            s['n'] += 1
            s['time'] += dt
            ok = {k: res.get(k) == truth[k] for k in ('amount', 'date', 'category')}
            for k, v in ok.items():
                s[k] += v
            s['all'] += all(ok.values())
            if args.verbose and not all(ok.values()):
                wrong = ', '.join(f'{k}: {res.get(k)!r} (đúng {truth[k]!r})' for k, v in ok.items() if not v)
                print(f'[r{i:02d} {lv}] {wrong}')

    print(f'\nOCR benchmark - {args.n} hóa đơn mô phỏng x {len(levels)} mức ảnh\n')
    print(f'{"Mức ảnh":10} {"Số tiền":>8} {"Ngày":>8} {"Danh mục":>9} {"Đúng cả 3":>10} {"TB giây":>8}')
    tot = {'amount': 0, 'date': 0, 'category': 0, 'all': 0, 'time': 0.0, 'n': 0}
    for lv, s in stats.items():
        n = s['n']
        print(f'{lv:10} {s["amount"]/n:8.0%} {s["date"]/n:8.0%} {s["category"]/n:9.0%} {s["all"]/n:10.0%} {s["time"]/n:8.2f}')
        for k in tot:
            tot[k] += s[k]
    n = tot['n']
    print(f'{"Tổng":10} {tot["amount"]/n:8.0%} {tot["date"]/n:8.0%} {tot["category"]/n:9.0%} {tot["all"]/n:10.0%} {tot["time"]/n:8.2f}')


def _jpeg(img):
    b = io.BytesIO()
    img.save(b, 'JPEG', quality=92)
    return b.getvalue()


def _png(img):
    b = io.BytesIO()
    img.save(b, 'PNG')
    return b.getvalue()


if __name__ == '__main__':
    main()
