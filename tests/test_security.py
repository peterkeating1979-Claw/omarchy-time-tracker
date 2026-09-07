import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker
import bridge
from pdf_report import export_pdf


class SecurityTests(unittest.TestCase):
    def test_database_permissions_and_existing_data(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'private' / 'records.db'
            old = os.umask(0)
            try:
                db = tracker.connect(path)
            finally:
                os.umask(old)
            db.execute("INSERT INTO companies(name) VALUES ('Existing company')")
            db.close()
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
            path.chmod(0o644)
            db = tracker.connect(path)
            self.assertEqual(db.execute('SELECT name FROM companies').fetchone()[0], 'Existing company')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            self.assertEqual(db.execute('PRAGMA trusted_schema').fetchone()[0], 0)
            db.close()

    def test_reject_database_and_journal_links(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / 'target.db'
            tracker.connect(target).close()
            before = target.read_bytes()
            for hard in (False, True):
                link = root / 'link.db'
                if hard:
                    os.link(target, link)
                else:
                    link.symlink_to(target)
                with self.assertRaises((OSError, ValueError)):
                    tracker.connect(link)
                link.unlink()
            journal = root / 'target.db-journal'
            journal.symlink_to(target)
            with self.assertRaises((OSError, ValueError)):
                tracker.connect(target)
            self.assertEqual(target.read_bytes(), before)

    def test_reject_shared_writable_directory_and_fifo(self):
        with tempfile.TemporaryDirectory() as folder:
            shared = Path(folder) / 'shared'
            shared.mkdir()
            shared.chmod(0o777)
            with self.assertRaises(ValueError):
                tracker.connect(shared / 'test.db')
            fifo = Path(folder) / 'pipe'
            os.mkfifo(fifo)
            with self.assertRaises(ValueError):
                tracker.connect(fifo)

    def test_bridge_rejects_malformed_requests_before_storage(self):
        for raw in ['[]', 'null', '{', '{"args":"status"}', '{"args":[1]}', '{"args":["--help"]}', '{"args":["companies","--he"]}', '{"args":["report","invalid"]}', '{"args":[],"unexpected":true}', '{"args":["status","--db","/tmp/elsewhere"]}', json.dumps({'args':['x'*17000]})]:
            with self.subTest(raw=raw[:50]), self.assertRaises(ValueError):
                bridge.parse_request(raw)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'not-created.db'
            env = dict(os.environ, TIME_TRACKER_DB=str(target))
            result = subprocess.run([sys.executable, str(Path(bridge.__file__)), '{"args":["report","invalid"]}'], env=env, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1)
            self.assertFalse(json.loads(result.stdout)['ok'])
            self.assertFalse(target.exists())

    def test_input_limits_and_sql_metacharacters(self):
        with tempfile.TemporaryDirectory() as folder:
            db = tracker.connect(Path(folder) / 'test.db')
            for name in ['x'*201, 'a\x00b', 'fake\u202ename']:
                with self.assertRaises(ValueError):
                    tracker.execute(db, tracker.parser().parse_args(['add-company', name]))
            name = "Acme'); DROP TABLE companies; --"
            tracker.execute(db, tracker.parser().parse_args(['add-company', name]))
            self.assertEqual(db.execute('SELECT name FROM companies').fetchone()[0], name)
            db.close()

    def test_pdf_symlink_refusal_and_permissions(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            db = tracker.connect(root / 'test.db')
            report = tracker.execute(db, tracker.parser().parse_args(['report','daily']))
            db.close()
            target = root / 'outside.pdf'
            link = root / 'report.pdf'
            link.symlink_to(target)
            with self.assertRaises(ValueError):
                export_pdf(report, str(link))
            self.assertFalse(target.exists())
            link.unlink()
            export_pdf(report, str(link))
            self.assertEqual(stat.S_IMODE(link.stat().st_mode), 0o600)


if __name__ == '__main__':
    unittest.main()
