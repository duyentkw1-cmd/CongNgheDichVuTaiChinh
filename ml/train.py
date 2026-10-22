"""Train two local classifiers; test split is used only for final evaluation.

Usage: python -m ml.train
Change datasets/train.csv / validation.csv; restart backend after training.
No pretrained LLM or external AI service participates in this training.

v2: Enhanced with better hyperparameter search, dual-vectorizer ensemble,
    class weight tuning, and comprehensive metric reporting.
"""
import csv
import hashlib
import json
import platform
from pathlib import Path

import joblib
import sklearn
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion

from ml.text import normalize

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ['sales','service','capital','other_income','materials','rent','utilities','shipping','salary','other_expense']
INCOME = {'sales','service','capital','other_income'}


def load_data():
    splits = {}
    all_groups, all_ids, all_text = set(), set(), set()
    for name in ('train','validation','test'):
        path = ROOT / 'datasets' / f'{name}.csv'
        with path.open(encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
        if not rows:
            raise ValueError(f'{path.name} is empty')
        groups = {r['group_id'] for r in rows}
        texts = {normalize(r['text']) for r in rows}
        ids = {r['id'] for r in rows}
        if len(ids) != len(rows) or all_ids & ids or all_groups & groups:
            raise ValueError('Duplicate id or overlapping group across splits. Fix the data split.')
        if {r['category'] for r in rows} != set(CATEGORIES):
            raise ValueError(f'{name}: every category needs examples')
        for row in rows:
            expected = 'income' if row['category'] in INCOME else 'expense'
            if row['kind'] != expected or row['split'] != name or not row['group_id'] or not row['text'].strip():
                raise ValueError(f'Invalid training row: {row["id"]}')
        all_ids |= ids; all_groups |= groups; all_text |= texts
        splits[name] = rows
    return splits


def train():
    rows = load_data()
    # ── Dual vectorizer: char n-grams + word n-grams ──
    char_vect = TfidfVectorizer(
        analyzer='char_wb', ngram_range=(2, 5), min_df=2,
        sublinear_tf=True, max_features=25000, lowercase=False)
    word_vect = TfidfVectorizer(
        analyzer='word', ngram_range=(1, 3), min_df=2,
        sublinear_tf=True, max_features=15000, lowercase=False)
    vect = FeatureUnion([('char', char_vect), ('word', word_vect)])

    x = { 'train': vect.fit_transform([normalize(r['text']) for r in rows['train']]) }
    x.update({s: vect.transform([normalize(r['text']) for r in rows[s]]) for s in ('validation','test')})
    out = ROOT / 'models' / 'finance'
    out.mkdir(parents=True, exist_ok=True)
    total_features = x['train'].shape[1]
    report = {'version':'local-finance-v2', 'data_origin':'synthetic; not validated on real household data',
              'split_policy':'disjoint semantic seed families; no training on validation or test',
              'counts':{s:len(r) for s,r in rows.items()}, 'features':total_features,
              'python':platform.python_version(), 'sklearn':sklearn.__version__, 'tasks':{}}
    models = {}
    for task in ('kind','category'):
        y = {s:[r[task] for r in rs] for s,rs in rows.items()}
        best, score, best_c = None, -1, None
        # Wider hyperparameter search
        for c in (0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 32.0):
            candidate = LogisticRegression(
                C=c, class_weight='balanced', max_iter=2000,
                random_state=42, solver='lbfgs')
            candidate.fit(x['train'],y['train'])
            f1 = f1_score(y['validation'],candidate.predict(x['validation']),average='macro',zero_division=0)
            if f1 > score:
                best, score, best_c = candidate, float(f1), c
        predicted = best.predict(x['test'])
        report['tasks'][task] = {'selected_C':best_c,'validation_macro_f1':score,
            'test_accuracy':float(accuracy_score(y['test'],predicted)),
            'test_macro_f1':float(f1_score(y['test'],predicted,average='macro',zero_division=0)),
            'classification_report':classification_report(y['test'],predicted,output_dict=True,zero_division=0),
            'labels':list(best.classes_), 'confusion_matrix':confusion_matrix(y['test'],predicted,labels=best.classes_).tolist()}
        models[task] = best
        joblib.dump(best, out / f'{task}.joblib', compress=3)
    joblib.dump(vect, out / 'vectorizer.joblib', compress=3)
    # Human-readable predictions make errors reviewable without rerunning training.
    with (out / 'test_predictions.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f);writer.writerow(['id','text','true_category','predicted_category','true_kind','predicted_kind'])
        for r,cat,kind in zip(rows['test'],models['category'].predict(x['test']),models['kind'].predict(x['test'])):
            writer.writerow([r['id'],r['text'],r['category'],cat,r['kind'],kind])
    report['dataset_sha256']={s:hashlib.sha256((ROOT/'datasets'/f'{s}.csv').read_bytes()).hexdigest() for s in rows}
    report['model_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.glob('*.joblib')}
    (out/'metrics.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    for task, result in report['tasks'].items():
        print(f'{task}: test accuracy={result["test_accuracy"]:.3f}, macro F1={result["test_macro_f1"]:.3f} (SYNTHETIC TEST ONLY)')
    print('Saved:',out)


if __name__ == '__main__':
    train()
