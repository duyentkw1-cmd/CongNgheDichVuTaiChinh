"""Cross-platform bootstrap using Python's standard library only."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def run(args):
    subprocess.run([str(x) for x in args],cwd=ROOT,check=True)

def main():
    if not (3,11)<=sys.version_info[:2]<(3,14):
        print('Please install Python 3.12 64-bit from https://www.python.org/downloads/ and try again.')
        return 1
    py=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    if not py.is_file():run([sys.executable,'-m','venv',ROOT/'.venv'])
    requirements=ROOT/'backend'/'requirements.txt'
    digest=hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker=ROOT/'.venv'/'local-ready.txt'
    if not marker.exists() or marker.read_text().strip()!=digest:
        print('Installing Python libraries. Internet is needed for this first setup.',flush=True)
        run([py,'-m','pip','install','-r',requirements])
    if not (ROOT/'models'/'finance'/'category.joblib').is_file():run([py,'-m','ml.train'])
    run([py,ROOT/'scripts'/'prepare_models.py'])
    marker.unlink(missing_ok=True)
    run([py,ROOT/'scripts'/'doctor.py','--speech'])
    marker.write_text(digest)
    print('\nSetup complete. Windows OCR engine: run install-ocr-windows.bat once if MISSING.')
    print('Next: start-demo.bat (Windows) or bash start-demo.sh (macOS/Linux).')
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except (subprocess.CalledProcessError,OSError) as e:
        print('Setup failed:',e)
        print('See HUONG-DAN-WINDOWS.md. Check Python version, internet and available disk space.')
        raise SystemExit(1)
