"""Inference for two locally trained models. No network calls or training here.

v2: Compatible with FeatureUnion vectorizer and improved scoring.
"""
from functools import lru_cache
from pathlib import Path
import json
import joblib
import numpy as np
from ml.text import normalize

MODEL_DIR = Path(__file__).resolve().parents[1] / 'models' / 'finance'


@lru_cache(maxsize=1)
def load_models():
    # These fixed files are shipped/trained with the app; never accept uploaded pickle/joblib files.
    return tuple(joblib.load(MODEL_DIR / f'{name}.joblib') for name in ('vectorizer','kind','category'))


def ready():
    return all((MODEL_DIR/f'{x}.joblib').is_file() for x in ('vectorizer','kind','category'))


def metrics():
    path = MODEL_DIR/'metrics.json'
    if not path.is_file():
        return {}
    r=json.loads(path.read_text(encoding='utf-8'))
    return {'version':r['version'], 'counts':r['counts'], 'data_origin':'Dữ liệu mô phỏng',
            'scores':{k:{m:v[m] for m in ('test_accuracy','test_macro_f1')} for k,v in r['tasks'].items()}}


def classify(text):
    vectorizer, kind_model, category_model = load_models()
    normalized = normalize(text)
    x = vectorizer.transform([normalized])
    probs = category_model.predict_proba(x)[0]
    order = np.argsort(probs)[::-1]
    kind_probs = kind_model.predict_proba(x)[0]
    idx = int(np.argmax(kind_probs))
    score = float(probs[order[0]])
    margin = score - float(probs[order[1]])
    # Check if the input produced any features at all
    if hasattr(x, 'nnz'):
        has_features = x.nnz > 0
    else:
        has_features = np.any(x != 0) if hasattr(x, '__array__') else True
    return {'category':str(category_model.classes_[order[0]]),
            'kind':str(kind_model.classes_[idx]), 'score':round(score,4),
            'kind_score':round(float(kind_probs[idx]),4),
            'needs_review':bool(score < 0.45 or margin < 0.10 or not has_features),
            'alternatives':[{'category':str(category_model.classes_[i]),'score':round(float(probs[i]),4)} for i in order[:3]]}
