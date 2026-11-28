"""Shared deterministic normalization; it does not assign transaction labels.

v3: Preserves meaningful Vietnamese financial keywords and normalizes
    common unambiguous market/business shorthand and STT typos.
"""
import re
import unicodedata

ABBREVIATIONS = {
    'kh': 'khach',
    'khack': 'khach',
    'ck': 'chuyen khoan',
    'tm': 'tien mat',
    'ncc': 'nha cung cap',
    'nl': 'nguyen lieu',
    'mb': 'mat bang',
    'nv': 'nhan vien',
    'dv': 'dich vu',
    'shiper': 'shipper',
    'kiot': 'ki ot',
    'nghing': 'nghin',
    'ko': 'khong',
}

_ABBR_RE = re.compile(r'\b(' + '|'.join(ABBREVIATIONS) + r')\b')


def normalize(text):
    text = unicodedata.normalize('NFC', text).lower().replace('đ', 'd')
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    # Replace digit sequences with a single token to preserve the fact that
    # a number was present without overfitting to specific amounts.
    text = re.sub(r'\d+(?:[.,/]\d+)*', ' _num_ ', text)
    text = re.sub(r'[^a-z_\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return ''
    text = _ABBR_RE.sub(lambda m: ABBREVIATIONS[m.group(1)], text)
    return re.sub(r'\s+', ' ', text).strip()
