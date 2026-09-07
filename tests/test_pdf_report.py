import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from pypdf import PdfReader
import tracker


class PdfExportTests(unittest.TestCase):
    def test_filtered_export_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            db = tracker.connect(Path(folder) / 'test.sqlite3')
            def run(*args, now=1800000000):
                return tracker.execute(db, tracker.parser().parse_args(list(args)), now)
            run('add-company', 'Curaçao & Partners <Studio>')
            run('add-company', 'Excluded Company')
            run('add-project', 'Website', '--company', 'Curaçao & Partners <Studio>')
            start = tracker.datetime.fromisoformat('2026-09-07T09:00:00-04:00').timestamp()
            run('start', '--company', 'Curaçao & Partners <Studio>', '--project', 'Website', now=start)
            path = Path(folder) / 'filtered.pdf'
            result = run('report', 'daily', '--date', '2026-09-07', '--company', 'Curaçao & Partners <Studio>', '--project', 'Website', '--pdf', '--output', str(path), now=start+5400)
            self.assertEqual(result['total_hours'], 1.5)
            text = '\n'.join(page.extract_text() for page in PdfReader(path).pages)
            for expected in ['Curaçao & Partners <Studio>', 'Website', '01:30:00', 'PROVISIONAL']:
                self.assertIn(expected, text)
            self.assertNotIn('Excluded Company', text)
            self.assertIsNotNone(run('status')['running'])
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                run('report', 'daily', '--pdf', '--output', str(path))
            self.assertEqual(path.read_bytes(), before)
            db.close()

    def test_empty_cli_export(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'empty.pdf'
            result = subprocess.run([sys.executable, str(SCRIPTS / 'tracker.py'), '--db', str(Path(folder)/'test.db'), 'report', 'yearly', '--date', '2026-01-01', '--pdf', '--output', str(path)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['pdf_path'], str(path))
            reader = PdfReader(path)
            self.assertEqual(len(reader.pages), 1)
            self.assertIn('No time recorded', reader.pages[0].extract_text())

    def test_missing_pdf_dependency_has_actionable_error(self):
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run([sys.executable, '-S', str(SCRIPTS / 'tracker.py'), '--db', str(Path(folder)/'test.db'), 'report', 'daily', '--pdf'], capture_output=True, text=True, env={'PATH': '/usr/bin'})
            self.assertEqual(result.returncode, 1)
            self.assertIn('python-reportlab', json.loads(result.stderr)['error'])


if __name__ == '__main__':
    unittest.main()
