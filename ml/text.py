"""Shared deterministic normalization; it does not assign transaction labels.

v2: Preserves meaningful Vietnamese financial keywords that were being stripped.
"""
import re
import unicodedata


def normalize(text):
    text = unicodedata.normalize('NFC', text).lower().replace('đ', 'd')
    text = ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn')
    # Replace digit sequences with a single token to preserve the fact that
    # a number was present without overfitting to specific amounts.
    text = re.sub(r'\d+(?:[.,/]\d+)*', ' _num_ ', text)
    text = re.sub(r'[^a-z_\s]', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()
