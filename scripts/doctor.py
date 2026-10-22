"""Check local AI dependencies; --speech also exercises Whisper and VAD offline."""
import argparse
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.ai import connection_status, speech_model, ocr, speech, tesseract_path, tessdata_path
from fastapi import HTTPException
from ml.predict import load_models


def check_speech():
    import numpy as np
    from faster_whisper.vad import get_speech_timestamps

    model = speech_model()
    print('MODEL OK - loaded local Whisper weights', flush=True)
    silence = np.zeros(16000, dtype=np.float32)
    get_speech_timestamps(silence)
    print('VAD OK - local speech detector ran', flush=True)
    segments, _ = model.transcribe(silence, language='vi', vad_filter=False, beam_size=1)
    list(segments)  # Inference is lazy; consume it to catch runtime/DLL failures.
    print('WHISPER OK - inference ran on a one-second silence sample', flush=True)
    print('This checks runtime operation, not recognition accuracy on human speech.')


def check_ocr():
    print('Tesseract executable:', tesseract_path(), flush=True)
    print('OCR language directory:', tessdata_path(), flush=True)
    for language in ('vie', 'eng'):
        path = tessdata_path() / (language + '.traineddata')
        print(language + '.traineddata:', path.stat().st_size if path.is_file() else 'MISSING', flush=True)
    sample = Path(__file__).resolve().parents[1] / 'backend' / 'assets' / 'sample-receipt.png'
    result = ocr(sample.read_bytes())
    if result['amount'] != 650000:
        raise RuntimeError('OCR ran but the bundled sample did not produce the expected amount 650000.')
    print('OCR OK - real sample receipt read as 650000 VND', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speech', action='store_true', help='Load Whisper, run VAD and a short inference test')
    parser.add_argument('--ocr', action='store_true', help='Read the bundled receipt with the local Tesseract engine')
    parser.add_argument('--audio', type=Path, help='Optionally diagnose one of your own audio files (under 5 MB)')
    args = parser.parse_args()
    status = connection_status()
    failed = not status['text']
    print('\nSO THU CHI - LOCAL AI', flush=True)
    if status['text']:
        try:
            load_models()
            print('OK       finance - model loaded', flush=True)
        except Exception:
            traceback.print_exc()
            print('FAILED   finance - run train-models.bat')
            failed = True
    else:
        print('MISSING  finance - run train-models.bat')

    if status['voice']:
        try:
            # Explicitly check this Windows dependency on every platform as well.
            importlib.import_module('pkg_resources')
            importlib.import_module('faster_whisper')
            if args.speech:
                check_speech()
            else:
                print('OK       whisper - imports and files only; use --speech for runtime test')
        except Exception as exc:
            traceback.print_exc()
            print('FAILED   whisper - runtime could not start')
            if isinstance(exc, ModuleNotFoundError) and exc.name == 'pkg_resources':
                print('Run: .venv\\Scripts\\python.exe -m pip install "setuptools==80.9.0"')
            failed = True
    else:
        print('MISSING  whisper - run setup-local.bat to prepare dependencies and models')
        failed = True

    if args.ocr:
        try:
            check_ocr()
        except HTTPException as exc:
            print('FAILED   OCR - HTTP', exc.status_code, exc.detail, flush=True)
            failed = True
        except Exception:
            traceback.print_exc()
            print('FAILED   OCR - sample check did not pass')
            failed = True
    else:
        print(('FOUND    ' if status['image'] else 'MISSING  ') + 'tesseract - presence check only')
    if not status['image']:
        print('For image OCR: run install-ocr-windows.bat. This is separate from speech.')
    if args.audio:
        try:
            with args.audio.open('rb') as source:
                result = speech(source.read(5 * 1024 * 1024 + 1))
            print('AUDIO OK - transcript has', len(result['raw_text']), 'characters; review the transaction in the app.')
        except HTTPException as exc:
            print('AUDIO FAILED - HTTP', exc.status_code, exc.detail)
            failed = True
        except Exception:
            traceback.print_exc()
            failed = True
    print('No API keys needed. No external AI inference requests.')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
