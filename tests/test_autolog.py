import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tracker


class AutoLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.vault = self.root/'Vault'
        self.vault.mkdir()
        self.path = self.root/'test.db'
        self.db = tracker.connect(self.path)
        self.run_cmd('add-company','Acme')
        self.run_cmd('add-project','Website','--company','Acme')
        self.run_cmd('vault',str(self.vault))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def run_cmd(self,*args,now=1800000000):
        return tracker.execute(self.db,tracker.parser().parse_args(list(args)),now)

    def test_stop_logs_company_project_and_duration_once(self):
        self.run_cmd('auto-obsidian','on')
        self.run_cmd('start','--company','Acme','--project','Website','--note','Homepage work',now=100)
        self.db.execute('BEGIN IMMEDIATE')
        result=self.run_cmd('stop',now=5500)
        path=Path(result['obsidian_path'])
        content=path.read_text()
        for item in ['Acme','Website','01:30:00','Homepage work','duration_seconds: 5400']:
            self.assertIn(item,content)
        self.assertIsNone(self.run_cmd('status')['running'])
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(self.run_cmd('retry-obsidian')['attempted'],0)
        # Simulate a crash between publishing a note and saving its receipt.
        self.db.execute('UPDATE obsidian_jobs SET path=NULL')
        self.assertEqual(self.run_cmd('retry-obsidian')['delivered'],1)
        self.assertEqual(len(list(path.parent.glob('*.md'))),1)

    def test_missing_vault_preserves_stop_and_retries_after_restart(self):
        self.run_cmd('auto-obsidian','on')
        self.run_cmd('start','--company','Acme',now=100)
        self.vault.rmdir()
        self.db.execute('BEGIN IMMEDIATE')
        result=self.run_cmd('stop',now=200)
        self.assertIn('warning',result)
        self.db.close()
        self.db=tracker.connect(self.path)
        self.assertIsNone(self.run_cmd('status')['running'])
        self.assertEqual(self.run_cmd('status')['obsidian_pending'],1)
        # A later destination change must not redirect the pending session.
        other=self.root/'Other'
        other.mkdir()
        self.run_cmd('vault',str(other))
        self.vault.mkdir()
        path=Path(self.run_cmd('retry-obsidian')['obsidian_path'])
        self.assertEqual(path.parent,self.vault/'Time Tracker')
        self.assertEqual(self.run_cmd('status')['obsidian_pending'],0)

    def test_off_and_clear_prevent_new_jobs(self):
        self.run_cmd('start','--company','Acme',now=100)
        self.assertNotIn('obsidian_path',self.run_cmd('stop',now=200))
        self.run_cmd('auto-obsidian','on')
        self.run_cmd('vault','--clear')
        self.assertFalse(self.run_cmd('status')['obsidian_autolog'])
        with self.assertRaises(ValueError):
            self.run_cmd('auto-obsidian','on')
        self.assertFalse((self.vault/'Time Tracker').exists())

    def test_existing_changed_note_is_preserved(self):
        self.run_cmd('auto-obsidian','on')
        self.run_cmd('start','--company','Acme',now=100)
        path=Path(self.run_cmd('stop',now=200)['obsidian_path'])
        path.write_text('Personal edits')
        self.db.execute('UPDATE obsidian_jobs SET path=NULL')
        self.assertIn('warning',self.run_cmd('retry-obsidian'))
        self.assertEqual(path.read_text(),'Personal edits')

    def test_bridge_stop_reports_success_with_pending_log(self):
        self.run_cmd('auto-obsidian','on')
        self.run_cmd('start','--company','Acme',now=100)
        self.vault.rmdir()
        proc=subprocess.run([sys.executable,str(Path(tracker.__file__).with_name('bridge.py')),json.dumps({'args':['stop']})],env=dict(os.environ,TIME_TRACKER_DB=str(self.path)),capture_output=True,text=True,check=True)
        data=json.loads(proc.stdout)
        self.assertTrue(data['ok'])
        self.assertIsNone(data['status']['running'])
        self.assertIn('warning',data['result'])
        self.assertEqual(data['status']['obsidian_pending'],1)


if __name__ == '__main__':
    unittest.main()
