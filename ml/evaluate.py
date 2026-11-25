"""Score the trained models on the hand-written challenge set.

datasets/challenge.csv is written by hand in real-life style (market speech,
no accents, receipt lines, abbreviations) and is NEVER used for training or for
choosing hyperparameters. It is a sanity check that the models generalize beyond
the synthetic templates in train/validation/test.

Usage: python -m ml.evaluate [--errors]
"""
import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

from ml.predict import classify, load_models

ROOT = Path(__file__).resolve().parents[1]
INCOME = {'sales', 'service', 'capital', 'other_income'}


def evaluate(path=ROOT / 'datasets' / 'challenge.csv'):
    with path.open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    load_models.cache_clear()
    per_cat = defaultdict(lambda: [0, 0])
    kind_ok = cat_ok = 0
    errors = []
    confusions = Counter()
    for r in rows:
        res = classify(r['text'])
        true_kind = 'income' if r['category'] in INCOME else 'expense'
        # The app shows the kind implied by the category, so score that.
        pred_kind = 'income' if res['category'] in INCOME else 'expense'
        kind_ok += pred_kind == true_kind
        hit = res['category'] == r['category']
        cat_ok += hit
        per_cat[r['category']][0] += hit
        per_cat[r['category']][1] += 1
        if not hit:
            errors.append((r['text'], r['category'], res['category'], res['score']))
            confusions[(r['category'], res['category'])] += 1
    n = len(rows)
    return {'n': n, 'kind_accuracy': kind_ok / n, 'category_accuracy': cat_ok / n,
            'per_category': {c: ok / tot for c, (ok, tot) in sorted(per_cat.items())},
            'errors': errors, 'confusions': confusions.most_common(8)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--errors', action='store_true', help='print every misclassified sentence')
    args = ap.parse_args()
    r = evaluate()
    print(f'Bộ kiểm tra viết tay: {r["n"]} câu (không dùng để huấn luyện)')
    print(f'  Thu/Chi đúng:   {r["kind_accuracy"]:.1%}')
    print(f'  Danh mục đúng:  {r["category_accuracy"]:.1%}')
    for cat, acc in r['per_category'].items():
        print(f'    {cat:14} {acc:.0%}')
    print('  Nhầm nhiều nhất:', ', '.join(f'{a}->{b} ({k})' for (a, b), k in r['confusions']))
    if args.errors:
        for text, true, pred, score in r['errors']:
            print(f'  [{true} -> {pred} {score:.2f}] {text}')


if __name__ == '__main__':
    main()
