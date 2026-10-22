"""Package source + trained/pretrained models; exclude private ledgers, env and caches."""
import argparse
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EXCLUDED={'.venv','node_modules','data','qa','.git','__pycache__','.cache','.pytest_cache'}

def selected():
    for p in sorted(ROOT.rglob('*')):
        rel=p.relative_to(ROOT)
        if not p.is_file() or p.is_symlink() or any(part in EXCLUDED for part in rel.parts):continue
        if any(part.startswith('.') for part in rel.parts) and str(rel) not in {'.env.example','.gitignore','.dockerignore'}:continue
        if p.suffix in {'.pyc','.zip','.sqlite3','.db','.tsbuildinfo'}:continue
        yield p

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT.parent/'So-Thu-Chi-AI-Local-Full.zip')
    output=parser.parse_args().output.resolve()
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in selected():
            if p.resolve()!=output:z.write(p,Path(ROOT.name)/p.relative_to(ROOT))
    with zipfile.ZipFile(output) as z:
        bad=z.testzip()
        if bad:raise RuntimeError('Corrupt ZIP entry: '+bad)
        for name in ('frontend/dist/index.html','backend/main.py','models/finance/kind.joblib','models/finance/category.joblib',
                     'models/whisper-base/model.bin','models/tessdata/vie.traineddata','datasets/train.csv','train-models.bat'):
            if ROOT.name+'/'+name not in z.namelist():raise RuntimeError('Missing required file: '+name)
        print('Files:',len(z.namelist()))
    print('ZIP:',output)
    print('Size MB:',round(output.stat().st_size/1024/1024,1))

if __name__=='__main__':main()
