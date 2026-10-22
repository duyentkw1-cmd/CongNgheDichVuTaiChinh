"""Regression checks: a failed OCR engine must not be reported as a timeout."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from _isolation import TEMP_DIR
from fastapi import HTTPException
from backend import ai


@unittest.skipUnless(ai.capabilities()['image'], 'Tesseract not installed')
class OCRErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sample = (Path(__file__).resolve().parents[1] / 'backend/assets/sample-receipt.png').read_bytes()

    def test_broken_language_files_are_not_a_timeout(self):
        # Exercise a real immediate Tesseract failure, which used to return 504.
        with tempfile.TemporaryDirectory(prefix='bad-ocr-') as directory:
            for language in ('vie', 'eng'):
                (Path(directory) / (language + '.traineddata')).write_bytes(b'broken test data')
            with patch.dict(os.environ, {'TESSDATA_DIR': directory}), self.assertLogs('backend.ai', level='ERROR'):
                with self.assertRaises(HTTPException) as error:
                    ai.ocr(self.sample)
        self.assertEqual(error.exception.status_code, 503)
        self.assertIn('tiếng Việt/Anh', error.exception.detail)

    def test_only_timeout_expired_returns_504(self):
        with patch.object(ai.subprocess, 'run', side_effect=subprocess.TimeoutExpired('tesseract', 30)):
            with self.assertLogs('backend.ai', level='WARNING'), self.assertRaises(HTTPException) as error:
                ai.ocr(self.sample)
        self.assertEqual(error.exception.status_code, 504)
        self.assertIn('30 giây', error.exception.detail)

    def test_missing_executable_returns_503(self):
        with patch.object(ai.subprocess, 'run', side_effect=FileNotFoundError('test engine unavailable')):
            with self.assertLogs('backend.ai', level='ERROR'), self.assertRaises(HTTPException) as error:
                ai.ocr(self.sample)
        self.assertEqual(error.exception.status_code, 503)

    def test_language_directory_with_spaces_and_accents(self):
        with tempfile.TemporaryDirectory(prefix='ocr-path-') as directory:
            languages = Path(directory) / 'Bộ tiếng Việt có dấu và khoảng trắng'
            languages.mkdir()
            for language in ('vie', 'eng'):
                filename = language + '.traineddata'
                shutil.copy2(ai.tessdata_path() / filename, languages / filename)
            with patch.dict(os.environ, {'TESSDATA_DIR': str(languages)}):
                result = ai.ocr(self.sample)
        self.assertEqual(result['amount'], 650000)
        self.assertEqual(result['category'], 'materials')


if __name__ == '__main__':
    unittest.main(verbosity=2)
