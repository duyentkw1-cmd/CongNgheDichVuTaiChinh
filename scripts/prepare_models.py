"""Explicit first-time model download; never called by inference endpoints."""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def download(url,path):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.part')
    try:
        urllib.request.urlretrieve(url,temp)
        temp.replace(path)
    finally:
        if temp.exists(): temp.unlink()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--upgrade-small',action='store_true')
    args=parser.parse_args()
    name='small' if args.upgrade_small else 'base'
    voice=ROOT/'models'/f'whisper-{name}'
    required=('config.json','model.bin','tokenizer.json','vocabulary.txt')
    if not all((voice/f).is_file() for f in required):
        from huggingface_hub import snapshot_download
        print(f'Downloading pretrained Whisper {name}. No API key or billing required.',flush=True)
        snapshot_download(f'Systran/faster-whisper-{name}',local_dir=voice,allow_patterns=list(required))
    for lang in ('vie','eng'):
        path=ROOT/'models'/'tessdata'/f'{lang}.traineddata'
        if not path.is_file():
            print('Downloading OCR language:',lang,flush=True)
            download(f'https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/main/{lang}.traineddata',path)
    if args.upgrade_small:
        print('Small model downloaded. Set WHISPER_MODEL_PATH=models/whisper-small in .env and restart.')
    print('Local model files are ready. Recognition runs without a network connection.')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        print('Download failed:',str(exc),file=sys.stderr)
        print('Check your connection and run setup-local again. No API payment is needed.',file=sys.stderr)
        raise SystemExit(1)
